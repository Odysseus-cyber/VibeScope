import { useEffect, useRef } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import * as echarts from "echarts/core";
import { LineChart, PieChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
echarts.use([
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  SVGRenderer,
]);
import type { EChartsOption } from "echarts";
import {
  AlertCircle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ExternalLink,
  LoaderCircle,
  Search,
  Star,
} from "lucide-react";
import { compact, evidenceLabel, growthText, kindLabel } from "./api";
import type { AppItem, Daily, Distribution } from "./types";
export function Status({
  loading,
  error,
  empty,
  onRetry,
  children,
}: {
  loading?: boolean;
  error?: string;
  empty?: boolean;
  onRetry?: () => void;
  children: ReactNode;
}) {
  if (loading)
    return (
      <div className="state" role="status">
        <LoaderCircle size={26} className="spin" />
        <strong>正在读取观测数据</strong>
        <span>让每一个结论，都有迹可循。</span>
      </div>
    );
  if (error)
    return (
      <div className="state error" role="alert">
        <AlertCircle size={28} />
        <strong>暂时无法读取数据</strong>
        <span>{error}</span>
        <button className="button" onClick={onRetry}>
          重新加载
        </button>
      </div>
    );
  if (empty)
    return (
      <div className="state">
        <Search size={30} />
        <strong>这里还没有观测记录</strong>
        <span>试试调整筛选条件，或在数据工作台运行采集。</span>
      </div>
    );
  return <>{children}</>;
}
export function Chart({
  option,
  onClick,
  height = 270,
}: {
  option: EChartsOption;
  onClick?: (name: string) => void;
  height?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const chart = echarts.init(ref.current, undefined, { renderer: "svg" });
    chart.setOption(option);
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(ref.current);
    if (onClick) chart.on("click", (p: { name: string }) => onClick(p.name));
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [option, onClick]);
  return (
    <div
      ref={ref}
      role="img"
      aria-label="数据趋势图"
      style={{ height, width: "100%" }}
    />
  );
}
export function TrendChart({
  data,
  height = 270,
}: {
  data: Daily[];
  height?: number;
}) {
  return (
    <Chart
      height={height}
      option={{
        animationDuration: 450,
        tooltip: {
          trigger: "axis",
          backgroundColor: "#172d2c",
          borderWidth: 0,
          textStyle: { color: "#fff" },
          valueFormatter: (v) => String(v ?? "历史不足"),
        },
        grid: { left: 52, right: 20, top: 22, bottom: 32 },
        xAxis: {
          type: "category",
          boundaryGap: false,
          data: data.map((x) => x.date.slice(5)),
          axisLine: { lineStyle: { color: "#e9eeec" } },
          axisTick: { show: false },
          axisLabel: { color: "#94a29f", fontSize: 11 },
        },
        yAxis: {
          type: "value",
          splitLine: { lineStyle: { color: "#edf0ef", type: "dashed" } },
          axisLabel: { color: "#94a29f", fontSize: 11 },
        },
        series: [
          {
            name: "Stars",
            type: "line",
            data: data.map((x) => x.stars),
            smooth: 0.3,
            symbolSize: 6,
            showSymbol: false,
            itemStyle: { color: "#198c76" },
            lineStyle: { width: 3 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: "rgba(43,158,129,.22)" },
                { offset: 1, color: "rgba(43,158,129,.005)" },
              ]),
            },
          },
        ],
      }}
    />
  );
}
export function DistributionChart({
  items,
  onSelect,
}: {
  items: Distribution[];
  onSelect: (name: string) => void;
}) {
  const palette = [
    "#168471",
    "#79b9a6",
    "#f2c469",
    "#86a4cd",
    "#b9a5ca",
    "#cfada0",
    "#b8c9c4",
    "#d2dcd8",
  ];
  return (
    <div className="distribution">
      <Chart
        height={185}
        onClick={onSelect}
        option={{
          tooltip: { trigger: "item", formatter: "{b}: {c} 个" },
          color: palette,
          series: [
            {
              type: "pie",
              radius: ["57%", "79%"],
              center: ["50%", "50%"],
              avoidLabelOverlap: true,
              label: { show: false },
              itemStyle: {
                borderColor: "#fff",
                borderWidth: 4,
                borderRadius: 5,
              },
              data: items.map((x) => ({ name: x.name, value: x.count })),
            },
          ],
        }}
      />
      <div className="legend">
        {items.map((x, i) => (
          <button key={x.name} onClick={() => onSelect(x.name)}>
            <span
              className="legend-dot"
              style={{ background: palette[i % palette.length] }}
            />
            <span>{x.name}</span>
            <strong>{x.percentage.toFixed(1)}%</strong>
          </button>
        ))}
      </div>
    </div>
  );
}
export function Growth({ value }: { value: number | null }) {
  return (
    <span
      className={`growth ${value === null ? "muted" : value < 0 ? "negative" : ""}`}
    >
      {value != null &&
        (value < 0 ? <ArrowDownRight size={13} /> : <ArrowUpRight size={13} />)}
      {growthText(value)}
    </span>
  );
}
export function AppIcon({
  app,
  small = false,
}: {
  app: AppItem;
  small?: boolean;
}) {
  const colors = ["mint", "lavender", "peach", "blue", "lemon"];
  return (
    <div
      className={`app-icon ${colors[Math.abs(app.id) % colors.length]} ${small ? "small" : ""}`}
    >
      {app.name.slice(0, 2).toUpperCase()}
    </div>
  );
}
export function AppCard({ app }: { app: AppItem }) {
  return (
    <article className="app-card">
      <div className="app-card-top">
        <AppIcon app={app} />
        <span className="category-tag">{app.category}</span>
      </div>
      <Link to={`/apps/${app.id}`} className="app-title">
        {app.name}
        <ArrowUpRight size={17} />
      </Link>
      <p className="app-description">
        {app.summary || app.description || "项目介绍等待补充"}
      </p>
      <div className="app-tags">
        {app.tools.slice(0, 2).map((t) => (
          <span key={t}>{t}</span>
        ))}
        <span>{app.language || "未知语言"}</span>
      </div>
      <div className="app-card-bottom">
        <span className="star-count">
          <Star size={14} />
          {compact(app.stars)}
        </span>
        <span className="growth-label">
          7d <Growth value={app.growth_7d} />
        </span>
      </div>
    </article>
  );
}
export function AppTable({ apps }: { apps: AppItem[] }) {
  return (
    <div className="table-scroll">
      <table className="app-table">
        <thead>
          <tr>
            <th>应用项目</th>
            <th>应用类别</th>
            <th>开发工具</th>
            <th>Stars</th>
            <th>7 天净增</th>
            <th>开发证据</th>
          </tr>
        </thead>
        <tbody>
          {apps.map((app, i) => (
            <tr key={app.id}>
              <td>
                <Link to={`/apps/${app.id}`} className="app-cell">
                  <span className="rank">{String(i + 1).padStart(2, "0")}</span>
                  <AppIcon app={app} small />
                  <span>
                    <strong>{app.name}</strong>
                    <small>{kindLabel[app.kind] || app.kind}</small>
                  </span>
                </Link>
              </td>
              <td>
                <span className="category-tag">{app.category}</span>
              </td>
              <td>{app.tools.slice(0, 2).join(" · ") || "未知"}</td>
              <td>{compact(app.stars)}</td>
              <td>
                <Growth value={app.growth_7d} />
              </td>
              <td>
                <span
                  className={`evidence ${app.evidence_level === "explicit" ? "verified" : ""}`}
                >
                  {app.evidence_level === "explicit" && (
                    <CheckCircle2 size={12} />
                  )}{" "}
                  {evidenceLabel[app.evidence_level] || app.evidence_level}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function SectionTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="section-title">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h2>{title}</h2>
      </div>
      {children}
    </div>
  );
}
export function OutLink({
  url,
  children,
}: {
  url: string;
  children: ReactNode;
}) {
  return /^https?:\/\//i.test(url) ? (
    <a href={url} target="_blank" rel="noopener noreferrer">
      {children}
      <ExternalLink size={12} />
    </a>
  ) : (
    <span>{children}</span>
  );
}
export function MoreLink({
  to,
  children,
}: {
  to: string;
  children: ReactNode;
}) {
  return (
    <Link to={to} className="text-link">
      {children}
      <ArrowRight size={14} />
    </Link>
  );
}
