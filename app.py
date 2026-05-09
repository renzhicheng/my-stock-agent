import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 初始化：权限与模型 ---
st.set_page_config(page_title="A股智投私域终端", layout="wide", initial_sidebar_state="collapsed")

# 安全加载 Secrets
gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(gcp_info)
drive_service = build('drive', 'v3', credentials=credentials)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

# --- 2. 核心：云端数据抓取函数 ---
def load_data_from_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.ExcelFile(fh)

# --- 3. 配置你的“封装数据” ID ---
# 请在 Google Drive 网页版打开文件，URL 中 /d/ 后面那一串就是 ID
# 你可以设置两个固定 ID，一个总榜，一个细分
# --- 封装数据 ID 配置 ---
# 总榜：用于分析全市场大势，筛选 500 亿成交额以上的板块
SECTOR_FILE_ID = "1AeX5t-DngAZaVPpIJogEpU0M9-Q_bNj0"

# 分板：用于深挖特定行业（如半导体、电力）中前 20 名的核心个股
DETAIL_FILE_ID = "1xJu7ukLQ7li5jNVhdlISehkogxxvW_Vg"

# --- 4. 主界面布局 ---
st.title("🛡️ A股智投私域看板 (Gemini 3 Flash)")

tab1, tab2 = st.tabs(["📊 自动复盘报告", "💬 专家决策咨询"])

with tab1:
    col_a, col_b = st.columns([1, 1])
    
    # 自动加载逻辑
    try:
        with st.spinner("正在同步云端封装数据..."):
            # 默认加载细分板块数据作为演示
            excel_obj = load_data_from_drive(DETAIL_FILE_ID)
            latest_sheet = excel_obj.sheet_names[-1] # 自动取最新日期
            df = pd.read_excel(excel_obj, sheet_name=latest_sheet)
            
            # 应用封装逻辑：成交额前 20
            df_filtered = df.sort_values(by='成交额', ascending=False).head(20)
            
        with col_a:
            st.subheader(f"📅 数据快照：{latest_sheet}")
            st.dataframe(df_filtered, use_container_width=True, hide_index=True)
            
        with col_b:
            st.subheader("🤖 Gemini 3 Flash 自动诊断")
            # 自动触发分析（无需点击）
            if "daily_report" not in st.session_state:
                prompt = f"分析以下成交额前20的股票数据，总结今日资金流向特征：{df_filtered.to_string()}"
                response = model.generate_content(prompt)
                st.session_state.daily_report = response.text
            
            st.markdown(st.session_state.daily_report)

    except Exception as e:
        st.error(f"云端数据连接失败，请检查 FILE_ID 是否正确。错误信息: {e}")

with tab2:
    st.subheader("💬 实时决策支持")
    # 聊天记录存储
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if chat_input := st.chat_input("输入你的问题（如：根据今日数据，半导体板块的抱团程度如何？）"):
        st.session_state.messages.append({"role": "user", "content": chat_input})
        with st.chat_message("user"):
            st.markdown(chat_input)
            
        with st.chat_message("assistant"):
            # 聊天时也会自动带入当日数据上下文
            context_prompt = f"基于今日数据：{df_filtered.to_string()}。请回答用户问题：{chat_input}"
            response = model.generate_content(context_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
