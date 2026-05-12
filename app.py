import streamlit as st
import pandas as pd
import google.generativeai as genai
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from concurrent.futures import ThreadPoolExecutor
import io
import json

# --- 1. 样式配置 ---
st.set_page_config(page_title="赛博大明·决策链", layout="wide")

st.markdown("""
    <style>
    .decree-box { 
        background-color: #fffde7; padding: 15px; border: 2px dashed #d4af37; 
        border-radius: 10px; margin-top: 30px; margin-bottom: 10px; color: #5d4037; font-weight: bold;
    }
    .report-card { 
        padding: 20px; border-radius: 12px; margin-bottom: 20px; 
        background-color: #fcfaf2; box-shadow: 2px 2px 8px rgba(0,0,0,0.05); color: #333;
    }
    .cabinet-border { border-left: 8px solid #8b0000; }
    .jinyiwei-border { border-left: 8px solid #2f4f4f; }
    .header-text { font-size: 1.1rem; font-weight: bold; margin-bottom: 8px; display: block; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 权限初始化 (增加错误捕获) ---
try:
    if "GCP_SERVICE_ACCOUNT_JSON" not in st.secrets:
        st.error("❌ 缺少 GCP_SERVICE_ACCOUNT_JSON 密钥")
    gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(gcp_info)
    drive_service = build('drive', 'v3', credentials=credentials)
    
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    deepseek_client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
except Exception as e:
    st.error(f"⚠️ 密钥解析或 API 初始化失败: {e}")

# --- 3. 核心功能函数 ---
def get_all_csv_recursive(folder_id):
    all_files = []
    query = f"'{folder_id}' in parents and (name contains '.csv' or mimeType = 'text/csv')"
    try:
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        all_files.extend(results.get('files', []))
        folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
        folder_results = drive_service.files().list(q=folder_query, fields="files(id, name)").execute()
        for sub in folder_results.get('files', []):
            all_files.extend(get_all_csv_recursive(sub['id']))
    except: pass
    return all_files

@st.cache_data(ttl=600)
def fetch_imperial_data():
    kb_list = []
    fl = []
    ids = {
        "总榜": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t", 
        "分板": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"
    }
    
    all_tasks = []
    for f_type, f_id in ids.items():
        files = get_all_csv_recursive(f_id)
        for f in files:
            all_tasks.append((f, f_type))

    def download_one_file(task):
        f, f_type = task
        try:
            request = drive_service.files().get_media(fileId=f['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done: _, done = downloader.next_chunk()
            fh.seek(0)
            df = pd.read_csv(fh, encoding='utf-8-sig')
            # 放弃 markdown 模式，直接用 to_string 确保不依赖外部库
            content = f"【文件：{f['name']}】\n{df.to_string(index=False)}\n"
            return content, f"{f_type} -> {f['name']}"
        except Exception as e:
            return None, str(e)

    # 降低线程数至 5，确保稳定性
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(download_one_file, all_tasks))

    for content, name in results:
        if content:
            kb_list.append(content)
            fl.append(name)
    return "".join(kb_list), fl

@st.cache_resource
def get_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = [m for m in models if 'flash' in m.lower()]
        return sorted(flash, reverse=True)[0] if flash else 'models/gemini-1.5-flash'
    except: return 'models/gemini-1.5-flash'

if "decree_history" not in st.session_state:
    st.session_state.decree_history = []

# --- 4. 界面展示 ---
st.title("🏮 赛博大明·智投决策中心")

with st.sidebar:
    st.header("⚙️ 档案库")
    if st.button("🔄 同步并清空记录"):
        st.cache_data.clear()
        st.session_state.decree_history = []
        st.rerun()
    st.divider()
    knowledge, files = fetch_imperial_data()
    if files:
        st.success(f"已录入 {len(files)} 份奏章")
        for f in files: st.caption(f"📄 {f}")
    else:
        st.warning("查无奏章，请核对 ID 权限")

# --- 5. 圣旨发布区 ---
user_input = st.chat_input("朕有旨意...")

if user_input:
    with st.status("重臣正在议事...") as status:
        try:
            m_name = get_best_model()
            m = genai.GenerativeModel(m_name)
            cab_res = m.generate_content(f"专业复盘研报。旨意：{user_input}\n数据：\n{knowledge}").text
            
            j_res = deepseek_client.chat.completions.create(
                model="deepseek-chat", # 暂时回退到稳健的 chat 代号
                messages=[{"role": "user", "content": f"量化分析。参考内阁：{cab_res}\n数据：\n{knowledge}"}]
            ).choices[0].message.content
            
            st.session_state.decree_history.append({
                "decree": user_input, "cabinet": cab_res, "jinyiwei": j_res
            })
            status.update(label="✅ 朝议完毕", state="complete")
        except Exception as e:
            st.error(

if not st.session_state.decree_history:
    st.info("💡 请在下方输入框中发布圣旨。")

if not st.session_state.decree_history:
    st.info("💡 请在下方输入框中发布首道圣旨，开启今日廷议。")
