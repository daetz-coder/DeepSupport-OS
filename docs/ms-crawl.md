# Microsoft Support 爬取说明

见 [`data/knowledge/microsoft/README.md`](../knowledge/microsoft/README.md)。

首次试跑结果摘要（sitemap 发现 + 限速）：

- 成功约 12 篇（Outlook / Teams / OneDrive / Excel）
- 部分页面返回 HTTP 403（站点反爬/频控）；脚本已加 403 重试
- 本地检索：`search_docs` 会 `rglob` 本目录 Markdown
