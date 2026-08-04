# Microsoft Support 语料（zh-CN）

本目录存放从 [Microsoft Support](https://support.microsoft.com/) **公开页面**采集的 Markdown，供 DeepSupport OS 本地检索回退与后续 RAGLab 入库。

## 合规

- 遵守 `robots.txt`（不抓 `/search/` 等 Disallow 路径）
- 优先 sitemap 发现种子 URL
- 限速 + 可识别 User-Agent：`DeepSupportOS-ResearchBot`
- 每篇保留 `source_url`；仅用于演示/研究，请遵守 Microsoft 服务条款与版权

## 采集

```bash
cd backend
uv run python ../scripts/crawl_ms_support.py --discover --per-product 3
# 可选：RAGLab 运行时入库
uv run python ../scripts/crawl_ms_support.py --seeds-file ../data/raw/microsoft/seeds.json --ingest
```

产物：

- `data/knowledge/microsoft/*.md` — 清洗后的正文
- `data/raw/microsoft/html/` — 原始 HTML（可忽略入库）
- `data/raw/microsoft/crawl_manifest.json` — 采集清单
- `data/raw/microsoft/seeds.json` — 种子 URL
