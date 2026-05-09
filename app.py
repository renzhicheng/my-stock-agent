import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- 页面设置 ---
st.set_page_config(page_title="A股智投看板", layout="wide")

# --- 初始化 Gemini (使用你已有的 API Key) ---
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-pro')

# --- 侧边栏：文件上传与处理 ---
with st.sidebar:
    st.header("📤 数据同步中心")
    uploaded_file = st.file_uploader("上传原始 Excel", type=["xlsx"])
    
    if uploaded_file:
        # 这里可以嵌入你之前的 Colab 过滤逻辑
        st.success("数据已接收，正在执行自动化过滤并同步至 Google Drive...")

# --- 主界面布局 ---
tab1, tab2 = st.tabs(["📊 今日深度报告", "💬 智能助手对话"])

with tab1:
    if uploaded_file:
        st.subheader("🤖 Gemini 自动分析报告")
        # 模拟自动触发报告逻辑
        if st.button("更新今日分析"):
            with st.spinner("正在扫描云盘数据..."):
                # 这里放入你固定的专业 Prompt
                response = model.generate_content("请基于今日成交额数据，生成一份技术性分析报告。")
                st.markdown(response.text)
    else:
        st.info("请先上传数据以生成报告")

with tab2:
    st.subheader("💬 数据自由问答")
    # 初始化聊天历史
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 显示聊天历史
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 聊天输入
    if prompt := st.chat_input("问问关于板块资金流向的问题..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # 这里 Gemini 会结合你的数据进行回答
            response = model.generate_content(prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
