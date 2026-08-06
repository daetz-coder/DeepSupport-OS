# `db/`

Mock 企业数据与任务/评测持久化（默认 `data/deepsupport.db`）。工具与 HITL 写的「真相源」在此。

| 文件 | 作用 |
|------|------|
| `__init__.py` | 再导出模型与 `init_db` / `get_engine` / `get_session_factory` |
| `models.py` | SQLAlchemy ORM：员工/资产/账号/许可/工单/策略/案例/审计/任务记录/评测表；引擎与 `init_db` |
| `repositories.py` | 仓储与写路径：`EmployeeRepo` 等、`write_audit`、幂等账本 `AppliedAction` / `make_idempotency_key` |
| `seed.py` | 确定性 Faker 种子：Contoso 演示员工、工单、策略、知识案例 |
| `task_store.py` | 任务/线程注册表：`save_task` / `list_threads` / `delete_thread`（进程重启可恢复元数据） |
| `eval_store.py` | 评测用例与 run/结果落库；从 jsonl sync、指标目录 |
| `migrate.py` | 遗留 SQLite **加列**迁移（`create_all` 不会补已有表的新列） |

## 表域速览

- **企业 Mock**：`employees` · `assets` · `accounts` · `licenses` · `tickets` · `policies` · `cases`
- **运行时**：`task_records` · `audit_logs` · `applied_actions`
- **评测**：`eval_cases` · `eval_runs` · `eval_case_results`
