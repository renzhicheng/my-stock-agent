import streamlit as st
import pandas as pd
import google.generativeai as genai
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 样式与配置 ---
st.set_page_config(page_title="赛博大明·双臣版", layout="wide")

st.markdown("""
    <style>
    .stMain { overflow-y: auto !important; }
    .stChatMessageContainer { overflow-y: auto !important; }
    .minister-box { padding: 15px; border-radius: 8px; border: 2px solid #d4af37; background-color: #fcfaf2; margin-bottom: 20px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 令牌注入 (Secrets) ---
# 确保在 Streamlit Secrets 填好：GCP_SERVICE_ACCOUNT_JSON, GEMINI_API_KEY, DEEPSEEK_API_KEY
gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(gcp_info)
drive_service = build('drive', 'v3', credentials=credentials)

# 初始化内阁 (Gemini)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
# 初始化锦衣卫 (DeepSeek)
deepseek_client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")

# --- 3. 奏章档案路径 ---
FOLDER_IDS = {
    "总榜文件夹": "1AeX5t-DngAZaVPpIJogEpU0M9-Q_bNj0",
    "分板数据仓": "1xJu7ukLQ7li5jNVhdlISehkogxxvW_Vg"
}

# --- 4. 奏章提取函数 (递归扫描 CSV) ---
def get_all_csv_recursive(folder_id):
    all_files = []
    query = f"'{folder_id}' in parents and mimeType = 'text/csv'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    all_files.extend(results.get('files', []))
    
    folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    folder_results = drive_service.files().list(q=folder_query, fields="files(id, name)").execute()
    for sub in folder_results.get('files', []):
        all_files.extend(get_all_csv_recursive(sub['id']))
    return all_files

@st.cache_data(ttl=3600)
def fetch_imperial_data():
    knowledge_base = ""
    file_list = []
    for f_type, f_id in FOLDER_IDS.items():
        files = get_all_csv_recursive(f_id)
        for f in files:
            file_list.append(f"{f_type} -> {f['name']}")
            request = drive_service.files().get_media(fileId=f['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df = pd.read_csv(fh, encoding='utf-8-sig')
            knowledge_base += f"\n【文件：{f['name']}】\n{df.to_string(index=False)}\n"
    return knowledge_base, file_list

# --- 5. 交互界面 ---
st.title("🏮 赛博大明·双臣廷议系统")

with st.sidebar:
    st.header("⚙️ 司礼监日常")
    if st.button("🔄 宣：同步最新奏章", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.subheader("📂 已呈递清单")
    knowledge, files = fetch_imperial_data()
    for f in files:
        st.caption(f"📄 {f}")

# 上朝廷议
if st.button("🏮 开启双臣对话", use_container_width=True):
    tab1, tab2 = st.tabs(["📜 内阁 (Gemini)", "🦅 锦衣卫 (DeepSeek)"])
    
    with tab1:
        st.subheader("内阁首辅意见 (全量深度复盘)")
        with st.spinner("首辅拟票中..."):
            m = genai.GenerativeModel('gemini-1.5-pro')
            prompt = f"你现在的身份是大明内阁首辅。当前日期是 2026年5月12日。请基于以下全量 A股数据进行复盘，指出核心行业逻辑：\n{knowledge}"
            response = m.generate_content(prompt)
            st.markdown(f"<div class='minister-box'>{response.text}</div>", unsafe_allow_html=True)

    with tab2:
        st.subheader("锦衣卫密折 (资金流向刺探)")
        with st.spinner("锦衣卫密探中..."):
            prompt = f"你现在的身份是大明锦衣卫都指挥使。请针对以下数据，刺探盘面中诡谲的资金动向和标的异常，给出密折：\n{knowledge}"
            response = deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )
            st.markdown(f"<div class='minister-box'>{response.choices[0].message.content}</div>", unsafe_allow_html=True)

st.divider()
# 自由对话区
if "messages" not in st.session_state: st.session_state.messages = []
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

if prompt := st.chat_input("朕还有话要问..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        # 追问默认走 Gemini
        m = genai.GenerativeModel('gemini-1.5-pro')
        response = m.generate_content(f"基于数据：\n{knowledge}\n回答追问：{prompt}")
        st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
