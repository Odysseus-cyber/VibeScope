import { useCallback, useEffect, useState } from "react";
export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : `请求失败（${res.status}），请稍后重试。`,
    );
  }
  return res.json();
}
export function useApi<T>(path: string, interval = 0) {
  const [data, setData] = useState<T>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const reload = useCallback(() => setRevision((v) => v + 1), []);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    request<T>(path, { signal: controller.signal })
      .then((result) => {
        setData(result);
        setLoading(false);
      })
      .catch((e) => {
        if (e.name !== "AbortError") {
          setError(e.message);
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [path, revision]);
  useEffect(() => {
    if (!interval) return;
    const id = window.setInterval(reload, interval);
    return () => window.clearInterval(id);
  }, [interval, reload]);
  return { data, error, loading, reload };
}
export const num = (n: number | undefined | null) =>
  n == null ? "—" : new Intl.NumberFormat("zh-CN").format(n);
export const compact = (n: number) =>
  n >= 10000 ? `${(n / 10000).toFixed(1)}万` : num(n);
const utcTimestamp = (value: string) =>
  /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(value) &&
  !/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value)
    ? `${value.replace(" ", "T")}Z`
    : value;
export const date = (value?: string | null, time = false) =>
  value
    ? new Date(utcTimestamp(value)).toLocaleString("zh-CN", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        ...(time ? { hour: "2-digit", minute: "2-digit" } : {}),
      })
    : "暂无记录";
export const growthText = (n: number | null) =>
  n == null ? "历史不足" : `${n > 0 ? "+" : ""}${num(n)}`;
export const kindLabel: Record<string, string> = {
  application: "应用作品",
  developer_tool: "开发工具",
  resource: "模板 / 资源",
};
export const evidenceLabel: Record<string, string> = {
  explicit: "明确声明",
  weak: "待核验",
  unknown: "未知",
};
export const methodLabel: Record<string, string> = {
  rules: "规则分类",
  llm: "AI 模型",
  manual: "人工核验",
  demo: "演示数据",
  template: "统计摘要",
};
export const jobLabel: Record<string, string> = {
  sync: "完整同步",
  github: "GitHub 采集",
  hn: "HN 采集",
  classify: "应用分类",
  warehouse: "数仓构建",
  report: "趋势周报",
};
export const statusLabel: Record<string, string> = {
  queued: "等待执行",
  running: "执行中",
  succeeded: "已完成",
  partial: "部分完成",
  failed: "失败",
  pass: "通过",
  warn: "需关注",
  fail: "未通过",
  complete: "完整",
  limited: "覆盖有限",
  ok: "正常",
};
