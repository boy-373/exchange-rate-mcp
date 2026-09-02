# -*- coding: utf-8 -*-
"""
汇率查询 · 远程 MCP Server
-------------------------
部署在 mcp.pianam.cn，任何支持 MCP 协议的 AI 客户端
(Claude Desktop / Cursor / Cline 等) 填入 URL 即可查询汇率。
数据源：Frankfurter（欧洲央行 ECB 每日参考汇率，免费、无需 API Key、无需注册），
网络异常时自动切换备用通道 open.er-api.com。纯只读查询，不涉及账号与付费。

Author: liufuyang  2026-09-01
"""
import json
import os
import ssl
import time
import urllib.parse
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

BASE_DIR = Path(__file__).parent

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# 常用货币代码 -> 中文名/符号（仅用于展示友好名称，查询用三字母代码）
CURRENCY_CN = {
    "CNY": "人民币", "USD": "美元", "EUR": "欧元", "JPY": "日元", "GBP": "英镑",
    "HKD": "港币", "KRW": "韩元", "TWD": "新台币", "AUD": "澳元", "CAD": "加元",
    "CHF": "瑞士法郎", "SGD": "新加坡元", "NZD": "新西兰元", "RUB": "俄罗斯卢布",
    "INR": "印度卢比", "THB": "泰铢", "MYR": "马来西亚林吉特", "IDR": "印尼盾",
    "PHP": "菲律宾比索", "VND": "越南盾", "ZAR": "南非兰特", "AED": "阿联酋迪拉姆",
    "SAR": "沙特里亚尔", "BRL": "巴西雷亚尔", "MXN": "墨西哥比索", "SEK": "瑞典克朗",
    "NOK": "挪威克朗", "DKK": "丹麦克朗", "PLN": "波兰兹罗提", "TRY": "土耳其里拉",
    "CZK": "捷克克朗", "HUF": "匈牙利福林", "ILS": "以色列新谢克尔", "ISK": "冰岛克朗",
}

# 中文货币名 -> ISO 代码（归一化用户输入）
CN_TO_CODE = {
    "人民币": "CNY", "元": "CNY", "美元": "USD", "美金": "USD", "美刀": "USD",
    "欧元": "EUR", "日元": "JPY", "英镑": "GBP", "港币": "HKD", "港元": "HKD",
    "韩元": "KRW", "新台币": "TWD", "台币": "TWD", "澳元": "AUD", "澳币": "AUD",
    "加元": "CAD", "加币": "CAD", "瑞士法郎": "CHF", "法郎": "CHF",
    "新加坡元": "SGD", "新币": "SGD", "新西兰元": "NZD", "卢布": "RUB",
    "印度卢比": "INR", "卢比": "INR", "泰铢": "THB", "林吉特": "MYR",
    "印尼盾": "IDR", "比索": "PHP", "越南盾": "VND", "兰特": "ZAR",
    "迪拉姆": "AED", "里亚尔": "SAR", "雷亚尔": "BRL", "克朗": "SEK",
}

CACHE_TTL = 2 * 3600  # 汇率每日更新，缓存 2 小时
_rates_cache = {}


def _http_get_json(url, timeout=15):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    req.add_header("Accept", "application/json,text/plain,*/*")
    resp = urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX)
    return json.loads(resp.read().decode("utf-8", errors="ignore"))


def normalize_code(name):
    """把用户输入（USD / usd / 美元 / 美金）归一化成三字母代码；无法识别返回 None。"""
    if not name:
        return None
    s = str(name).strip().upper()
    if s in CURRENCY_CN:
        return s
    if s in CN_TO_CODE:
        return CN_TO_CODE[s]
    raw = str(name).strip()
    if raw in CN_TO_CODE:
        return CN_TO_CODE[raw]
    if len(s) == 3 and s.isalpha():
        return s  # 未知代码也放行，让上游数据源报错
    return None


def fetch_frankfurter(base, targets):
    """主通道：Frankfurter（ECB 参考汇率，工作日每日更新）。"""
    symbols = ",".join(t for t in targets if t != base)
    url = ("https://api.frankfurter.dev/v1/latest"
           f"?base={urllib.parse.quote(base)}"
           + (f"&symbols={urllib.parse.quote(symbols)}" if symbols else ""))
    d = _http_get_json(url, timeout=15)
    rates = d.get("rates") or {}
    rates[base] = 1.0
    return rates, d.get("date", ""), "Frankfurter（欧洲央行参考汇率）"


def fetch_erapi(base, targets):
    """备用通道：open.er-api.com（免费全币种）。"""
    d = _http_get_json(f"https://open.er-api.com/v6/latest/{urllib.parse.quote(base)}", timeout=15)
    if d.get("result") != "success":
        raise RuntimeError(d.get("error-type") or "er-api 返回失败")
    all_rates = d.get("rates") or {}
    rates = {t: all_rates[t] for t in targets if t in all_rates}
    rates[base] = 1.0
    if base not in all_rates:
        raise RuntimeError(f"不支持的基准货币 {base}")
    missing = [t for t in targets if t != base and t not in all_rates]
    if missing:
        raise RuntimeError(f"不支持的目标货币: {','.join(missing)}")
    date = (d.get("time_last_update_utc") or "")[:16]
    return rates, date, "open.er-api.com（备用通道）"


def get_rates(base):
    """取某基准货币的全量汇率（带缓存，主备自动切换）。"""
    cached = _rates_cache.get(base)
    if cached and time.time() - cached[0] < CACHE_TTL:
        return cached[1]
    targets = list(CURRENCY_CN.keys())
    err = None
    try:
        rates, date, src = fetch_frankfurter(base, targets)
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        rates, date, src = fetch_erapi(base, targets)  # 再失败直接抛给上层
    data = {"rates": rates, "date": date, "source": src, "fallback_error": err}
    _rates_cache[base] = (time.time(), data)
    return data


def cur_label(code):
    cn = CURRENCY_CN.get(code)
    return f"{code}（{cn}）" if cn else code


mcp = FastMCP(
    "exchange-rate-query",
    host=os.environ.get("MCP_HOST", "127.0.0.1"),
    port=int(os.environ.get("MCP_PORT", "8005")),
    transport_security=TransportSecuritySettings(
        allowed_hosts=(os.environ.get("MCP_ALLOWED_HOSTS") or "127.0.0.1:*,localhost:*,[::1]:*,mcp.pianam.cn,mcp.pianam.cn:*").split(","),
        allowed_origins=(os.environ.get("MCP_ALLOWED_ORIGINS") or "https://mcp.pianam.cn,https://mcp.pianam.cn:*,http://127.0.0.1:*,http://localhost:*").split(","),
    ),
)


@mcp.tool()
def query_exchange_rate(base: str = "USD", target: str = "", amount: float = 0) -> dict:
    """查询实时汇率并可做金额换算。

    参数:
        base: 基准货币，代码或中文名均可，例如 "USD"、"美元"、"欧元"，默认美元
        target: 目标货币，代码或中文名均可，例如 "CNY"、"人民币"、"日元"；
                留空则返回常用货币（人民币/欧元/日元/英镑/港币/韩元）汇率
        amount: 可选，要换算的金额，例如 100 表示 100 单位基准货币折合多少目标货币
    返回:
        汇率日期、基准货币、目标货币汇率；给了 amount 时同时返回换算结果。
    数据源: Frankfurter（欧洲央行每日参考汇率，免费无需 Key），
            网络异常时自动切换 open.er-api.com。
    """
    try:
        b = normalize_code(base)
        if not b:
            return {"error": f"无法识别基准货币「{base}」，请用三字母代码（如 USD）或中文名（如 美元）"}
        data = get_rates(b)
        rates = data["rates"]

        if not target or not str(target).strip():
            show = ["CNY", "EUR", "JPY", "GBP", "HKD", "KRW"]
            show = [c for c in show if c in rates and c != b]
            out = {
                "基准货币": cur_label(b),
                "汇率日期": data["date"],
                "常用汇率": {cur_label(c): rates[c] for c in show},
                "数据源": data["source"],
                "说明": "参考汇率每日更新，非实时交易牌价，实际换汇以银行柜台为准",
            }
            if data.get("fallback_error"):
                out["备用通道原因"] = data["fallback_error"]
            return out

        t = normalize_code(target)
        if not t:
            return {"error": f"无法识别目标货币「{target}」，请用三字母代码（如 CNY）或中文名（如 人民币）"}
        if t not in rates:
            return {"error": f"数据源暂不支持货币 {t}，常见货币如人民币CNY/美元USD/欧元EUR/日元JPY均可查"}

        result = {
            "汇率日期": data["date"],
            "基准货币": cur_label(b),
            "目标货币": cur_label(t),
            "汇率": f"1 {b} = {rates[t]} {t}",
            "反向汇率": f"1 {t} = {round(1.0 / rates[t], 6)} {b}" if rates[t] else "",
            "数据源": data["source"],
            "说明": "参考汇率每日更新，非实时交易牌价，实际换汇以银行柜台为准",
        }
        try:
            amt = float(amount)
            if amt > 0:
                result["换算"] = f"{amt:g} {b} ≈ {round(amt * rates[t], 2)} {t}"
        except (TypeError, ValueError):
            pass
        if data.get("fallback_error"):
            result["备用通道原因"] = data["fallback_error"]
        return result
    except Exception as e:
        return {"error": f"汇率查询失败: {type(e).__name__}: {e}"}


if __name__ == "__main__":
    # 挂限流中间件：必须用 uvicorn 直接跑自定义 app——mcp.run() 内部会另建 app 实例，外挂中间件会被丢弃
    import sys
    import uvicorn
    sys.path.insert(0, str(BASE_DIR))
    from rate_limit import RateLimitMiddleware
    _app = mcp.streamable_http_app()
    _app.add_middleware(RateLimitMiddleware, limit_per_minute=60)
    uvicorn.run(_app, host=mcp.settings.host, port=mcp.settings.port, log_level=mcp.settings.log_level.lower())
