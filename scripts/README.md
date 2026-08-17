# `scripts/`

仓库根目录运维 / 演示 / 评测 / 知识管线脚本。多数需在 `backend` 下用 `uv run python ../scripts/<name>.py` 执行（保证 `deepsupport_os` 可导入）。

## 演示与冒烟

| 文件 | 作用 |
|------|------|
| `demo-public.ps1` | 公开公网演示：全 Docker（DeepSupport + RAGLab）+ tunnel；只暴露 UI `:5173`（同源反代 API）。`-TunnelMode cloudflare\|localtunnel\|none`（默认 `cloudflare`） |
| `run_outlook_demo.py` | 无 HTTP：Outlook 登录失败场景直调 harness |
| `run_hitl_demo.py` | HITL 批准 + 密码重置落库 + 开单演示 |
| `smoke_checkpoint.py` | Checkpointer 最小冒烟（新建 thread `get_state`） |
| `test_remote_mcp.py` | 远程 MCP（Employee HTTP）连通性冒烟 |
| `seed_mock_data.py` | CLI 入口：调用 `db.seed.main` 写入 Mock 企业数据 |

```powershell
# 仓库根目录：起全栈并穿透（需 ../RAGLab 与两边 .env）
powershell -ExecutionPolicy Bypass -File scripts\demo-public.ps1
# 只起栈、不穿透：
powershell -ExecutionPolicy Bypass -File scripts\demo-public.ps1 -TunnelMode none
```

隧道模式（`-TunnelMode`）：

| 模式 | 公网地址 | 说明 |
| --- | --- | --- |
| `cloudflare`（默认） | `https://<随机>.trycloudflare.com` | Cloudflare quick tunnel：无需账号、无拦截页，脚本自动解析并打印公网 URL |
| `localtunnel` | `https://deepsupport-os.loca.lt` | 品牌域名；访客可能看到 loca.lt 密码页（需填本机公网 IP），子域名可能被占用 |
| `none`（旧 `-SkipTunnel`） | — | 只起栈，自行对 5173 穿透 |

Compose 宿主机映射：**UI 5173**、**API 18000→8000**、**RAGLab 18001→8000**、**RAGLab UI 18080**；容器内 `api` 经 `http://raglab:8000` 访问 RAGLab。对外演示只隧道 **5173**（nginx 同源反代 `/api` 与 `/health`，SSE 已关缓冲）。

## 评测与基线

| 文件 | 作用 |
|------|------|
| `run_eval.py` | 离线（schema）/ 在线评测；`--fast` 提速模式 |
| `run_baselines.py` | Baseline A（仅 RAG）/ B（LLM+工具无 Skills）对比 |
| `generate_full_cases.py` | 生成 `data/benchmark/full_cases.jsonl` |
| `print_eval_metrics.py` | 打印 last_eval / resume_partial 聚合指标 |
| `analyze_eval_failures.py` | 分析在线评测失败原因分布 |
| `write_eval_results_md.py` | 从评测产物写 `docs/eval-results.md` |

## 知识语料与 RAGLab

| 文件 | 作用 |
|------|------|
| `crawl_ms_support.py` | 爬取微软支持（zh-CN）为 Markdown（robots/限速） |
| `check_knowledge_quality.py` | 知识库质量门禁（长度、frontmatter、软警告） |
| `rebuild_ms_inventory.py` | 从已爬 md 重建 `inventory.json` |
| `ingest_to_raglab.py` | 批量 HTTP 入库 RAGLab（`RAGLAB_KB=deepsupport`） |
| `migrate_ms_kb.py` | 从错误 kb 清理/迁入 deepsupport |

## Skills

| 文件 | 作用 |
|------|------|
| `import_skill.py` | 从 `skills/catalog.json` 下载公开 skill 到 `skills/imported/` |

## 常用命令（示例）

```bash
cd backend
uv run python ../scripts/seed_mock_data.py
uv run python ../scripts/run_eval.py --offline
uv run python ../scripts/run_outlook_demo.py
uv run python ../scripts/ingest_to_raglab.py --limit 20
```
