# -*- coding: utf-8 -*-
import os
import json
import pandas as pd
import akshare as ak

# 屏蔽代理，直连新浪（新浪在海外直连极快）
os.environ['NO_PROXY'] = '*'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING_FILE = os.path.join(BASE_DIR, "data", "industry_mapping.json")
THRESHOLD_BILLION = 500 

def load_industry_mapping():
    if not os.path.exists(MAPPING_FILE): return {}
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_and_aggregate():
    print("🚀 正在聚合板块涨幅（口径见输出列「口径」）…")
    
    mapping = load_industry_mapping()
    if not mapping: return "❌ 映射表丢失。"

    try:
        # 1. 抓取个股全量数据（包含：涨跌幅、成交额、总市值）
        df_all = ak.stock_zh_a_spot()
        
        # 2. 核心列名自适应（识别：changepercent, amount, mktcap）
        col_code = next(
            (c for c in ['code', 'symbol', '代码'] if c in df_all.columns),
            None,
        )
        if col_code is None:
            return f"❌ 找不到股票代码列，当前列: {list(df_all.columns)}"
        col_change = next(
            (c for c in ['changepercent', '涨跌幅'] if c in df_all.columns),
            None,
        )
        col_amount = next(
            (c for c in ['amount', '成交额'] if c in df_all.columns),
            None,
        )
        if col_change is None or col_amount is None:
            return (
                "❌ 涨跌幅或成交额列缺失，当前列: "
                f"{list(df_all.columns)}"
            )
        col_cap = next(
            (c for c in ['mktcap', '总市值'] if c in df_all.columns),
            None,
        )
        use_amount_weight = col_cap is None
        agg_label = "成交额加权" if use_amount_weight else "总市值加权"

        # 3. 数据脱水
        df_all['clean_code'] = df_all[col_code].astype(str).str.extract(r'(\d{6})')[0]
        df_all['change_val'] = pd.to_numeric(df_all[col_change], errors='coerce').fillna(0)
        df_all['amount_val'] = pd.to_numeric(df_all[col_amount], errors='coerce').fillna(0)
        if col_cap is not None:
            df_all['cap_val'] = pd.to_numeric(df_all[col_cap], errors='coerce').fillna(0)
        else:
            df_all['cap_val'] = 0.0

        # 情绪标签
        df_all['is_up'] = df_all['change_val'] > 0
        df_all['is_down'] = df_all['change_val'] < 0
        df_all['is_limit'] = df_all['change_val'] > 9.8 

        # 建立极速索引
        stock_dict = df_all.set_index('clean_code').to_dict('index')

        # 4. 聚合计算
        sector_results = []
        for sector_name, stocks in mapping.items():
            s_amount = 0.0
            # 加权涨幅：sum(r_i * w_i) / sum(w_i)。w_i 为市值时近似「市值加权组合」的当日涨跌；
            # w_i 为成交额时衡量的是「资金活跃度加权」，与多数网站上的行业指数涨跌幅不是同一口径。
            weighted_numerator = 0.0
            total_weight_in_sector = 0.0
            matched_changes = []  # 有行情的成分，用于等权对照
            up, down, limit = 0, 0, 0
            
            for s in stocks:
                info = stock_dict.get(str(s['code']))
                if info:
                    change = info['change_val']
                    cap = info['cap_val']
                    amt = info['amount_val']
                    
                    s_amount += amt
                    matched_changes.append(change)
                    up += 1 if info['is_up'] else 0
                    down += 1 if info['is_down'] else 0
                    limit += 1 if info['is_limit'] else 0
                    
                    w = amt if use_amount_weight else cap
                    if w > 0:
                        weighted_numerator += change * w
                        total_weight_in_sector += w
            
            if total_weight_in_sector > 0:
                final_change = weighted_numerator / total_weight_in_sector
                eq_change = (
                    sum(matched_changes) / len(matched_changes)
                    if matched_changes
                    else None
                )
                
                sector_results.append({
                    "板块名称": sector_name,
                    "口径": agg_label,
                    "加权涨幅%": round(final_change, 2),
                    "等权涨幅%": round(eq_change, 2) if eq_change is not None else None,
                    "成交额(亿)": round(s_amount / 1e8, 2),
                    "上涨": up,
                    "下跌": down,
                    "涨停": limit,
                    "总家数": len(stocks)
                })

        # 5. 排序展示
        all_df = pd.DataFrame(sector_results).sort_values("成交额(亿)", ascending=False)
        return all_df[all_df["成交额(亿)"] >= THRESHOLD_BILLION].to_markdown(index=False)

    except Exception as e:
        return f"💥 异常: {str(e)}"

if __name__ == "__main__":
    print(fetch_and_aggregate())