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
st.set_page_config(page_title="赛博大明·智投金銮殿", layout="wide")

st.markdown("""
    <style>
    .stMain { overflow-y: auto !important; }
    .stChatMessageContainer { overflow-y: auto !important; }
    .minister-box { 
        padding: 20px; 
        border-radius: 10px; 
        border: 2px solid #d4af37; 
        background-color: #fcfaf2; 
        margin-bottom: 20px; 
        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 令牌与权限初始化 ---
# 确保在 Streamlit Secrets 填好：GCP_SERVICE_ACCOUNT_JSON, GEMINI_API_KEY, DEEPSEEK_API_KEY
try:
    gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(gcp_info)
    drive_service = build('drive', 'v3', credentials=credentials)

    # 令牌 A：内阁 (Gemini 3 Flash)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

    # 令牌 B：锦衣卫 (DeepSeek)
    deepseek_client = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"], 
        base_url="https://api.deepseek.com"
    )
except Exception as e:
    st.error(f"❌ 司礼监配置错误：{e}")

# --- 3. 档案库配置 ---
FOLDER_IDS = {
    "总榜文件夹": "1AeX5t-DngAZaVPpIJogEpU0M9-Q_bNj0",
    "分板数据仓": "1xJu7ukLQ7li5jNVhdlISehkogxxvW_Vg"
}

# --- 4. 奏章提取逻辑 (全量递归扫描 CSV) ---
def get_all_csv_recursive(folder_id):
    all_files = []
    # 查找 CSV 文件
    query = f"'{folder_id}' in parents and mimeType = 'text/csv'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    all_files.extend(results.get('files', []))
    
    # 查找子文件夹并递归
    folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    folder_results = drive_service.files().list(q=folder_query, fields="files(id, name)").execute()
    for sub in folder_results.get('files', []):
        all_files.extend(get_all_csv_recursive(sub['id']))
    return all_files

@st.cache_data(ttl=3600)
def fetch_imperial_data():
    knowledge_base = ""
    file_list_display = []
    for folder_name, f_id in FOLDER_IDS.items():
        files = get_all_csv_recursive(f_id)
        for f in files:
            file_list_display.append(f"{folder_name} -> {f['name']}")
            try:
                request = drive_service.files().get_media(fileId=f['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: _, done = downloader.next_chunk()
                fh.seek(0)
                # 读取 CSV
                df = pd.read_csv(fh, encoding='utf-8-sig')
                knowledge_base += f"\n### 奏章名称：{f['name']} ###\n{df.to_string(index=False)}\n"
            except Exception as e:
                st.warning(f"跳过损毁奏章 {f['name']}: {e}")
    return knowledge_base, file_list_display

# --- 5. 交互界面 ---
st.title("🏮 赛博大明·智投金銮殿")

with st.sidebar:
    st.header("⚙️ 司礼监管理")
    if st.button("🔄 宣：全量同步奏章", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    st.subheader("📂 在库奏章清单")
    knowledge, files = fetch_imperial_data()
    for f_name in files:
        st.caption(f"📄 {f_name}")

# 点击开启“上朝”
if st.button("🏮 宣：文武百官上朝议事", use_container_width=True):
    tab1, tab2 = st.tabs(["📜 内阁 (Gemini 3 Flash)", "🦅 锦衣卫 (DeepSeek)"])
    
    with tab1:
    st.subheader("内阁首辅意见 (动态选才版)")
    with st.spinner("首辅拟票中..."):
        try:
            # --- 动态寻才逻辑：不再猜名字，直接现场点名 ---
            available_models = [
                m.name for m in genai.list_models() 
                if 'generateContent' in m.supported_generation_methods
                and 'flash' in m.name.lower()  # 只要是 Flash 家族的
            ]
            
            if not available_models:
                # 兜底：如果列表落空，尝试最经典的稳定版官衔
                target_model = 'models/gemini-1.5-flash'
            else:
                # 排序取最新：比如列表中有 1.5, 2.0, 3.0，取最新那个
                target_model = sorted(available_models, reverse=True)[0]
            
            # --- 正式传旨 ---
            m = genai.GenerativeModel(target_model)
            prompt_text = f"你现在的身份是大明内阁首辅。请基于以下全量奏章数据，给出复盘意见：\n{knowledge}"
            
            response = m.generate_content(prompt_text)
            
            st.markdown(f"<div class='minister-box'>{response.text}</div>", unsafe_allow_html=True)
            st.caption(f"✨ 内阁首辅已到任。当前使用的御赐官衔为：`{target_model}`")
            
        except Exception as e:
            st.error(f"❌ 内阁传旨再次受阻。臣有罪，错误详情：{e}")
            st.info("💡 建议：请确保 Google AI Studio 的 API Key 已正确配置在 Streamlit Secrets 中。")

    with tab2:
        st.subheader("锦衣卫密折 (资金动态刺探)")
        with st.spinner("都指挥使密探中..."):
            try:
                prompt = f"你现在的身份是大明锦衣卫都指挥使。请针对以下数据刺探异常资金：\n{knowledge}"
                res = deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.markdown(f"<div class='minister-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)
                st.caption("✨ 此回复由锦衣卫 DeepSeek-V3 呈递")
            except Exception as e:
                st.error(f"锦衣卫探报受阻：{e}")

st.divider()

# --- 6. 圣裁追问区 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if user_input := st.chat_input("朕还有一事不明..."):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    
    with st.chat_message("assistant"):
        try:
            # 追问同样走 Gemini 3 Flash
            m = genai.GenerativeModel('models/gemini-3-flash')
            final_prompt = f"基于以下知识库数据：\n{knowledge}\n\n回答万岁爷的追问：{user_input}"
            response = m.generate_content(final_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"回复失败：{e}")
