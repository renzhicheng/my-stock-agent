# -*- coding: utf-8 -*-
"""
东方财富行业板块高成交额筛选与指标补全。
"""

from __future__ import annotations

import math
import random
import time
from datetime import datetime
from typing import Any, Dict, List

import os
# 强行清空 Python 环境的代理设置，让请求直连国内网络
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
os.environ["all_proxy"] = ""

import akshare as ak
import pandas as pd

from akshare.utils.func import fetch_paginated_data

# 500 亿 = 500 * 1 亿 = 5e10 元
TURNOVER_THRESHOLD_YUAN = 50_000_000_000

# 东方财富行业板块列表（与 akshare __stock_board_industry_name_em 同源）并补充成交量/成交额/振幅等字段
_INDUSTRY_CLIST_URL = "https://17.push2.eastmoney.com/api/qt/clist/get"
_INDUSTRY_CLIST_PARAMS: Dict[str, Any] = {
    "pn": "1",
    "pz": "100",
    "po": "1",
    "np": "1",
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": "2",
    "invt": "2",
    "fid": "f3",
    "fs": "m:90 t:2 f:!50",
    "fields": (
        "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,"
        "f23,f24,f25,f26,f22,f33,f11,f62,f128,f136,f115,f152,f124,f107,f104,f105,"
        "f140,f141,f207,f208,f209,f222,f47,f48,f171"
    ),
}

_OUTPUT_COLUMNS: List[str] = [
    "序号",
    "代码",
    "名称",
    "涨幅",
    "成交量",
    "换手%",
    "涨速%",
    "成交额",
    "振幅%",
    "涨停家数",
    "跌停家数",
    "上涨家数",
    "下跌家数",
    "5日涨幅%",
    "10日涨幅%",
    "20日涨幅%",
    "60日涨幅%",
    "120日涨幅%",
    "250日涨幅%",
    "年初至今涨幅%",
    "周涨幅%",
    "月涨幅%",
]


def _to_num(s: Any) -> float:
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return float("nan")
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace(",", "")
    if t in {"", "-", "--", "nan", "None"}:
        return float("nan")
    try:
        return float(t)
    except ValueError:
        return float("nan")


def _series_num(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(float("nan"), index=df.index)
    return pd.to_numeric(df[col], errors="coerce")


def _turnover_yuan_from_row(row: pd.Series) -> float:
    """优先 f48（clist 常见成交额字段），否则尝试 f6。"""
    for key in ("f48", "f6"):
        if key not in row.index:
            continue
        v = _to_num(row.get(key))
        if not math.isnan(v) and v > 0:
            if v > 1e15:
                v = v * 1e-2
            return v
    return float("nan")


def _fetch_industry_spot_with_amount(timeout: int = 30) -> pd.DataFrame:
    """分页拉取行业板块实时列表（含 f47/f48 等扩展字段）。"""
    params = dict(_INDUSTRY_CLIST_PARAMS)
    df = fetch_paginated_data(_INDUSTRY_CLIST_URL, params, timeout=timeout)
    for c in df.columns:
        if str(c).startswith("f") and c not in ("f12", "f14"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _limit_up_down_counts(symbol: str, sleep_s: float = 0.25) -> tuple[int, int]:
    """用成分股涨跌幅近似统计涨停/跌停家数（主板约 10%，科创/创业约 20%）。"""
    time.sleep(sleep_s)
    try:
        cons = ak.stock_board_industry_cons_em(symbol=symbol)
    except Exception:
        return 0, 0
    if cons is None or cons.empty or "涨跌幅" not in cons.columns:
        return 0, 0
    chg = pd.to_numeric(cons["涨跌幅"], errors="coerce").fillna(0.0)
    zt = int(((chg >= 9.85) & (chg < 17)).sum() + (chg >= 17.5).sum())
    dt = int(((chg <= -9.85) & (chg > -17)).sum() + (chg <= -17.5).sum())
    return zt, dt


def _hist_daily(symbol: str, timeout: int = 30) -> pd.DataFrame:
    end = datetime.now().strftime("%Y%m%d")
    start = "20150101"
    time.sleep(0.2)
    try:
        d = ak.stock_board_industry_hist_em(
            symbol=symbol,
            start_date=start,
            end_date=end,
            period="日k",
            adjust="",
        )
    except Exception:
        return pd.DataFrame()
    if d is None or d.empty:
        return pd.DataFrame()
    d = d.copy()
    d["日期"] = pd.to_datetime(d["日期"], errors="coerce")
    d["收盘"] = pd.to_numeric(d["收盘"], errors="coerce")
    d = d.dropna(subset=["日期", "收盘"]).sort_values("日期")
    return d


def _hist_period_last_chg(symbol: str, period: str, sleep_s: float = 0.2) -> float:
    time.sleep(sleep_s)
    try:
        h = ak.stock_board_industry_hist_em(
            symbol=symbol,
            start_date="20180101",
            end_date=datetime.now().strftime("%Y%m%d"),
            period=period,
            adjust="",
        )
    except Exception:
        return float("nan")
    if h is None or h.empty or "涨跌幅" not in h.columns:
        return float("nan")
    last = pd.to_numeric(h["涨跌幅"], errors="coerce").dropna()
    if last.empty:
        return float("nan")
    return float(last.iloc[-1])


def _return_over_trading_days(
    closes: pd.Series, trading_days_back: int
) -> float:
    """最近一个收盘相对前 trading_days_back 个交易日收盘的涨跌幅 %。"""
    c = closes.dropna()
    if len(c) < trading_days_back + 1:
        return float("nan")
    a = float(c.iloc[-(trading_days_back + 1)])
    b = float(c.iloc[-1])
    if a == 0 or math.isnan(a) or math.isnan(b):
        return float("nan")
    return (b / a - 1.0) * 100.0


def _ytd_return_pct(daily: pd.DataFrame) -> float:
    if daily.empty or "日期" not in daily.columns or "收盘" not in daily.columns:
        return float("nan")
    year = datetime.now().year
    sub = daily[daily["日期"] >= pd.Timestamp(year, 1, 1)]
    if sub.empty:
        return float("nan")
    first_close = float(sub["收盘"].iloc[0])
    last_close = float(sub["收盘"].iloc[-1])
    if first_close == 0:
        return float("nan")
    return (last_close / first_close - 1.0) * 100.0


def _spot_metrics_from_f(df: pd.DataFrame) -> pd.DataFrame:
    """从 clist 原始 f 字段整理涨幅、换手、涨速、振幅、家数等。"""
    out = pd.DataFrame(index=df.index)
    out["代码"] = df["f12"].astype(str) if "f12" in df.columns else ""
    out["名称"] = df["f14"].astype(str) if "f14" in df.columns else ""
    out["涨幅"] = _series_num(df, "f4")
    out["成交量"] = _series_num(df, "f47")
    out["换手%"] = _series_num(df, "f9")
    out["涨速%"] = _series_num(df, "f22")
    out["振幅%"] = _series_num(df, "f171")
    if "f7" in df.columns and out["振幅%"].isna().all():
        out["振幅%"] = _series_num(df, "f7")
    out["上涨家数"] = _series_num(df, "f128")
    out["下跌家数"] = _series_num(df, "f136")
    tu = df.apply(_turnover_yuan_from_row, axis=1)
    out["成交额_元"] = tu
    out["成交额_亿"] = tu / 1e8
    zt = _series_num(df, "f104")
    dt = _series_num(df, "f105")
    out["_涨停_接口"] = zt
    out["_跌停_接口"] = dt
    return out


def _df_to_markdown(df: pd.DataFrame) -> str:
    if df.empty and len(df.columns) == 0:
        df = pd.DataFrame(columns=_OUTPUT_COLUMNS)
    if df.empty:
        try:
            return df.to_markdown(index=False)
        except ImportError:
            cols = list(_OUTPUT_COLUMNS)
            return "| " + " | ".join(cols) + " |\n| " + " | ".join(["---"] * len(cols)) + " |"
    try:
        return df.to_markdown(index=False)
    except ImportError:
        cols = list(df.columns)
        sep = "| " + " | ".join(cols) + " |"
        bar = "| " + " | ".join(["---"] * len(cols)) + " |"
        lines = [sep, bar]
        for _, row in df.iterrows():
            cells = []
            for c in cols:
                v = row[c]
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    cells.append("")
                else:
                    cells.append(str(v))
            lines.append("| " + " | ".join(cells) + " |")
        return "\n".join(lines)


def fetch_high_turnover_industries(
    turnover_threshold_yuan: float = TURNOVER_THRESHOLD_YUAN,
    request_timeout: int = 30,
) -> str:
    """
    获取东方财富行业板块实时行情，筛选成交额（元）大于阈值的板块，
    补全多周期涨幅与涨跌停家数等字段，返回 Markdown 表格字符串。

    主数据与 akshare 的东方财富行业板块 clist 一致（``m:90 t:2 f:!50``），
    在原生 fields 基础上追加 ``f47/f48/f171`` 等以获取成交量、成交额、振幅。

    输出表中「成交额」列的数值单位为**亿元**（由元除以 1e8），筛选逻辑仍按**元**
    与 ``turnover_threshold_yuan`` 比较（默认 5e10 即 500 亿）。

    :param turnover_threshold_yuan: 成交额下限（元），默认 500 亿 = 5e10。
    :param request_timeout: HTTP 超时秒数。
    :return: Markdown 表格字符串。
    """
    raw = _fetch_industry_spot_with_amount(timeout=request_timeout)
    if raw.empty:
        return _df_to_markdown(pd.DataFrame(columns=_OUTPUT_COLUMNS))

    spot = _spot_metrics_from_f(raw)
    spot = spot[spot["成交额_元"] >= float(turnover_threshold_yuan)].copy()
    spot = spot.sort_values("成交额_元", ascending=False).reset_index(drop=True)

    rows: List[Dict[str, Any]] = []
    for rank, (_, r) in enumerate(spot.iterrows(), start=1):
        code = str(r["代码"]).strip()
        name = str(r["名称"]).strip()
        sym = code if code.upper().startswith("BK") else name

        zt_api = r.get("_涨停_接口")
        dt_api = r.get("_跌停_接口")
        if pd.notna(zt_api) and pd.notna(dt_api):
            zt_n, dt_n = int(round(float(zt_api))), int(round(float(dt_api)))
        else:
            zt_n, dt_n = _limit_up_down_counts(sym, sleep_s=0.25)

        daily = _hist_daily(sym, timeout=request_timeout)
        closes = daily["收盘"] if not daily.empty else pd.Series(dtype=float)

        r5 = _return_over_trading_days(closes, 5)
        r10 = _return_over_trading_days(closes, 10)
        r20 = _return_over_trading_days(closes, 20)
        r60 = _return_over_trading_days(closes, 60)
        r120 = _return_over_trading_days(closes, 120)
        r250 = _return_over_trading_days(closes, 250)
        ytd = _ytd_return_pct(daily)
        wchg = _hist_period_last_chg(sym, "周k", sleep_s=0.2)
        mchg = _hist_period_last_chg(sym, "月k", sleep_s=0.2)

        vol = r["成交量"]

        row_out: Dict[str, Any] = {
            "序号": rank,
            "代码": code,
            "名称": name,
            "涨幅": round(float(r["涨幅"]), 4)
            if not math.isnan(float(r["涨幅"]))
            else "",
            "成交量": int(vol) if not math.isnan(vol) else "",
            "换手%": round(float(r["换手%"]), 4)
            if not math.isnan(float(r["换手%"]))
            else "",
            "涨速%": round(float(r["涨速%"]), 4)
            if not math.isnan(float(r["涨速%"]))
            else "",
            "成交额": round(float(r["成交额_亿"]), 4)
            if not math.isnan(float(r["成交额_亿"]))
            else "",
            "振幅%": round(float(r["振幅%"]), 4)
            if not math.isnan(float(r["振幅%"]))
            else "",
            "涨停家数": zt_n,
            "跌停家数": dt_n,
            "上涨家数": int(r["上涨家数"])
            if not math.isnan(float(r["上涨家数"]))
            else "",
            "下跌家数": int(r["下跌家数"])
            if not math.isnan(float(r["下跌家数"]))
            else "",
            "5日涨幅%": round(r5, 4) if not math.isnan(r5) else "",
            "10日涨幅%": round(r10, 4) if not math.isnan(r10) else "",
            "20日涨幅%": round(r20, 4) if not math.isnan(r20) else "",
            "60日涨幅%": round(r60, 4) if not math.isnan(r60) else "",
            "120日涨幅%": round(r120, 4) if not math.isnan(r120) else "",
            "250日涨幅%": round(r250, 4) if not math.isnan(r250) else "",
            "年初至今涨幅%": round(ytd, 4) if not math.isnan(ytd) else "",
            "周涨幅%": round(wchg, 4) if not math.isnan(wchg) else "",
            "月涨幅%": round(mchg, 4) if not math.isnan(mchg) else "",
        }
        rows.append(row_out)
        time.sleep(random.uniform(0.35, 0.75))

    result = pd.DataFrame(rows, columns=_OUTPUT_COLUMNS)
    return _df_to_markdown(result)

# ==========================================
# 🚀 本地测试：直接运行此文件时触发出征命令
# ==========================================
if __name__ == "__main__":
    import time
    print("🕵️‍♂️ 东厂探子已出动，正在潜入东方财富服务器...")
    start_time = time.time()
    
    # 呼叫你刚才让 Cursor 写的核心函数
    result = fetch_high_turnover_industries()
    
    print("\n" + "="*50)
    print("📜 截获情报如下：\n")
    print(result)
    print("="*50)
    print(f"⏱️ 抓取完毕！耗时: {time.time() - start_time:.2f} 秒")