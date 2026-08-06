# `rag/`

知识检索：优先 RAGLab HTTP（`RAGLAB_KB=deepsupport`），失败时回退本地 `data/knowledge/*.md`。

| 文件 | 作用 |
|------|------|
| `client.py` | `RAGLabClient`：health / search / get / list documents |
| `knowledge_tools.py` | LangChain 工具：`search_docs`、`get_document`、`search_cases`；导出 `KNOWLEDGE_TOOLS` |

Agent 侧通常经 knowledge 子代理或主 Agent 调用上述工具；长文落到 workspace，消息只留摘要与路径。
