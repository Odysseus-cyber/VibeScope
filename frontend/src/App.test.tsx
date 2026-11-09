import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import App from "./App";
import { Growth } from "./components";
import { date } from "./api";
import type { AppItem } from "./types";
vi.mock("echarts/core", () => ({
  use: vi.fn(),
  init: () => ({
    setOption: vi.fn(),
    on: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  }),
  graphic: { LinearGradient: class {} },
}));
const meta = {
  mode: "demo",
  as_of: "2026-11-09",
  last_updated: "2026-11-09T00:00:00Z",
  llm_enabled: false,
  categories: ["效率工具", "教育学习"],
  tools: ["Cursor"],
  languages: ["TypeScript"],
};
const app: AppItem = {
  id: 1,
  name: "Garden Notes",
  full_name: "demo/garden-notes",
  description: "个人知识整理工具",
  summary: "用 AI 辅助开发的笔记应用",
  url: "https://github.com/demo/garden-notes",
  homepage: null,
  category: "效率工具",
  tools: ["Cursor"],
  language: "TypeScript",
  kind: "application",
  evidence_level: "explicit",
  stars: 120,
  forks: 8,
  growth_7d: null,
  growth_30d: -4,
  created_at: "2026-10-01T00:00:00Z",
  first_seen_at: "2026-11-01T00:00:00Z",
  last_observed_at: "2026-11-09T00:00:00Z",
  method: "rules",
  evidence: [
    { quote: "Built with Cursor", url: "https://github.com/demo/garden-notes" },
  ],
  manual_override: false,
};
const json = (data: unknown, status = 200) =>
  Promise.resolve(
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
function setup(
  path: string,
  handler?: (
    url: string,
    options?: RequestInit,
  ) => ReturnType<typeof json> | undefined,
) {
  const mock = vi.fn(
    (url: string, options?: RequestInit) =>
      handler?.(url, options) ??
      (url.endsWith("/meta")
        ? json(meta)
        : url.includes("/apps?")
          ? json({ items: [app], total: 1, page: 1, page_size: 12, meta })
          : json({ items: [] })),
  );
  vi.stubGlobal("fetch", mock);
  render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return mock;
}
beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});
describe("metric semantics", () => {
  it("treats naive API timestamps as UTC before displaying Shanghai time", () => {
    expect(date("2026-11-09T07:44:00", true)).toContain("15:44");
    expect(date("2026-11-09T07:44:00Z", true)).toContain("15:44");
    expect(date("2026-11-09T15:44:00+08:00", true)).toContain("15:44");
  });
  it("shows missing growth as insufficient history, and keeps negative growth", () => {
    const { rerender } = render(<Growth value={null} />);
    expect(screen.getByText("历史不足")).toBeInTheDocument();
    expect(screen.queryByText("+0")).not.toBeInTheDocument();
    rerender(<Growth value={-4} />);
    expect(screen.getByText("-4")).toBeInTheDocument();
  });
});
describe("application discovery", () => {
  it("renders API projects and marks the workspace as demo", async () => {
    setup("/apps");
    expect(await screen.findByText("Garden Notes")).toBeInTheDocument();
    expect(
      screen.getByText(/所有项目及趋势均为独立模拟数据/),
    ).toBeInTheDocument();
    expect(screen.getByText("历史不足")).toBeInTheDocument();
  });
  it("passes search, category and review filters to the backend", async () => {
    const mock = setup("/apps");
    await screen.findByText("Garden Notes");
    fireEvent.change(screen.getByLabelText("搜索应用"), {
      target: { value: "notes" },
    });
    fireEvent.click(screen.getByRole("button", { name: "搜索" }));
    await waitFor(() =>
      expect(mock.mock.calls.some(([u]) => u.includes("q=notes"))).toBe(true),
    );
    fireEvent.change(screen.getByLabelText("应用类别"), {
      target: { value: "效率工具" },
    });
    await waitFor(() =>
      expect(mock.mock.calls.some(([u]) => u.includes("category="))).toBe(true),
    );
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() =>
      expect(
        mock.mock.calls.some(([u]) => u.includes("eligible_only=false")),
      ).toBe(true),
    );
  });
  it("exposes retry after an API failure and recovers", async () => {
    let fail = true;
    setup("/apps", (url) =>
      url.includes("/apps?")
        ? fail
          ? json({ detail: "采集暂不可用" }, 503)
          : json({ items: [app], total: 1, page: 1, page_size: 12, meta })
        : undefined,
    );
    expect(await screen.findByText("采集暂不可用")).toBeInTheDocument();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    expect(await screen.findByText("Garden Notes")).toBeInTheDocument();
  });
  it("exports using the same active filters", async () => {
    setup("/apps?tool=Cursor&eligible_only=false");
    await screen.findByText("Garden Notes");
    const href = screen
      .getByRole("link", { name: "导出 CSV" })
      .getAttribute("href");
    expect(href).toContain("tool=Cursor");
    expect(href).toContain("eligible_only=false");
  });
});
describe("human correction", () => {
  it("submits edited classification and preserves evidence", async () => {
    const mock = setup("/apps/1", (url, options) =>
      url.endsWith("/apps/1")
        ? json({
            app,
            history: [],
            discussions: [],
            classification: {
              method: "rules",
              model: "",
              prompt_version: "v1",
              classified_at: app.first_seen_at,
              manual_override: false,
              evidence: app.evidence,
            },
          })
        : url.endsWith("/classification") && options?.method === "PATCH"
          ? json({ ...app, manual_override: true })
          : undefined,
    );
    await screen.findByRole("button", { name: "修正分类" });
    fireEvent.click(screen.getByRole("button", { name: "修正分类" }));
    fireEvent.change(screen.getByLabelText("应用类别"), {
      target: { value: "教育学习" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存人工修正" }));
    await waitFor(() =>
      expect(
        mock.mock.calls.some(
          ([u, o]) => u.endsWith("/classification") && o?.method === "PATCH",
        ),
      ).toBe(true),
    );
    const body = JSON.parse(
      mock.mock.calls.find(
        ([u, o]) => u.endsWith("/classification") && o?.method === "PATCH",
      )![1]!.body as string,
    );
    expect(body.category).toBe("教育学习");
    expect(body.evidence[0].quote).toBe("Built with Cursor");
  });
});
describe("report generation", () => {
  it("queues a report instead of inventing a local report", async () => {
    const mock = setup("/reports", (url, opts) =>
      url.endsWith("/reports") && opts?.method === "POST"
        ? json({ id: 4, kind: "report", status: "queued" })
        : undefined,
    );
    await screen.findByText("你的第一份趋势观察，等待生成。");
    fireEvent.click(screen.getByRole("button", { name: "生成最新周报" }));
    await waitFor(() =>
      expect(
        mock.mock.calls.some(
          ([u, o]) => u.endsWith("/reports") && o?.method === "POST",
        ),
      ).toBe(true),
    );
    expect(
      await screen.findByRole("button", { name: "正在生成报告…" }),
    ).toBeDisabled();
  });
});
