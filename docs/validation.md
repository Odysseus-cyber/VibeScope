# 验证记录

验证日期：2026-11-09（Asia/Shanghai）。环境：macOS ARM64、Docker Desktop 29.5.3、容器 Python 3.12、PostgreSQL 17、Node 22。所有测试在项目自己的临时目录和 Compose 资源内运行。

## 已执行结果

| 检查 | 结果 |
| --- | --- |
| 后端 `python -m pytest -q backend/tests` | 61 passed；覆盖边界缺失、负增长、去重、改名、跨源关联、分类重试、人工覆盖、模式隔离、周报事实、API与SQL口径 |
| 前端 `npm test` | 8 passed；覆盖导航、筛选、错误/空态、增长语义与UTC时间显示 |
| 前端 TypeScript + Vite 生产构建 | 通过；已生成并运行 Nginx 生产镜像 |
| dbt build（实际 PostgreSQL） | 7 个模型 success、30 个数据测试 pass |
| Docker Compose demo/live | 两种模式均完成迁移、初始化、dbt构建和服务健康检查，使用独立网络与数据卷 |
| 演示 HTTP 端到端 | Nginx → FastAPI → PostgreSQL → worker → 周报成功；72候选、64正式应用、36天模拟历史，7/30/90日筛选与CSV通过 |
| 真实匿名采集 + PostgreSQL/dbt | 4个GitHub项目、6条HN讨论、22条原始记录、4个快照、4次规则分类；2个应用符合榜单条件，生成2个真实来源的观察摘要；演示原始记录为0 |
| 浏览器检查 | 窗口切换、类别下钻、详情证据、人工修正保存、周报异步生成、同步任务完成、375px布局无全页横向溢出 |
| 迁移幂等性 | 新库迁移、seed、重复迁移通过；重复seed不重复创建项目和快照 |

启动验收曾发现 PostgreSQL 的 `date >= varchar` 严格类型错误，已改为绑定 Python date，并通过实际容器重跑。SQLite 测试不能替代该检查。

## 分类评估

- `data/evaluation/results.json`：40条人工定义预期的**合成规格**，当前规则逐字段符合率100%，只用于规格回归。
- `data/evaluation/real-agent-cases.json` 和 `real-agent-results.json`：32个真实GitHub来源，逐条附短摘录、来源与审读理由。当前规则作品类型符合率27/32（84.38%）；作者开发声明判断32/32，但只有2个正例。
- 真实样本由AI审读，且用于迭代规则，属于开发样本，不是人类标注或独立留出测试；五个作品类型错误已保留。
- `live-smoke-results.json` 记录实际匿名来源采集；其SQLite验证另由本页记录的PostgreSQL端到端验证补充。
- 未配置外部LLM密钥，因此没有声称验证任何付费模型服务的质量或成本；协议、输出验证和失败回退使用mock测试。

## 复现

```bash
./scripts/start.sh demo
./scripts/check.sh demo
python3 scripts/verify_http.py --base-url http://127.0.0.1:5180
```

开发环境运行：

```bash
cd backend
uv sync --frozen
uv run pytest
uv run python -m app.cli evaluate
# 在 frontend 运行 npm ci、npm test、npm run build
```

dbt 的 `run_results.json` 与 `manifest.json` 保存在对应模式runtime数据卷的 `/srv/runtime/dbt/target`。启动脚本不会删除历史数据。

## 尚未测量的项目

尚未进行长期定时采集观察、高并发吞吐/P95、真实人类标注集评估或外部LLM服务实测。前端生产JS压缩后约318 KB（gzip）；存在非阻塞的大bundle构建提示。不要把演示数据规模写成线上业务规模，也不要把开发样本成绩写成生产模型准确率。
