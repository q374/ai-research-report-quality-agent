import { expect, test, type Route } from "@playwright/test";

import {
  mockLangGraphAPI,
  MOCK_THREAD_ID,
  MOCK_THREAD_ID_2,
} from "./utils/mock-api";

const THREADS = [
  {
    thread_id: MOCK_THREAD_ID,
    title: "First conversation",
    updated_at: "2025-06-01T12:00:00Z",
  },
  {
    thread_id: MOCK_THREAD_ID_2,
    title: "Second conversation",
    updated_at: "2025-06-02T12:00:00Z",
  },
];
const DEMO_THREAD_ID = "7cfa5f8f-a2f8-47ad-acbd-da7137baf990";
const SVG_PROMPT_THREAD_ID = "00000000-0000-0000-0000-000000000777";
const CITATION_THREAD_ID = "00000000-0000-0000-0000-000000000779";
const SVG_PROMPT_MARKER = "LEAK-STRICT-SVG-PROMPT-SHOULD-DISAPPEAR";
const OPTIMISTIC_PROMPT_MARKER = "LEAK-OPTIMISTIC-SVG-PROMPT-SHOULD-DISAPPEAR";

test.describe("Thread history", () => {
  test("sidebar shows existing threads", async ({ page }) => {
    mockLangGraphAPI(page, { threads: THREADS });

    await page.goto("/workspace/chats/new");

    // Both thread titles should appear in the sidebar
    await expect(page.getByText("First conversation")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByText("Second conversation")).toBeVisible();
  });

  test("clicking a thread in sidebar navigates to it", async ({ page }) => {
    mockLangGraphAPI(page, { threads: THREADS });

    await page.goto("/workspace/chats/new");

    // Wait for sidebar to populate
    const firstThread = page.getByText("First conversation");
    await expect(firstThread).toBeVisible({ timeout: 15_000 });

    // Click on the first thread
    await firstThread.click();

    // Should navigate to that thread's URL
    await page.waitForURL(`**/workspace/chats/${MOCK_THREAD_ID}`);
    await expect(page).toHaveURL(new RegExp(MOCK_THREAD_ID));
  });

  test("existing thread loads historical messages", async ({ page }) => {
    mockLangGraphAPI(page, { threads: THREADS });

    // Navigate directly to an existing thread
    await page.goto(`/workspace/chats/${MOCK_THREAD_ID}`);

    // The historical AI response should be displayed
    await expect(
      page.getByText("Response in thread First conversation"),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("historical evidence citation opens as a safe external link", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: CITATION_THREAD_ID,
          title: "Evidence citation",
          updated_at: "2026-09-20T01:00:00Z",
          messages: [
            {
              type: "ai",
              id: "msg-ai-citation",
              content:
                "Deep Research 会执行研究。[citation:来源1](https://example.com/source)",
            },
          ],
        },
      ],
    });

    await page.goto(`/workspace/chats/${CITATION_THREAD_ID}`);

    const citation = page.getByRole("link", { name: "来源1" });
    await expect(citation).toBeVisible({ timeout: 15_000 });
    await expect(citation).toHaveAttribute(
      "href",
      "https://example.com/source",
    );
    await expect(citation).toHaveAttribute("target", "_blank");
    await expect(citation).toHaveAttribute("rel", /noopener/);
    await expect(citation).toHaveAttribute("rel", /noreferrer/);
  });

  test("blocked evidence validation explains why the report cannot be published", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: CITATION_THREAD_ID,
          title: "Blocked evidence report",
          updated_at: "2026-09-20T02:00:00Z",
        },
      ],
    });
    await page.route("**/evidence-validation", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          validation_id: "validation-1",
          auto_status: "blocked",
          validation_result: {
            status: "blocked",
            finding_counts: { blocker: 2, warning: 1, info: 0 },
            findings: [
              {
                rule_id: "EV-05",
                severity: "blocker",
                message: "可见引用链接与结构化证据绑定不一致。",
                required_action: "修正引用与证据绑定。",
              },
              {
                rule_id: "EV-06",
                severity: "blocker",
                message: "正文超过长度上限。",
                required_action: "缩减正文后重新校验。",
              },
            ],
          },
        }),
      }),
    );

    await page.goto(`/workspace/chats/${CITATION_THREAD_ID}`);

    const banner = page.getByTestId("evidence-validation-banner");
    await expect(banner).toContainText("质量校验：暂不建议发布", {
      timeout: 15_000,
    });
    await expect(banner).toContainText("2 个阻断问题，1 个提醒");
    await expect(banner).toContainText("EV-05");
    await expect(banner).toContainText("修正引用与证据绑定");
    const bannerBox = await banner.boundingBox();
    expect(bannerBox?.y).toBeGreaterThanOrEqual(48);
    await expect(banner.getByRole("button", { name: "确认通过" })).toHaveCount(
      0,
    );
  });

  test("reviewer approval is bound to the report hash and updates the banner", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: CITATION_THREAD_ID,
          title: "Reviewable evidence report",
          updated_at: "2026-09-20T03:00:00Z",
        },
      ],
    });
    let submittedReview: Record<string, unknown> | undefined;
    await page.route("**/evidence-validation/reviews", async (route) => {
      submittedReview = route.request().postDataJSON() as Record<
        string,
        unknown
      >;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          validation_id: "validation-reviewable",
          report_hash: "hash-reviewable",
          final_status: "confirmed",
          review_decisions: [{ decision: "approved" }],
          validation_result: {
            status: "confirmed",
            finding_counts: { blocker: 0, warning: 0, info: 0 },
            findings: [],
          },
        }),
      });
    });
    await page.route("**/evidence-validation", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          validation_id: "validation-reviewable",
          report_hash: "hash-reviewable",
          final_status: "review_required",
          review_decisions: [],
          validation_result: {
            status: "review_required",
            finding_counts: { blocker: 0, warning: 0, info: 0 },
            findings: [],
          },
        }),
      }),
    );

    await page.goto(`/workspace/chats/${CITATION_THREAD_ID}`);

    const banner = page.getByTestId("evidence-validation-banner");
    await expect(banner).toContainText("质量校验：需要人工复核", {
      timeout: 15_000,
    });
    await banner.getByRole("button", { name: "确认通过" }).click();
    await expect(banner).toContainText("质量校验：已通过");
    expect(submittedReview).toMatchObject({
      decision: "approved",
      expected_report_hash: "hash-reviewable",
    });
    expect(submittedReview?.idempotency_key).toEqual(expect.any(String));
  });

  test("rejection requires a reason and keeps the audit reason visible", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: CITATION_THREAD_ID,
          title: "Rejected evidence report",
          updated_at: "2026-09-20T04:00:00Z",
        },
      ],
    });
    await page.route("**/evidence-validation/reviews", async (route) => {
      const request = route.request().postDataJSON() as Record<string, unknown>;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          validation_id: "validation-rejected",
          report_hash: "hash-rejected",
          final_status: "rejected",
          review_decisions: [
            {
              decision: "rejected",
              reason: request.reason,
            },
          ],
          validation_result: {
            status: "rejected",
            finding_counts: { blocker: 0, warning: 0, info: 0 },
            findings: [],
          },
        }),
      });
    });
    await page.route("**/evidence-validation", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          validation_id: "validation-rejected",
          report_hash: "hash-rejected",
          final_status: "review_required",
          review_decisions: [],
          validation_result: {
            status: "review_required",
            finding_counts: { blocker: 0, warning: 0, info: 0 },
            findings: [],
          },
        }),
      }),
    );

    await page.goto(`/workspace/chats/${CITATION_THREAD_ID}`);

    const banner = page.getByTestId("evidence-validation-banner");
    await banner.getByRole("button", { name: "拒绝发布" }).click();
    await expect(banner.getByRole("alert")).toContainText("必须填写理由");
    await banner.getByRole("textbox", { name: "复核理由" }).fill("证据不充分");
    await banner.getByRole("button", { name: "拒绝发布" }).click();
    await expect(banner).toContainText("质量校验：已拒绝发布");
    await expect(banner).toContainText("复核意见：证据不充分");
  });

  test("deleting an inactive chat keeps the current chat open", async ({
    page,
  }) => {
    mockLangGraphAPI(page, { threads: THREADS });

    await page.goto(`/workspace/chats/${MOCK_THREAD_ID}`);
    await expect(
      page.getByText("Response in thread First conversation"),
    ).toBeVisible({ timeout: 15_000 });

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const inactiveThreadItem = sidebar
      .locator("[data-sidebar='menu-item']")
      .filter({
        has: page.getByRole("button", { name: /more/i }),
        hasText: "Second conversation",
      })
      .first();
    await expect(inactiveThreadItem).toBeVisible();
    await inactiveThreadItem.hover();
    await inactiveThreadItem.getByRole("button", { name: /more/i }).click();
    await page.getByRole("menuitem", { name: /delete/i }).click();

    await expect(page).toHaveURL(new RegExp(MOCK_THREAD_ID));
    await expect(
      page.getByText("Response in thread First conversation"),
    ).toBeVisible();
    await expect(sidebar.getByText("Second conversation")).toHaveCount(0);
  });

  test("new chat does not show previous thread messages after client-side navigation", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: SVG_PROMPT_THREAD_ID,
          title: "SVG artifact prompt",
          updated_at: "2025-06-03T12:00:00Z",
          messages: [
            {
              type: "human",
              id: "msg-human-svg-prompt",
              content: [
                {
                  type: "text",
                  text: `请严格执行：\n1. 使用 write_file 创建 /mnt/user-data/outputs/shared.svg，内容包含 ${SVG_PROMPT_MARKER}\n2. 最终回复只输出 Markdown 图片。`,
                },
              ],
            },
            {
              type: "ai",
              id: "msg-ai-svg-prompt",
              content: "![shared artifact](/mnt/user-data/outputs/shared.svg)",
            },
          ],
        },
      ],
    });

    await page.goto(`/workspace/chats/${SVG_PROMPT_THREAD_ID}`);
    await expect(page.getByText(SVG_PROMPT_MARKER)).toBeVisible({
      timeout: 15_000,
    });

    await page
      .locator("[data-sidebar='sidebar'] a[href='/workspace/chats/new']")
      .click();
    await page.waitForURL("**/workspace/chats/new");

    await expect(page.getByText(SVG_PROMPT_MARKER)).toBeHidden();
    await expect(page.getByPlaceholder(/how can i assist you/i)).toBeVisible();
  });

  test("new chat does not show previous optimistic user message after client-side navigation", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID_2,
          title: "Destination conversation",
          updated_at: "2025-06-04T12:00:00Z",
        },
      ],
    });

    const metadataOnlyStream = async (route: Route) => {
      const body = [
        {
          event: "metadata",
          data: {
            run_id: "00000000-0000-0000-0000-000000000778",
            thread_id: MOCK_THREAD_ID,
          },
        },
        { event: "end", data: {} },
      ]
        .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
        .join("");

      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body,
      });
    };

    await page.route("**/api/langgraph/runs/stream", metadataOnlyStream);
    await page.route(
      "**/api/langgraph/threads/*/runs/stream",
      metadataOnlyStream,
    );

    await page.goto("/workspace/chats/new");
    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });
    await textarea.fill(
      `请严格执行：使用 write_file 创建 shared.svg，内容包含 ${OPTIMISTIC_PROMPT_MARKER}。`,
    );
    await textarea.press("Enter");

    await expect(page.getByText(OPTIMISTIC_PROMPT_MARKER)).toBeVisible();

    await page.getByText("Destination conversation").click();
    await page.waitForURL(`**/workspace/chats/${MOCK_THREAD_ID_2}`);
    await expect(page.getByText(OPTIMISTIC_PROMPT_MARKER)).toHaveCount(0);

    await page
      .locator("[data-sidebar='sidebar'] a[href='/workspace/chats/new']")
      .click();
    await page.waitForURL("**/workspace/chats/new");

    await expect(page.getByText(OPTIMISTIC_PROMPT_MARKER)).toHaveCount(0);
    await expect(page.getByPlaceholder(/how can i assist you/i)).toBeVisible();
  });

  test("deleting the active newly created chat returns to the new chat screen", async ({
    page,
  }) => {
    mockLangGraphAPI(page);
    await page.route(/\/api\/threads\/[^/]+$/, (route) => {
      if (route.request().method() === "DELETE") {
        return route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Local cleanup failed" }),
        });
      }
      return route.fallback();
    });

    await page.goto("/workspace/chats/new");
    const textarea = page.getByPlaceholder(/how can i assist you/i);
    await expect(textarea).toBeVisible({ timeout: 15_000 });
    await textarea.fill("What should disappear after deletion?");
    await textarea.press("Enter");

    await expect(page.getByText("Hello from DeerFlow!")).toBeVisible({
      timeout: 15_000,
    });

    const sidebar = page.locator("[data-sidebar='sidebar']");
    const recentThreadItem = sidebar
      .locator("[data-sidebar='menu-item']")
      .filter({
        has: page.getByRole("button", { name: /more/i }),
        hasText: "New Chat",
      })
      .first();
    await expect(recentThreadItem).toBeVisible();
    await recentThreadItem.hover();
    await recentThreadItem.getByRole("button", { name: /more/i }).click();
    await page.getByRole("menuitem", { name: /delete/i }).click();

    await expect(page).toHaveURL(/\/workspace\/chats\/new$/);
    await expect(page.getByText("Previous question")).toHaveCount(0);
    await expect(page.getByText("Hello from DeerFlow!")).toHaveCount(0);
    await expect(page.getByPlaceholder(/how can i assist you/i)).toBeVisible();

    await page.goto(`/workspace/chats/${MOCK_THREAD_ID}`);
    await page.waitForURL("**/workspace/chats/new");
    await expect(page.getByText("Hello from DeerFlow!")).toHaveCount(0);
    await expect(page.getByPlaceholder(/how can i assist you/i)).toBeVisible();
  });

  test("mock thread does not load real backend run history", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: DEMO_THREAD_ID,
          title: "Forecasting 2026 Trends and Opportunities",
          updated_at: "2025-06-01T12:00:00Z",
          messages: [
            {
              type: "human",
              id: `run-human-${DEMO_THREAD_ID}`,
              content: [
                {
                  type: "text",
                  text: "This run-message endpoint should not be called.",
                },
              ],
            },
          ],
        },
      ],
    });
    const backendRunHistoryUrls: string[] = [];
    await page.route(
      /\/api\/langgraph\/threads\/[^/]+\/runs(?:\?|$)/,
      (route) => {
        if (
          route.request().method() === "GET" &&
          route
            .request()
            .url()
            .includes(`/api/langgraph/threads/${DEMO_THREAD_ID}/runs`)
        ) {
          backendRunHistoryUrls.push(route.request().url());
          return route.fulfill({
            status: 500,
            contentType: "application/json",
            body: JSON.stringify({
              error: "mock=true must not load real runs",
            }),
          });
        }
        return route.fallback();
      },
    );
    await page.route(
      /\/api\/threads\/[^/]+\/runs\/[^/]+\/messages(?:\?|$)/,
      (route) => {
        if (
          route.request().method() === "GET" &&
          route.request().url().includes(`/api/threads/${DEMO_THREAD_ID}/runs/`)
        ) {
          backendRunHistoryUrls.push(route.request().url());
          return route.fulfill({
            status: 500,
            contentType: "application/json",
            body: JSON.stringify({
              error: "mock=true must not load real run messages",
            }),
          });
        }
        return route.fallback();
      },
    );

    await page.goto(`/workspace/chats/${DEMO_THREAD_ID}?mock=true`);

    await expect(
      page.getByText("What might be the trends and opportunities in 2026?"),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      page.getByText("I've created a modern, minimalist website"),
    ).toBeVisible();
    expect(backendRunHistoryUrls).toEqual([]);
  });

  test("chats list page shows all threads", async ({ page }) => {
    mockLangGraphAPI(page, { threads: THREADS });

    await page.goto("/workspace/chats");

    // Both threads should be listed in the main content area
    const main = page.locator("main");
    await expect(main.getByText("First conversation")).toBeVisible({
      timeout: 15_000,
    });
    await expect(main.getByText("Second conversation")).toBeVisible();
  });

  test("IM channel threads show their source in thread lists", async ({
    page,
  }) => {
    mockLangGraphAPI(page, {
      threads: [
        {
          thread_id: MOCK_THREAD_ID,
          title: "Feishu conversation",
          updated_at: "2025-06-03T12:00:00Z",
          metadata: {
            channel_source: {
              type: "im_channel",
              provider: "feishu",
              chat_id: "oc_mock",
            },
          },
        },
      ],
    });

    await page.goto("/workspace/chats/new");

    const sidebarThread = page.locator(
      `a[href='/workspace/chats/${MOCK_THREAD_ID}']`,
    );
    await expect(sidebarThread).toBeVisible({ timeout: 15_000 });
    await expect(sidebarThread.getByLabel("Feishu channel")).toBeVisible();

    await page.goto("/workspace/chats");

    const mainThread = page
      .locator("main")
      .locator(`a[href='/workspace/chats/${MOCK_THREAD_ID}']`);
    await expect(mainThread.getByText("Feishu conversation")).toBeVisible({
      timeout: 15_000,
    });
    await expect(mainThread.getByText("Feishu", { exact: true })).toBeVisible();
  });
});
