# 数据字典

## PostgreSQL public：来源与操作状态

| 表 | 粒度与关键字段 | 说明 |
| --- | --- | --- |
| `raw_records` | 每次来源响应；`source, source_id, payload, observed_at, run_id` | 原始 JSON 与采集批次 |
| `applications` | 每个 repository ID 一行 | 当前名称、链接、描述、创建/收录/观测时间、stars/forks、分类、工具和证据 |
| `snapshots` | `app_id + snapshot_date` 唯一 | UTC 每日最后成功观测的 stars/forks，不补不存在的历史 |
| `discussions` | 每个 HN item ID 一行 | 标题、URL、分数、评论数、发布时间、采集时间、可空 app_id |
| `classifications` | 每次分类事件 | 分类、工具、证据、方式、模型、提示版本、时间、内容标识 |
| `jobs` | 每个任务 ID 一行 | kind、status、进度、处理/错误数量、摘要、开始/结束时间 |
| `coverage` | 每个来源运行观测 | source、status、detail、run_id、observed_at |
| `reports` | 每份报告一行 | 正文、事实、来源、统计周期、生成方式及数据模式；具体字段以模型为准 |
| `app_settings` | 每个设置键一行 | JSON 设置值 |

`applications.tools` 是字符串数组，`evidence` 是 `[{quote, url}]`。`kind` 为 application / developer_tool / resource；`evidence_level` 为 explicit / weak / unknown。`manual_override` 标记人工结论优先。

`method` 区分 rules / llm / manual / demo；`model`、`prompt_version`、`classified_at` 和 `content_hash` 用于说明一次结果来自什么输入与处理版本。未调用真实模型时不能把规则或演示结果记为 llm。

## dbt 输出契约

| 完整对象名 | 主要字段 |
| --- | --- |
| `dwd.dwd_applications` | `app_id, category, kind, evidence_level, tools, is_eligible` 以及应用身份与时间字段 |
| `dwd.dwd_snapshots` | `snapshot_id, app_id, snapshot_date, stars, forks, observed_at` |
| `dwd.dwd_discussions` | `discussion_id, app_id, title, url, score, comments, posted_at, observed_at` |
| `dws.dws_daily_metrics` | `snapshot_date, stars, apps, expected_apps, growth_eligible_apps, growth, coverage_ratio` |
| `ads.ads_app_metrics` | `app_id, as_of, stars, forks, growth_7d, growth_30d`；覆盖全部应用，含候选 |
| `ads.ads_category_metrics` | `category, count, percentage`；仅正式统计池 |
| `ads.ads_tool_metrics` | `tool, count, percentage`；仅正式统计池，多标签 |

`apps` 是该日实际观测数量；`expected_apps` 是当前正式统计池规模；`growth_eligible_apps` 是当日与前一日都有观测的应用数；`coverage_ratio=apps/expected_apps`。三个数量不能互相替代。

API 的每日趋势在数仓就绪时读取 DWS；缺失日期补出 null 观测和零个样本。应用详情同样保留缺日，不把断采连成连续历史。

所有 dbt 输出目前为视图。`generate_schema_name` 将层名映射为精确 dwd/dws/ads schema，不使用默认的 public_dwd 前缀。dbt profiles 从 `DBT_HOST/PORT/USER/PASSWORD/DBNAME` 读取连接信息，模型文件不保存凭据。
