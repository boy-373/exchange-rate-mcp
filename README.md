# Exchange Rate MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Server-blue)](https://modelcontextprotocol.io)
[![Remote](https://img.shields.io/badge/Streamable%20HTTP-hosted%20free-success)](https://mcp.pianam.cn/exchange-mcp/mcp)

Live **currency exchange rates and amount conversion** for 30+ currencies, accepting both ISO codes (USD) and Chinese names (美元), based on ECB daily reference rates.

- **Try it in 30 seconds**: a free public MCP endpoint is already running — just paste the URL into your MCP client (no install, no API key).
- **Or self-host**: a single Python file, stdlib HTTP + FastMCP, zero paid dependencies.

## ⚡ Use the hosted endpoint (no setup)

```
https://mcp.pianam.cn/exchange-mcp/mcp
```

Transport: **Streamable HTTP** (MCP 2025-03-26 compatible). No authentication required.

## 🔌 Client configuration

Add this to your MCP client's `mcpServers` configuration (Claude Desktop `claude_desktop_config.json`, Cursor `mcp.json`, Cline, Cherry Studio, etc.):

```json
{
  "mcpServers": {
    "exchange-rate": {
      "type": "http",
      "url": "https://mcp.pianam.cn/exchange-mcp/mcp"
    }
  }
}
```

> Clients that do not accept `"type": "http"` (some Cherry Studio / older
> Cline versions) accept the same entry with just `"url"`.

## 🧰 Tools

| Tool | Parameters | Returns |
|---|---|---|
| `query_exchange_rate(base="USD", target="", amount=0)` | `base` / `target`: ISO code or Chinese name — `"USD"` / `"美元"` / `"美金"` all work. Empty `target` returns common rates (CNY/EUR/JPY/GBP/HKD/KRW).<br>`amount`: optional, converts N units of base currency. | Rate date, base→target rate, reverse rate, and (when `amount` is given) the converted amount. Reference rates — not live trading prices. |

## 📡 Data sources, caching & limits

- Primary source: **[Frankfurter](https://frankfurter.dev/)** — European Central Bank (ECB) daily reference rates, free, no API key.
- Automatic fallback: **[open.er-api.com](https://www.exchange-api.com/)** if the primary source fails.
- 32 currencies with Chinese display names (人民币, 美元, 欧元, 日元, 港币, 韩元, 新台币 …) and Chinese aliases (美金/美刀, 港元, 台币, 澳币 …).
- Rates cached for **2 hours** (ECB updates on working days); hosted endpoint rate-limited to **60 requests / minute / IP**.

## 🐢 Self-hosting

```bash
git clone https://github.com/boy-373/exchange-rate-mcp.git
cd exchange-rate-mcp
pip install -r requirements.txt
python exchange_mcp_server.py
# the server listens on 127.0.0.1:8005 by default; override with:
#   MCP_HOST=0.0.0.0 MCP_PORT=9000 python exchange_mcp_server.py
#   MCP_ALLOWED_HOSTS="your-domain.com,127.0.0.1:*"
#   MCP_ALLOWED_ORIGINS="https://your-domain.com"
```

Then point your MCP client at `http://127.0.0.1:8005/mcp`.
No API keys or accounts are ever required.



## 🗂️ Files

- `exchange_mcp_server.py` — the MCP server (FastMCP, Streamable HTTP transport).
- `rate_limit.py` — lightweight per-IP sliding-window rate-limit middleware (60 req/min default).
- `requirements.txt` — `mcp`, `uvicorn`, `starlette`.
- `server.json` — official MCP Registry manifest (remote server entry, ready to publish with `mcp-publisher`).
- `smithery.yaml` / `glama.json` — directory listing metadata.

---

## 🇨🇳 中文使用说明

**一句话**：30+ 常用货币实时参考汇率与金额换算，中文货币名直接问（「100 美元换多少人民币」）。

**在线直连地址（免费、无需 Key、开箱即用）**：`https://mcp.pianam.cn/exchange-mcp/mcp`

在 MCP 客户端（Claude Desktop / Cursor / Cherry Studio / Cline 等）的配置里加入：

```json
{
  "mcpServers": {
    "exchange-rate": {
      "type": "http",
      "url": "https://mcp.pianam.cn/exchange-mcp/mcp"
    }
  }
}
```

**工具**：

- `query_exchange_rate(base, target, amount)`：查汇率并可换算金额。货币可用三字母代码或中文名（USD / 美元 / 美金均可）；`target` 留空返回人民币/欧元/日元/英镑/港币/韩元常用汇率；`amount` 给正数则同时返回换算结果。
- 主数据源 Frankfurter（欧洲央行 ECB 每日参考汇率，免费无需 Key），故障自动切换 open.er-api.com。
- 参考汇率每日更新，非实时交易牌价，实际换汇以银行柜台为准。

**服务特性**：数据源全部为公开接口、无需注册/付费；服务端内存缓存、失败自动降级/切换备用通道；单 IP 限流 60 次/分钟。

**本地部署**：

```bash
git clone https://github.com/boy-373/exchange-rate-mcp.git
cd exchange-rate-mcp
pip install -r requirements.txt
python exchange_mcp_server.py
# 默认监听 127.0.0.1:8005，可用环境变量 MCP_HOST / MCP_PORT / MCP_ALLOWED_HOSTS / MCP_ALLOWED_ORIGINS 覆盖
```

## 📄 License

[MIT](LICENSE) © 2026 boy-373

## Install via Smithery

One-click install for [Smithery](https://smithery.ai)-supported clients (Claude Desktop, Cursor, etc.):

[![Smithery](https://smithery.ai/badge/1561852680/exchange-rate-mcp)](https://smithery.ai/servers/1561852680/exchange-rate-mcp)

Or run:

```bash
npx -y @smithery/cli install 1561852680/exchange-rate-mcp --client claude
```
