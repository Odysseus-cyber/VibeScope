export type Evidence = { quote: string; url: string };
export type AppItem = {
  id: number;
  name: string;
  full_name: string;
  description: string;
  summary: string;
  url: string;
  homepage: string | null;
  category: string;
  tools: string[];
  language: string | null;
  kind: string;
  evidence_level: string;
  stars: number;
  forks: number;
  growth_7d: number | null;
  growth_30d: number | null;
  created_at: string;
  first_seen_at: string;
  last_observed_at: string;
  method: string;
  evidence: Evidence[];
  manual_override: boolean;
};
export type Meta = {
  mode: "demo" | "live";
  as_of: string;
  last_updated: string | null;
  llm_enabled: boolean;
  categories: string[];
  tools: string[];
  languages: string[];
};
export type Distribution = { name: string; count: number; percentage: number };
export type Daily = {
  date: string;
  stars: number | null;
  apps?: number;
  forks?: number | null;
  growth: number | null;
};
export type Overview = {
  meta: Meta;
  kpis: {
    tracked: number;
    eligible: number;
    new_created: number;
    new_discovered: number;
    stars: number;
    growth_7d: number | null;
    classified: number;
    coverage_days: number;
  };
  categories: Distribution[];
  tools: Distribution[];
  daily: Daily[];
  leaders: AppItem[];
};
export type AppList = {
  items: AppItem[];
  total: number;
  page: number;
  page_size: number;
  meta: Meta;
};
export type AppDetail = {
  app: AppItem;
  history: Daily[];
  discussions: {
    id: number;
    title: string;
    url: string;
    score: number;
    comments: number;
    posted_at: string;
  }[];
  classification: {
    method: string;
    model: string;
    prompt_version: string;
    classified_at: string;
    manual_override: boolean;
    evidence: Evidence[];
  };
};
export type Report = {
  id: string;
  title: string;
  period_start: string;
  period_end: string;
  body: string;
  method: string;
  created_at: string;
  facts: Record<string, unknown>;
  sources: { title: string; url: string }[];
  mode: string;
};
export type Job = {
  id: string;
  kind: string;
  status: string;
  progress: number;
  processed: number;
  errors: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  summary: Record<string, unknown> | string | null;
};
export type Quality = {
  meta: Meta;
  checks: {
    name: string;
    status: string;
    value: string | number;
    detail: string;
  }[];
  layers: { name: string; rows: number }[];
  coverage: {
    source: string;
    observed_at: string;
    status: string;
    detail: string | Record<string, unknown>;
  }[];
};
