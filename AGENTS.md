# VibeScope development

- UI、说明与面试材料使用中文，标识符使用英文。
- 首次执行前阅读 README.md、docs/metrics.md 与 docs/api-contract.md。
- demo 与 live 的数据库、缓存、周报和采集状态隔离；不向 live 写演示历史。
- 已确认统计池：`kind='application' AND evidence_level='explicit'`。工具、教程与证据未知项保留在候选区。
- 星标净增使用精确窗口边界的成功观测；缺失值保留 null，允许负增长。不得用当前 star 总数推造历史。
- AI 分类保存来源片段和版本；尊重人工修正。周报数字由 SQL 提供，不由 LLM 计算或编造。
- 更新公开接口时同步 docs/api-contract.md；更新指标时同步 dbt SQL 与 docs/metrics.md。
- 使用 pytest 检查后端、前端构建检查类型、dbt build 验证 PostgreSQL 仓库。不得把 SQLite 测试描述为 PostgreSQL 已验证。
- 不提交 .env、token、本地数据库、dbt 运行产物；不自动发布公网服务。
