import streamlit as st
import pandas as pd
import google.generativeai as genai
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 帝国基调与样式配置 ---
st.set_page_config(page_title="赛博大明·智投决策中心", layout="wide")

# 注入 CSS：确保滚动条可用，并美化重臣奏折区域
st.markdown("""
    <style>
    .stMain { overflow-y: auto !important; }
    .stChatMessageContainer { overflow-y: auto !important; }
    .minister-box { 
        padding: 20px; 
        border-radius: 10px; 
        border: 1px solid #d4af37; 
        background-color: #fcfaf2; 
        color: #333;
        line-height: 1.6;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 令牌与权限初始化 ---
# 必须在 Secrets 中配置：GCP_SERVICE_ACCOUNT_JSON, GEMINI_API_KEY, DEEPSEEK_API_KEY
gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(gcp_info)
drive_service = build('drive', 'v3', credentials=credentials)

# 初始化内阁大臣 (Gemini)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 初始化锦衣卫 (DeepSeek)
deepseek_client = OpenAI(
    api_key=st.secrets["DEEPSEEK_API_KEY"], 
    base_url="https://api.deepseek.com"
)

# --- 3. 档案库文件夹 ID ---
FOLDER_IDS = {
    "总榜文件夹": "1AeX5t-DngAZaVPpIJogEpU0M9-Q_bNj0",
    "分板数据仓": "1xJu7ukLQ7li5jNVhdlISehkogxxvW_Vg"
}

# --- 4. 递归扫描 CSV 奏章 ---
def get_all_csv_recursive(folder_id):
    all_files = []
    # 查找当前目录下所有 CSV
    query = f"'{folder_id}' in parents and mimeType = 'text/csv'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    all_files.extend(results.get('files', []))
    
    # 查找子文件夹并递归扫描
    folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    folder_results = drive_service.files().list(q=folder_query, fields="files(id, name)").execute()
    for sub in folder_results.get('files', []):
        all_files.extend(get_all_csv_recursive(sub['id']))
    return all_files

@st.cache_data(ttl=3600)
def fetch_imperial_knowledge():
    full_text = ""
    file_names = []
    for f_type, f_id in FOLDER_IDS.items():
        files = get_all_csv_recursive(f_id)
        for f in files:
            file_names.append(f"{f_type} -> {f['name']}")
            try:
                request = drive_service.files().get_media(fileId=f['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: _, done = downloader.next_chunk()
                fh.seek(0)
                # 使用 utf-8-sig 兼容中文
                df = pd.read_csv(fh, encoding='utf-8-sig')
                full_text += f"\n### 奏章名称：{f['name']} ###\n{df.to_string(index=False)}\n"
            except Exception as e:
                st.warning(f"无法读取奏章 {f['name']}: {e}")
    return full_text, file_names

# --- 5. 交互逻辑 ---
st.title("🏮 赛博大明·双臣廷议系统")

with st.sidebar:
    st.header("⚙️ 司礼监日常")
    if st.button("🔄 宣：同步最新奏章", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.subheader("📂 已挂载奏章清单")
    knowledge_context, files_found = fetch_imperial_knowledge()
    for name in files_found:
        st.caption(f"📄 {name}")

# 点击开启上朝
if st.button("🏮 宣：文武百官上朝议事", use_container_width=True):
    tab1, tab2 = st.tabs(["📜 内阁首辅 (Gemini)", "🦅 锦衣卫 (DeepSeek)"])
    
    with tab1:
        st.subheader("内阁首辅意见 (深度分析)")
        with st.spinner("首辅拟票中..."):
            try:
                # 关键修正：添加 models/ 前缀防止 NotFound
                m = genai.GenerativeModel('models/gemini-1.5-pro')
                prompt = f"你现在的身份是大明内阁首辅。请基于以下奏章数据，复盘今日 A 股行情逻辑：\n{knowledge_context}"
                response = m.generate_content(prompt)
                st.markdown(f"<div class='minister-box'>{response.text}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"内阁传旨受阻：{e}")

    with tab2:
        st.subheader("锦衣卫密折 (资金刺探)")
        with st.spinner("都指挥使密探中..."):
            try:
                prompt = f"你现在的身份是大明锦衣卫都指挥使。请针对以下数据，探寻资金异动与标的风险：\n{knowledge_context}"
                res = deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.markdown(f"<div class='minister-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"锦衣卫探报受阻：{e}")

st.divider()

# --- 6. 圣裁追问区 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt_in := st.chat_input("朕还有一事不明..."):
    st.session_state.messages.append({"role": "user", "content": prompt_in})
    with st.chat_message("user"):
        st.markdown(prompt_in)
    
    with st.chat_message("assistant"):
        try:
            # 追问默认走内阁逻辑
            m = genai.GenerativeModel('models/gemini-1.5-pro')
            final_prompt = f"基于奏章：\n{knowledge_context}\n\n回答万岁爷追问：{prompt_in}"
            response = m.generate_content(final_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"回复失败：{e}")
