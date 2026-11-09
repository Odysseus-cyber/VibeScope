# VibeScope 前端

中文 React 工作台，所有页面通过 `/api/v1` 读取后端，没有独立的前端假数据。演示数据由后端独立演示库提供。

## 开发

需要 Node.js 22.12+，先启动后端 API（本地端口 8000）：

```sh
npm ci
npm run dev
```

浏览器访问 `http://127.0.0.1:5180`。Vite 将 `/api` 请求代理到本地后端。Docker 中通过 Nginx 代理到 `api:8000`。

```sh
npm test
npm run build
```

## 代码入口

- `src/App.tsx`：应用布局、路由与五类页面。
- `src/components.tsx`：ECharts 图表、应用卡片、榜单、空状态等共享组件。
- `src/api.ts`：API 调用、取消请求、周期刷新、UTC → 上海时间转换。
- `src/types.ts`：接口类型。任务和报告 ID 为字符串；缺失净增与历史观测值为 `null`。
- `src/styles.css`：响应式视觉与移动端布局。
- `src/App.test.tsx`：交互及统计语义回归测试。

图表使用 ECharts 的模块化引入及 SVG 渲染，仅打包折线图、环形图和所需组件。所有项目介绍、来源片段、API 错误均作为文本渲染；周报使用 React Markdown。

无时区 API 时间按 UTC 解析，界面始终使用 Asia/Shanghai。工具分布为多标签，不要求百分比总和为 100%；增长缺失显示“历史不足”，不会显示为零。
