import streamlit as st
import pandas as pd

# --- 页面配置 ---
st.set_page_config(page_title="A股量化分析看板", layout="wide")

# --- 侧边栏：文件上传 ---
st.sidebar.header("📂 数据中心")
uploaded_file = st.sidebar.file_uploader("上传 Colab 处理后的 Excel", type=["xlsx"])

# --- 主界面 ---
st.title("📈 A股资金流向量化看板")

if uploaded_file:
    # 1. 读取 Excel 里的所有日期（Sheets）
    excel_data = pd.ExcelFile(uploaded_file)
    sheet_names = excel_data.sheet_names
    
    # 2. 让用户选择日期
    selected_date = st.sidebar.selectbox("选择分析日期", sheet_names)
    
    # 3. 加载选定日期的数据
    df = pd.read_excel(uploaded_file, sheet_name=selected_date)
    
    # 4. 界面布局：左边看表，右边看统计
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader(f"📍 {selected_date} 详细数据")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
    with col2:
        st.subheader("📊 数据概览")
        # 简单计算：这一天总共筛选出了多少个核心板块/个股
        total_count = len(df)
        st.metric(label="活跃标的数量", value=total_count)
        
        # 如果是行业板块，可以看平均成交额
        if '成交额' in df.columns:
            avg_amount = df['成交额'].mean() / 1e8  # 转为亿元
            st.metric(label="平均成交额 (亿元)", value=f"{avg_amount:.2f}")

else:
    # 未上传文件时的提示状态
    st.info("👋 欢迎！请先在左侧上传你的 Excel 文件开始分析。")
    # 这里可以插入一张示意图，展示应用结构
    #
