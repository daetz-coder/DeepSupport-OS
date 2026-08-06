# `core/`

跨层基础设施：配置、运行时开关、共享 HTTP 工具。无业务领域逻辑。

| 文件 | 作用 |
|------|------|
| `__init__.py` | 包标记（无导出） |
| `config.py` | `Settings` / `get_settings` / `ROOT_DIR`：LLM、DB、RAGLab、Daytona、CORS、路径解析 |
| `extensions.py` | `config/extensions.json`：Skills/MCP/禁用工具与子代理等开关读写 |
| `http_retry.py` | `request_with_retries`：有界超时 + 对超时/5xx 的有限重试（供 RAG 等出站调用） |
