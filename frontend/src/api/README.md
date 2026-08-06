# `frontend/src/api/`

与后端通信的薄封装（非 axios 实例层；以 `fetch` 为主）。

| 文件 | 作用 |
|------|------|
| `client.ts` | `API` base（dev 直连 :8000 / prod 同源）；`apiHeaders` 注入 `X-Admin-Token`；`apiJson` 统一 JSON 请求 |
