import { createContext, useContext, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  Compass,
  Database,
  Download,
  FileText,
  Filter,
  GitFork,
  Github,
  LayoutDashboard,
  LoaderCircle,
  Menu,
  Plus,
  RefreshCw,
  Search,
  Settings2,
  Sparkles,
  Star,
  TrendingUp,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import {
  date,
  evidenceLabel,
  jobLabel,
  kindLabel,
  methodLabel,
  num,
  request,
  statusLabel,
  useApi,
} from "./api";
import {
  AppCard,
  AppIcon,
  AppTable,
  DistributionChart,
  Growth,
  MoreLink,
  OutLink,
  SectionTitle,
  Status,
  TrendChart,
} from "./components";
import type {
  AppDetail,
  AppItem,
  AppList,
  Job,
  Meta,
  Overview,
  Quality,
  Report,
} from "./types";
const MetaContext = createContext<Meta | undefined>(undefined);
const ToastContext = createContext<(message: string) => void>(() => {});
const links = [
  { to: "/", label: "趋势总览", icon: LayoutDashboard },
  { to: "/apps", label: "应用发现", icon: Compass },
  { to: "/reports", label: "AI 趋势周报", icon: FileText },
  { to: "/workbench", label: "数据工作台", icon: Database },
];
export default function App() {
  const meta = useApi<Meta>("/meta", 30000);
  const [toast, setToast] = useState("");
  const [menu, setMenu] = useState(false);
  const location = useLocation();
  useEffect(() => {
    setMenu(false);
    window.scrollTo(0, 0);
  }, [location.pathname]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 6000);
    return () => clearTimeout(timer);
  }, [toast]);
  const current = links.find((x) =>
    x.to === "/"
      ? location.pathname === "/"
      : location.pathname.startsWith(x.to),
  );
  return (
    <MetaContext.Provider value={meta.data}>
      <ToastContext.Provider value={setToast}>
        <div className="shell">
          {menu && (
            <button
              className="sidebar-backdrop"
              aria-label="关闭导航"
              onClick={() => setMenu(false)}
            />
          )}
          <aside className={`sidebar ${menu ? "open" : ""}`}>
            <Link to="/" className="brand">
              <span className="brand-mark">
                <Activity size={23} />
              </span>
              <span>
                VibeScope<small>AI 应用趋势观察站</small>
              </span>
            </Link>
            <div className="sidebar-label">WORKSPACE</div>
            <nav>
              {links.map((x) => (
                <NavLink end={x.to === "/"} key={x.to} to={x.to}>
                  <x.icon size={18} />
                  <span>{x.label}</span>
                  {x.to === "/reports" && <span className="nav-ai">AI</span>}
                </NavLink>
              ))}
            </nav>
            <div className="sidebar-note">
              <div className="note-orbit">
                <Sparkles size={18} />
              </div>
              <strong>从灵感，看到趋势。</strong>
              <p>
                发现用 AI 创造的应用，
                <br />
                让每个洞察都有数据支撑。
              </p>
              <Link to="/workbench">
                了解数据链路 <ArrowUpRight size={13} />
              </Link>
            </div>
            <div className="sidebar-bottom">
              <div className="system-dot" />
              <span>本地独立工作区</span>
              <span className="version">v1.0</span>
            </div>
          </aside>
          <div className="main-shell">
            <header className="topbar">
              <div className="breadcrumb">
                <button
                  className="icon-button mobile-menu"
                  aria-label="展开导航"
                  onClick={() => setMenu(true)}
                >
                  <Menu size={20} />
                </button>
                <span>工作区</span>
                <ChevronRight size={13} />
                <strong>{current?.label || "应用详情"}</strong>
              </div>
              <div className="topbar-right">
                <span className="source-status">
                  <span className="system-dot" />
                  GitHub <span className="divider">/</span> Hacker News
                </span>
                <span className="local-badge">LOCAL</span>
                <div className="avatar">VS</div>
              </div>
            </header>
            <main>
              <div
                className={`mode-banner ${meta.data?.mode === "live" ? "live" : ""}`}
              >
                <span>
                  <span className="mode-badge">
                    {meta.data?.mode === "demo"
                      ? "DEMO"
                      : meta.data?.mode === "live"
                        ? "LIVE"
                        : "DATA"}
                  </span>
                  {meta.data?.mode === "demo"
                    ? "当前为演示工作区 · 所有项目及趋势均为独立模拟数据"
                    : meta.data?.mode === "live"
                      ? "真实数据工作区 · 统计范围为已收录公开项目"
                      : "正在连接数据工作区…"}
                </span>
                <Link to="/workbench">
                  数据说明 <ArrowUpRight size={12} />
                </Link>
              </div>
              {meta.error && (
                <div className="inline-error" role="alert">
                  数据服务连接失败：{meta.error}
                  <button onClick={meta.reload}>重试</button>
                </div>
              )}
              <Routes>
                <Route path="/" element={<OverviewPage />} />
                <Route path="/apps" element={<DiscoverPage />} />
                <Route path="/apps/:id" element={<DetailPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/workbench" element={<WorkbenchPage />} />
                <Route
                  path="*"
                  element={
                    <div className="state">
                      <h1>页面不存在</h1>
                      <Link to="/">返回总览</Link>
                    </div>
                  }
                />
              </Routes>
              <footer>
                <span>
                  VibeScope <span className="footer-dot">·</span>{" "}
                  发现应用，理解趋势
                </span>
                <span>UTC 统计日 · 页面时间为 Asia/Shanghai</span>
              </footer>
            </main>
          </div>
          {toast && (
            <div className="toast" role="status">
              <CheckCircle2 size={18} />
              <span>{toast}</span>
              <button
                className="icon-button"
                aria-label="关闭通知"
                onClick={() => setToast("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
        </div>
      </ToastContext.Provider>
    </MetaContext.Provider>
  );
}
function PageHeading({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      <div className="heading-actions">{children}</div>
    </div>
  );
}
function OverviewPage() {
  const [windowDays, setWindowDays] = useState(30);
  const { data, loading, error, reload } = useApi<Overview>(
    `/overview?window=${windowDays}`,
  );
  const navigate = useNavigate();
  return (
    <>
      <PageHeading
        eyebrow="THE SIGNAL, BEYOND THE NOISE"
        title="每一个新应用，都是下一个信号。"
        description="追踪 AI 辅助开发的作品，发现值得关注的产品与方向。"
      >
        <div className="segmented" aria-label="统计窗口">
          {[7, 30, 90].map((n) => (
            <button
              key={n}
              className={n === windowDays ? "active" : ""}
              onClick={() => setWindowDays(n)}
            >
              {n} 天
            </button>
          ))}
        </div>
        <button
          className="icon-button outline"
          aria-label="刷新数据"
          onClick={reload}
        >
          <RefreshCw size={16} />
        </button>
      </PageHeading>
      <Status loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <section className="hero">
              <div className="hero-copy">
                <span className="hero-eyebrow">
                  <span />
                  VIBE CODING OBSERVATORY
                </span>
                <h2>
                  灵感正在发生。
                  <br />
                  <span>下一波应用，先看见。</span>
                </h2>
                <p>从公开项目到可追溯的趋势，观察 AI 如何改变创造。</p>
                <Link to="/apps" className="hero-button">
                  探索应用图谱 <ArrowRight size={15} />
                </Link>
              </div>
              <div className="hero-visual" aria-hidden="true">
                <div className="orbit orbit-1" />
                <div className="orbit orbit-2" />
                <div className="orbit orbit-3" />
                <div className="orbit-core">
                  <Activity size={40} />
                </div>
                <div className="orbit-chip chip-1">
                  <Sparkles size={15} /> AI × CREATIVITY
                </div>
                <div className="orbit-chip chip-2">
                  <span className="pulse-dot" />
                  {num(data.kpis.eligible)} 个应用信号
                </div>
                <div className="orbit-chip chip-3">
                  <TrendingUp size={15} /> FOLLOW THE SIGNAL
                </div>
                <div className="orbit-point p1" />
                <div className="orbit-point p2" />
              </div>
            </section>
            <div className="metric-grid">
              <Metric
                label="收录应用项目"
                value={num(data.kpis.tracked)}
                icon={<Compass size={18} />}
                note={`${num(data.kpis.eligible)} 个应用有明确开发声明`}
              />
              <Metric
                label={`近 ${windowDays} 天新创建`}
                value={num(data.kpis.new_created)}
                icon={<Plus size={18} />}
                note={`同期首次收录 ${num(data.kpis.new_discovered)} 个项目`}
              />
              <Metric
                label="应用关注总量"
                value={num(data.kpis.stars)}
                icon={<Star size={18} />}
                note={
                  <>
                    <Growth value={data.kpis.growth_7d} />{" "}
                    <span>过去 7 天净增</span>
                  </>
                }
              />
              <Metric
                label="累计观测"
                value={num(data.kpis.coverage_days)}
                suffix="天"
                icon={<Activity size={18} />}
                note={`已分类 ${num(data.kpis.classified)} 个项目`}
              />
            </div>
            <div className="chart-grid">
              <section className="panel">
                <SectionTitle
                  title="关注度的流动"
                  eyebrow="ATTENTION OVER TIME"
                >
                  <span className="chart-key">
                    <span />
                    累计 Stars
                  </span>
                </SectionTitle>
                {data.daily.length ? (
                  <TrendChart data={data.daily} />
                ) : (
                  <div className="empty-small">
                    采集完成后，趋势将在这里逐日积累。
                  </div>
                )}
                <div className="panel-foot">
                  仅对观测样本统计 · 缺失历史不补零
                </div>
              </section>
              <section className="panel">
                <SectionTitle
                  title="灵感流向哪里"
                  eyebrow="APPLICATION LANDSCAPE"
                />
                {data.categories.length ? (
                  <DistributionChart
                    items={data.categories}
                    onSelect={(name) =>
                      navigate(`/apps?category=${encodeURIComponent(name)}`)
                    }
                  />
                ) : (
                  <div className="empty-small">暂无有明确声明的应用</div>
                )}
                <div className="panel-foot">
                  分母：{num(data.kpis.eligible)} 个有明确声明的应用 ·
                  点击类别查看
                </div>
              </section>
            </div>
            <section className="panel">
              <SectionTitle title="正在获得关注" eyebrow="RISING APPLICATIONS">
                <MoreLink to="/apps">查看全部应用</MoreLink>
              </SectionTitle>
              <Status empty={!data.leaders.length}>
                <AppTable apps={data.leaders.slice(0, 5)} />
              </Status>
            </section>
            <div className="bottom-grid">
              <section className="panel">
                <SectionTitle title="创作工具分布" eyebrow="BUILT WITH AI" />
                <div className="tool-bars">
                  {data.tools.slice(0, 6).map((item, i) => (
                    <button
                      key={item.name}
                      onClick={() =>
                        navigate(`/apps?tool=${encodeURIComponent(item.name)}`)
                      }
                    >
                      <span className="tool-index">0{i + 1}</span>
                      <span className="tool-name">{item.name}</span>
                      <span className="bar-track">
                        <span
                          style={{
                            width: `${Math.min(item.percentage, 100)}%`,
                          }}
                        />
                      </span>
                      <strong>{item.percentage.toFixed(1)}%</strong>
                      <small>{item.count} 个</small>
                    </button>
                  ))}
                </div>
                <div className="panel-foot">
                  一个应用可使用多个工具，占比之和可能超过 100%。未知单列。
                </div>
              </section>
              <section className="report-promo">
                <span className="eyebrow">YOUR WEEKLY PERSPECTIVE</span>
                <div className="promo-icon">
                  <BookOpen size={25} />
                  <Sparkles size={14} />
                </div>
                <h2>把数据，变成洞察。</h2>
                <p>
                  增长项目、赛道变化、代表案例。
                  <br />让 AI 帮你整理这一周的观察。
                </p>
                <Link className="button primary" to="/reports">
                  阅读趋势周报 <ArrowRight size={15} />
                </Link>
                <small>先计算事实，再生成解读。每条数据都可追溯。</small>
              </section>
            </div>
            <div className="freshness">
              <span className="system-dot" />
              最近更新：{date(data.meta.last_updated, true)} <span>·</span>{" "}
              观测日期 {data.meta.as_of}
            </div>
          </>
        )}
      </Status>
    </>
  );
}
function Metric({
  label,
  value,
  suffix,
  icon,
  note,
}: {
  label: string;
  value: string;
  suffix?: string;
  icon: ReactNode;
  note: ReactNode;
}) {
  return (
    <div className="metric">
      <div className="metric-label">
        {label}
        <span>{icon}</span>
      </div>
      <div className="metric-value">
        {value}
        <small>{suffix}</small>
      </div>
      <div className="metric-note">{note}</div>
    </div>
  );
}
function DiscoverPage() {
  const meta = useContext(MetaContext);
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState(params.get("q") || "");
  const [view, setView] = useState("cards");
  const query = new URLSearchParams(params);
  query.set("page_size", view === "cards" ? "12" : "20");
  const { data, loading, error, reload } = useApi<AppList>(`/apps?${query}`);
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next);
  };
  const searchSubmit = (e: FormEvent) => {
    e.preventDefault();
    set("q", search.trim());
  };
  return (
    <>
      <PageHeading
        eyebrow="THE APPLICATION INDEX"
        title="发现值得关注的创造。"
        description="每个作品背后，是一个用 AI 实现的想法。"
      >
        <a
          className="button outline"
          href={`/api/v1/apps/export.csv?${query}`}
          download
        >
          <Download size={15} />
          导出 CSV
        </a>
      </PageHeading>
      <section className="panel discovery-controls">
        <div className="filter-top">
          <form className="search-box" onSubmit={searchSubmit}>
            <Search size={18} />
            <input
              aria-label="搜索应用"
              placeholder="搜索应用名称、用途或关键词…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button type="submit">搜索</button>
          </form>
          <div className="segmented view-switch">
            <button
              onClick={() => setView("cards")}
              className={view === "cards" ? "active" : ""}
            >
              <LayoutDashboard size={15} />
              卡片
            </button>
            <button
              onClick={() => setView("table")}
              className={view === "table" ? "active" : ""}
            >
              <Menu size={16} />
              榜单
            </button>
          </div>
        </div>
        <div className="filter-row">
          <Filter size={15} />
          <Select
            label="应用类别"
            value={params.get("category") || ""}
            options={meta?.categories || []}
            onChange={(v) => set("category", v)}
          />
          <Select
            label="开发工具"
            value={params.get("tool") || ""}
            options={meta?.tools || []}
            onChange={(v) => set("tool", v)}
          />
          <Select
            label="开发语言"
            value={params.get("language") || ""}
            options={meta?.languages || []}
            onChange={(v) => set("language", v)}
          />
          <label className="date-filter">
            创建于
            <input
              aria-label="创建时间下限"
              type="date"
              value={params.get("created_after") || ""}
              onChange={(e) => set("created_after", e.target.value)}
            />
            之后
          </label>
          <button
            className="text-button"
            onClick={() => {
              setParams({});
              setSearch("");
            }}
          >
            清除筛选
          </button>
        </div>
        <div className="filter-bottom">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={params.get("eligible_only") === "false"}
              onChange={(e) =>
                set("eligible_only", e.target.checked ? "false" : "true")
              }
            />
            包含待核验项目、开发工具与资源
          </label>
          <select
            aria-label="排序方式"
            value={params.get("sort") || "growth_7d"}
            onChange={(e) => set("sort", e.target.value)}
          >
            <option value="growth_7d">7 天净增优先</option>
            <option value="stars">Stars 总量优先</option>
            <option value="newest">最近创建优先</option>
          </select>
        </div>
      </section>
      <div className="result-summary">
        <span>
          已发现 <strong>{num(data?.total)}</strong> 个项目
        </span>
        <span>7 天净增仅在历史完整时计算</span>
      </div>
      <Status
        loading={loading}
        error={error}
        empty={data?.items.length === 0}
        onRetry={reload}
      >
        {data &&
          (view === "cards" ? (
            <div className="app-grid">
              {data.items.map((app) => (
                <AppCard key={app.id} app={app} />
              ))}
            </div>
          ) : (
            <section className="panel">
              <AppTable apps={data.items} />
            </section>
          ))}
      </Status>
      {data && data.total > data.page_size && (
        <div className="pagination">
          <button
            className="button outline"
            disabled={data.page <= 1}
            onClick={() => set("page", String(data.page - 1))}
          >
            <ChevronLeft size={15} />
            上一页
          </button>
          <span>
            第 {data.page} / {Math.ceil(data.total / data.page_size)} 页
          </span>
          <button
            className="button outline"
            disabled={data.page * data.page_size >= data.total}
            onClick={() => set("page", String(data.page + 1))}
          >
            下一页
            <ChevronRight size={15} />
          </button>
        </div>
      )}
    </>
  );
}
function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="filter-select">
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">全部{label}</option>
        {options.map((x) => (
          <option key={x} value={x}>
            {x}
          </option>
        ))}
      </select>
      <ChevronDown size={13} />
    </div>
  );
}
function DetailPage() {
  const { id } = useParams();
  const { data, loading, error, reload } = useApi<AppDetail>(`/apps/${id}`);
  const [editing, setEditing] = useState(false);
  return (
    <>
      <Link className="back-link" to="/apps">
        <ArrowLeft size={15} />
        返回应用发现
      </Link>
      <Status loading={loading} error={error} onRetry={reload}>
        {data && (
          <>
            <div className="detail-heading">
              <AppIcon app={data.app} />
              <div>
                <div className="detail-tags">
                  <span className="category-tag">{data.app.category}</span>
                  <span className="muted">{kindLabel[data.app.kind]}</span>
                </div>
                <h1>{data.app.name}</h1>
                <p>{data.app.full_name}</p>
              </div>
              <a
                className="button primary"
                href={data.app.url}
                target="_blank"
                rel="noreferrer"
              >
                <Github size={16} />
                查看项目
                <ArrowUpRight size={15} />
              </a>
            </div>
            <div className="detail-intro">
              {data.app.summary || data.app.description}
            </div>
            <div className="metric-grid">
              <Metric
                label="当前 Stars"
                value={num(data.app.stars)}
                icon={<Star size={18} />}
                note="公开仓库关注总量"
              />
              <Metric
                label="当前 Forks"
                value={num(data.app.forks)}
                icon={<GitFork size={18} />}
                note="公开仓库分叉数量"
              />
              <Metric
                label="7 天净增"
                value={
                  data.app.growth_7d == null
                    ? "—"
                    : `${data.app.growth_7d > 0 ? "+" : ""}${num(data.app.growth_7d)}`
                }
                icon={<TrendingUp size={18} />}
                note={
                  data.app.growth_7d == null
                    ? "历史不足，暂不计算"
                    : "由窗口两端实际快照计算"
                }
              />
              <Metric
                label="30 天净增"
                value={
                  data.app.growth_30d == null
                    ? "—"
                    : `${data.app.growth_30d > 0 ? "+" : ""}${num(data.app.growth_30d)}`
                }
                icon={<Activity size={18} />}
                note={
                  data.app.growth_30d == null
                    ? "历史不足，暂不计算"
                    : "允许出现负增长"
                }
              />
            </div>
            <div className="detail-grid">
              <div className="stack">
                <section className="panel">
                  <SectionTitle title="关注度轨迹" eyebrow="OBSERVED HISTORY" />
                  {data.history.length ? (
                    <TrendChart data={data.history} />
                  ) : (
                    <div className="empty-small">尚无观测快照</div>
                  )}
                </section>
                <section className="panel">
                  <SectionTitle
                    title="AI 开发证据"
                    eyebrow="EVIDENCE, NOT ASSUMPTION"
                  >
                    <span
                      className={`evidence ${data.app.evidence_level === "explicit" ? "verified" : ""}`}
                    >
                      {evidenceLabel[data.app.evidence_level]}
                    </span>
                  </SectionTitle>
                  {data.app.evidence.length ? (
                    data.app.evidence.map((e, i) => (
                      <blockquote className="evidence-quote" key={i}>
                        <p>{e.quote}</p>
                        <OutLink url={e.url}>查看原文</OutLink>
                      </blockquote>
                    ))
                  ) : (
                    <div className="empty-small">
                      暂无明确声明，不能仅凭项目调用 AI 判断开发方式。
                    </div>
                  )}
                  <div className="evidence-meta">
                    <span>
                      {methodLabel[data.classification.method] ||
                        data.classification.method}
                    </span>
                    <span>{data.classification.model || "未配置模型"}</span>
                    <span>
                      提示版本 {data.classification.prompt_version || "—"}
                    </span>
                    <span>{date(data.classification.classified_at, true)}</span>
                  </div>
                </section>
                <section className="panel">
                  <SectionTitle
                    title="社区正在讨论"
                    eyebrow="HACKER NEWS SIGNALS"
                  />
                  {data.discussions.length ? (
                    data.discussions.map((d) => (
                      <div className="discussion" key={d.id}>
                        <span className="hn-icon">Y</span>
                        <div>
                          <OutLink url={d.url}>{d.title}</OutLink>
                          <small>
                            {d.score} 分 · {d.comments} 条评论 ·{" "}
                            {date(d.posted_at)}
                          </small>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="empty-small">
                      暂未发现可通过仓库链接明确关联的讨论。
                    </div>
                  )}
                </section>
              </div>
              <aside className="stack">
                <section className="panel app-facts">
                  <SectionTitle title="项目档案" />
                  <dl>
                    <dt>开发语言</dt>
                    <dd>{data.app.language || "未知"}</dd>
                    <dt>AI 开发工具</dt>
                    <dd className="app-tags">
                      {data.app.tools.length
                        ? data.app.tools.map((t) => <span key={t}>{t}</span>)
                        : "未知"}
                    </dd>
                    <dt>创建时间</dt>
                    <dd>{date(data.app.created_at)}</dd>
                    <dt>首次收录</dt>
                    <dd>{date(data.app.first_seen_at)}</dd>
                    <dt>最后观测</dt>
                    <dd>{date(data.app.last_observed_at, true)}</dd>
                    {data.app.homepage && (
                      <>
                        <dt>应用网站</dt>
                        <dd>
                          <OutLink url={data.app.homepage}>访问应用</OutLink>
                        </dd>
                      </>
                    )}
                  </dl>
                  <button
                    className="button outline full"
                    onClick={() => setEditing(true)}
                  >
                    <Settings2 size={15} />
                    修正分类
                  </button>
                  {data.app.manual_override && (
                    <p className="small-note">
                      人工修正已锁定，不会被自动分类覆盖。
                    </p>
                  )}
                </section>
                <div className="context-note">
                  <CircleHelp size={18} />
                  <strong>关于这份档案</strong>
                  <p>
                    “用 AI 开发”与“提供 AI
                    功能”是两件事。我们保留作者声明与原始来源，让分类可以复核。
                  </p>
                </div>
              </aside>
            </div>
            {editing && (
              <ClassificationModal
                app={data.app}
                onClose={() => setEditing(false)}
                onSaved={() => {
                  setEditing(false);
                  reload();
                }}
              />
            )}
          </>
        )}
      </Status>
    </>
  );
}
function ClassificationModal({
  app,
  onClose,
  onSaved,
}: {
  app: AppItem;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [category, setCategory] = useState(app.category);
  const [kind, setKind] = useState(app.kind);
  const [level, setLevel] = useState(app.evidence_level);
  const [tools, setTools] = useState(app.tools.join(", "));
  const [summary, setSummary] = useState(app.summary);
  const [evidence, setEvidence] = useState(app.evidence);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const toast = useContext(ToastContext);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await request(`/apps/${app.id}/classification`, {
        method: "PATCH",
        body: JSON.stringify({
          category,
          kind,
          evidence_level: level,
          tools: tools
            .split(/[,，]/)
            .map((t) => t.trim())
            .filter(Boolean),
          summary,
          evidence: evidence.filter((e) => e.quote.trim() && e.url.trim()),
        }),
      });
      toast("分类已保存，后续自动处理将保留人工修正。");
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };
  return (
    <div className="modal-backdrop">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="edit-title"
      >
        <div className="modal-header">
          <div>
            <span className="eyebrow">HUMAN REVIEW</span>
            <h2 id="edit-title">修正应用分类</h2>
          </div>
          <button
            className="icon-button"
            aria-label="关闭对话框"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </div>
        <form onSubmit={save}>
          <label>
            应用类别
            <input
              required
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            />
          </label>
          <div className="form-two">
            <label>
              项目类型
              <select value={kind} onChange={(e) => setKind(e.target.value)}>
                {Object.entries(kindLabel).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
            <label>
              证据等级
              <select value={level} onChange={(e) => setLevel(e.target.value)}>
                {Object.entries(evidenceLabel).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label>
            开发工具
            <input
              value={tools}
              onChange={(e) => setTools(e.target.value)}
              placeholder="用逗号分隔，如 Cursor, Claude Code"
            />
          </label>
          <label>
            应用简介
            <textarea
              rows={3}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
            />
          </label>
          <div className="form-label">
            来源证据{" "}
            <button
              type="button"
              className="text-button"
              onClick={() => setEvidence([...evidence, { quote: "", url: "" }])}
            >
              ＋ 添加证据
            </button>
          </div>
          {evidence.map((ev, i) => (
            <div className="evidence-editor" key={i}>
              <textarea
                aria-label={`证据片段 ${i + 1}`}
                value={ev.quote}
                onChange={(e) =>
                  setEvidence(
                    evidence.map((v, j) =>
                      i === j ? { ...v, quote: e.target.value } : v,
                    ),
                  )
                }
                placeholder="原文片段"
              />
              <input
                aria-label={`证据链接 ${i + 1}`}
                type="url"
                value={ev.url}
                onChange={(e) =>
                  setEvidence(
                    evidence.map((v, j) =>
                      i === j ? { ...v, url: e.target.value } : v,
                    ),
                  )
                }
                placeholder="https://github.com/…"
              />
              <button
                type="button"
                className="text-button"
                onClick={() => setEvidence(evidence.filter((_, j) => j !== i))}
              >
                移除
              </button>
            </div>
          ))}
          {error && (
            <p role="alert" className="inline-error">
              {error}
            </p>
          )}
          <div className="modal-actions">
            <button type="button" className="button outline" onClick={onClose}>
              取消
            </button>
            <button className="button primary" disabled={saving}>
              {saving ? (
                <LoaderCircle className="spin" size={16} />
              ) : (
                <CheckCircle2 size={16} />
              )}
              保存人工修正
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
function ReportsPage() {
  const { data, loading, error, reload } = useApi<{ items: Report[] }>(
    "/reports",
  );
  const [selected, setSelected] = useState<string>();
  const [job, setJob] = useState<Job>();
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState("");
  const toast = useContext(ToastContext);
  const meta = useContext(MetaContext);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.status)) return;
    const id = setInterval(
      () =>
        request<{ items: Job[] }>("/jobs")
          .then((r) => {
            const current = r.items.find((j) => j.id === job.id);
            if (current) {
              setJob(current);
              if (["succeeded", "partial"].includes(current.status)) {
                reload();
                setSelected(undefined);
                toast("新的趋势报告已生成。");
              }
              if (current.status === "failed")
                setActionError(
                  current.error || "生成失败，请前往数据工作台查看。",
                );
            }
          })
          .catch((e) => setActionError(e.message)),
      2000,
    );
    return () => clearInterval(id);
  }, [job, reload, toast]);
  const generate = async () => {
    setSending(true);
    setActionError("");
    try {
      setJob(await request<Job>("/reports", { method: "POST", body: "{}" }));
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setSending(false);
    }
  };
  const report = data?.items.find((r) => r.id === selected) || data?.items[0];
  const busy = sending || (!!job && ["queued", "running"].includes(job.status));
  return (
    <>
      <PageHeading
        eyebrow="THE WEEKLY PERSPECTIVE"
        title="数据有变化，洞察有来处。"
        description="先用 SQL 计算事实，再将本周的信号整理成一份可读的报告。"
      >
        <button className="button primary" disabled={busy} onClick={generate}>
          {busy ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <Sparkles size={16} />
          )}{" "}
          {busy ? "正在生成报告…" : "生成最新周报"}
        </button>
      </PageHeading>
      <div className="report-mode">
        <Sparkles size={17} />
        <span>
          {meta?.llm_enabled
            ? "模型已连接 · 周报由实际指标与来源证据生成"
            : "当前使用统计摘要 · 配置模型 API 后可生成 AI 解读"}
        </span>
        <span className="pill">
          {meta?.llm_enabled ? "AI + SQL" : "SQL FIRST"}
        </span>
      </div>
      {actionError && (
        <div className="inline-error" role="alert">
          {actionError}
        </div>
      )}
      <Status loading={loading} error={error} onRetry={reload}>
        {!data?.items.length ? (
          <div className="report-empty">
            <BookOpen size={45} />
            <h2>你的第一份趋势观察，等待生成。</h2>
            <p>
              数据不足一周时，我们会生成“观察摘要”。
              <br />
              历史积累完成后，增长榜与周趋势将自然出现。
            </p>
            <button
              className="button primary"
              disabled={busy}
              onClick={generate}
            >
              <Sparkles size={16} />
              生成观察摘要
            </button>
          </div>
        ) : (
          <div className="reports-layout">
            <aside className="report-list">
              <span className="eyebrow">OBSERVATION ARCHIVE</span>
              {data.items.map((r) => (
                <button
                  key={r.id}
                  className={report?.id === r.id ? "active" : ""}
                  onClick={() => setSelected(r.id)}
                >
                  <span>
                    <FileText size={16} />
                    {date(r.created_at)}
                  </span>
                  <strong>{r.title}</strong>
                  <small>
                    {r.period_start} — {r.period_end}
                  </small>
                </button>
              ))}
            </aside>
            {report && (
              <article className="report-document">
                <div className="document-top">
                  <span className="eyebrow">VIBESCOPE / FIELD NOTES</span>
                  <span className="pill">
                    {report.mode === "demo" ? "模拟数据报告" : "真实观测"}
                  </span>
                </div>
                <h1>{report.title}</h1>
                <div className="report-byline">
                  <span>
                    {report.period_start} — {report.period_end}
                  </span>
                  <span>{methodLabel[report.method] || report.method}</span>
                  <span>{date(report.created_at, true)}</span>
                </div>
                <div className="markdown">
                  <ReactMarkdown>{report.body}</ReactMarkdown>
                </div>
                {report.sources.length > 0 && (
                  <div className="report-sources">
                    <span className="eyebrow">SOURCES & EVIDENCE</span>
                    <h3>沿着来源，继续探索</h3>
                    {report.sources.map((s, i) => (
                      <OutLink key={i} url={s.url}>
                        {s.title}
                      </OutLink>
                    ))}
                  </div>
                )}
                <div className="report-disclaimer">
                  统计范围为已收录项目，覆盖情况见数据工作台。解读是基于样本的观察，不代表全网趋势或因果结论。
                </div>
              </article>
            )}
          </div>
        )}
      </Status>
    </>
  );
}
function WorkbenchPage() {
  const quality = useApi<Quality>("/quality", 15000);
  const jobs = useApi<{ items: Job[] }>("/jobs", 4000);
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState("");
  const [expanded, setExpanded] = useState<string>();
  const toast = useContext(ToastContext);
  const run = async (kind: string, retry?: string) => {
    setSending(true);
    setActionError("");
    try {
      await request(retry ? `/jobs/${retry}/retry` : "/jobs", {
        method: "POST",
        body: JSON.stringify({ kind }),
      });
      toast("任务已加入队列，可在下方查看处理进度。");
      jobs.reload();
    } catch (e) {
      setActionError((e as Error).message);
    } finally {
      setSending(false);
    }
  };
  return (
    <>
      <PageHeading
        eyebrow="THE DATA BEHIND THE SIGNAL"
        title="从原始记录，到可信指标。"
        description="看见采集、转换与检查的全过程，让数据链路也成为作品的一部分。"
      >
        <button
          className="button primary"
          disabled={sending}
          onClick={() => run("sync")}
        >
          {sending ? (
            <LoaderCircle size={16} className="spin" />
          ) : (
            <RefreshCw size={16} />
          )}
          运行完整同步
        </button>
      </PageHeading>
      {actionError && (
        <div className="inline-error" role="alert">
          {actionError}
        </div>
      )}
      <section className="panel pipeline-panel">
        <SectionTitle title="一条可追溯的数据链路" eyebrow="PIPELINE OVERVIEW">
          <span className="pill">PYTHON + SQL</span>
        </SectionTitle>
        <div className="pipeline">
          {[
            "公开 API",
            "ODS 原始层",
            "DWD 明细层",
            "DWS 汇总层",
            "ADS 应用层",
          ].map((name, i) => (
            <div className="pipeline-stage" key={name}>
              <span className="stage-index">0{i + 1}</span>
              <Database size={23} />
              <strong>{name}</strong>
              <small>
                {i === 0
                  ? "GitHub · Hacker News"
                  : `${num(quality.data?.layers.find((l) => l.name.toLowerCase().includes(["", "ods", "dwd", "dws", "ads"][i]))?.rows)} 条记录`}
              </small>
              {i < 4 && <ArrowRight className="stage-arrow" size={16} />}
            </div>
          ))}
        </div>
        <div className="pipeline-actions">
          {["github", "hn", "classify", "warehouse"].map((k) => (
            <button
              key={k}
              disabled={sending}
              className="button outline"
              onClick={() => run(k)}
            >
              {jobLabel[k]}
              <ArrowUpRight size={14} />
            </button>
          ))}
        </div>
      </section>
      <Status
        loading={!quality.data && quality.loading}
        error={quality.error}
        onRetry={quality.reload}
      >
        {quality.data && (
          <>
            <section className="panel">
              <SectionTitle title="数据质量检查" eyebrow="TRUST IS MEASURABLE">
                <span className="muted">
                  最近更新 {date(quality.data.meta.last_updated, true)}
                </span>
              </SectionTitle>
              <div className="quality-checks">
                {quality.data.checks.map((c, i) => (
                  <div className="quality-check" key={i}>
                    <span className={`check-icon ${c.status}`}>
                      <CheckCircle2 size={18} />
                    </span>
                    <div>
                      <strong>{c.name}</strong>
                      <p>{c.detail}</p>
                    </div>
                    <div className="check-value">
                      <strong>{String(c.value)}</strong>
                      <span className={`status ${c.status}`}>
                        {statusLabel[c.status] || c.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
            <section className="panel">
              <SectionTitle title="数据来源与覆盖" eyebrow="SOURCE COVERAGE" />
              <div className="coverage-list">
                {quality.data.coverage.length ? (
                  quality.data.coverage.map((c, i) => (
                    <div key={i}>
                      <span className="source-icon">
                        {c.source.toLowerCase().includes("github") ? (
                          <Github size={20} />
                        ) : (
                          <Activity size={20} />
                        )}
                      </span>
                      <div>
                        <strong>{c.source}</strong>
                        <p>
                          {typeof c.detail === "string"
                            ? c.detail
                            : JSON.stringify(c.detail)}
                        </p>
                        <small>{date(c.observed_at, true)}</small>
                      </div>
                      <span className={`status ${c.status}`}>
                        {statusLabel[c.status] || c.status}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="empty-small">
                    尚未采集，首次任务完成后将记录来源覆盖。
                  </div>
                )}
              </div>
            </section>
          </>
        )}
      </Status>
      <section className="panel">
        <SectionTitle title="任务运行记录" eyebrow="RUN HISTORY">
          <button className="text-button" onClick={jobs.reload}>
            <RefreshCw size={13} />
            刷新
          </button>
        </SectionTitle>
        <Status
          loading={!jobs.data && jobs.loading}
          error={jobs.error}
          empty={jobs.data?.items.length === 0}
          onRetry={jobs.reload}
        >
          <div className="table-scroll">
            <table className="jobs-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>状态</th>
                  <th>进度</th>
                  <th>处理 / 错误</th>
                  <th>开始时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data?.items.map((j) => (
                  <JobRow
                    key={j.id}
                    job={j}
                    sending={sending}
                    expanded={expanded === j.id}
                    onExpand={() =>
                      setExpanded(expanded === j.id ? undefined : j.id)
                    }
                    onRetry={() => run(j.kind, j.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </Status>
      </section>
      <div className="context-note horizontal">
        <CircleHelp size={19} />
        <div>
          <strong>采集边界，也是数据的一部分。</strong>
          <p>
            GitHub 搜索按时间分段，保存截断与限流状态；HN
            从接入后持续积累。失败任务可重跑，唯一键保证项目与每日快照不重复。
          </p>
        </div>
      </div>
    </>
  );
}
function JobRow({
  job: j,
  sending,
  expanded,
  onExpand,
  onRetry,
}: {
  job: Job;
  sending: boolean;
  expanded: boolean;
  onExpand: () => void;
  onRetry: () => void;
}) {
  return (
    <>
      <tr>
        <td>
          <strong>{jobLabel[j.kind] || j.kind}</strong>
          <small>#{j.id}</small>
        </td>
        <td>
          <span className={`status ${j.status}`}>
            {j.status === "running" && (
              <LoaderCircle size={12} className="spin" />
            )}
            {statusLabel[j.status] || j.status}
          </span>
        </td>
        <td>
          <span className="job-progress">
            <span
              style={{ width: `${Math.min(100, Math.max(0, j.progress))}%` }}
            />
          </span>
          <small>{Math.round(j.progress)}%</small>
        </td>
        <td>
          {num(j.processed)} <span className="muted">/</span>{" "}
          <span className={j.errors ? "text-danger" : ""}>{num(j.errors)}</span>
        </td>
        <td>{date(j.started_at || j.created_at, true)}</td>
        <td>
          <div className="row-actions">
            <button className="text-button" onClick={onExpand}>
              {expanded ? "收起" : "详情"}
            </button>
            {["failed", "partial"].includes(j.status) && (
              <button
                className="text-button"
                disabled={sending}
                onClick={onRetry}
              >
                重跑
              </button>
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={6}>
            <div className="job-detail">
              {j.error && <p className="text-danger">{j.error}</p>}
              <pre>
                {typeof j.summary === "string"
                  ? j.summary
                  : JSON.stringify(
                      j.summary || { message: "暂无详细记录" },
                      null,
                      2,
                    )}
              </pre>
              <small>完成时间：{date(j.finished_at, true)}</small>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
