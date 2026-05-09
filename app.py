import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 强制开启滚动条的 CSS 注入 ---
st.markdown("""
    <style>
    /* 强制主容器允许垂直滚动 */
    .stMain {
        overflow-y: auto !important;
    }
    /* 针对聊天消息容器的优化 */
    .stChatMessageContainer {
        overflow-y: auto !important;
    }
    /* 隐藏一些不必要的页边距，让滚动更顺滑 */
    .block-container {
        padding-bottom: 5rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. 基础配置 ---
st.set_page_config(page_title="智投对话终端", layout="wide")

# 初始化 GCP 与 Gemini 权限
gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(gcp_info)
drive_service = build('drive', 'v3', credentials=credentials)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- 2. 动态获取模型 (解决 404 关键) ---
@st.cache_resource
def get_best_model():
    # 自动获取当前 API 支持的所有模型
    models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    # 优先匹配 Gemini 3 系列
    for m in models:
        if 'gemini-3-flash' in m: return m
    return models[0] # 保底方案

target_model_name = get_best_model()
model = genai.GenerativeModel(target_model_name)

# --- 3. 数据加载函数 ---
def load_data(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    excel_obj = pd.ExcelFile(fh)
    # 自动取最新的 Sheet 数据
    return pd.read_excel(excel_obj, sheet_name=excel_obj.sheet_names[-1])

# --- 4. 界面布局 ---
st.title("💬 智投数据专家对话")
st.caption(f"当前运行模型: {target_model_name} | 模式: Paid Tier")

# 填入你之前的分板 ID
DETAIL_FILE_ID = "1xJu7ukLQ7li5jNVhdlISehkogxxvW_Vg"

# 加载数据并预览
try:
    df = load_data(DETAIL_FILE_ID)
    with st.expander("🔍 查看今日封装数据预览", expanded=False):
        st.dataframe(df.head(10), use_container_width=True)
except Exception as e:
    st.error(f"数据加载失败: {e}")
    df = pd.DataFrame() # 兜底防止后续报错

# --- 5. 核心对话区 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("基于今日数据，你想了解什么？"):
    # 记录并显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 助手回复
    with st.chat_message("assistant"):
        # 将数据作为背景上下文喂给 AI
        data_context = f"以下是今日成交额前20的标的数据：\n{df.to_string(index=False)}\n\n"
        full_prompt = f"{data_context}请回答用户问题：{prompt}"
        
        try:
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"对话生成失败: {e}")
