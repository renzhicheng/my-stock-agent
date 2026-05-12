import streamlit as st
import pandas as pd
import google.generativeai as genai
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 样式配置 ---
st.set_page_config(page_title="赛博大明·智投决策中心", layout="wide")

st.markdown("""
    <style>
    .report-card { 
        padding: 25px; border-radius: 15px; margin-bottom: 25px; 
        background-color: #fcfaf2; box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        color: #333; line-height: 1.6;
    }
    .cabinet-border { border-left: 10px solid #8b0000; }
    .jinyiwei-border { border-left: 10px solid #2f4f4f; }
    .header-text { font-size: 1.3rem; font-weight: bold; margin-bottom: 10px; display: block; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 权限初始化 ---
try:
    gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(gcp_info)
    drive_service = build('drive', 'v3', credentials=credentials)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    deepseek_client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
except Exception as e:
    st.error(f"❌ 司礼监初始化异常：{e}")

# --- 3. 核心工具函数 ---
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

@st.cache_data(ttl=3600)
def fetch_imperial_data():
    kb = ""
    fl = []
    # 🚨 已应用万岁爷提供的最新 ID 🚨
    ids = {
        "总榜文件夹": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t", 
        "分板数据仓": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"
    }
    for f_type, f_id in ids.items():
        files = get_all_csv_recursive(f_id)
        for f in files:
            fl.append(f"{f_type} -> {f['name']}")
            try:
                request = drive_service.files().get_media(fileId=f['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: _, done = downloader.next_chunk()
                fh.seek(0)
                df = pd.read_csv(fh, encoding='utf-8-sig')
                kb += f"\n【奏章名称：{f['name']}】\n{df.to_string(index=False)}\n"
            except: continue
    return kb, fl

def get_best_gemini():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = [m for m in models if 'flash' in m.lower()]
        return sorted(flash, reverse=True)[0] if flash else 'models/gemini-1.5-flash'
    except: return 'models/gemini-1.5-flash'

# --- 4. 状态初始化 ---
if "cabinet_report" not in st.session_state: st.session_state.cabinet_report = ""
if "jinyiwei_report" not in st.session_state: st.session_state.jinyiwei_report = ""
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# --- 5. 侧边栏 ---
st.title("🏮 赛博大明·智投决策中心")

with st.sidebar:
    st.header("⚙️ 档案库")
    if st.button("🔄 同步最新奏章", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.session_state.cabinet_report = ""
        st.session_state.jinyiwei_report = ""
        st.session_state.chat_history = []
        st.rerun()
    st.divider()
    knowledge, files = fetch_imperial_data()
    st.success(f"已录入 {len(files)} 份奏章")
    for f in files: st.caption(f"📄 {f}")

# --- 6. 廷议按钮 ---
if st.button("🏮 宣：文武百官上朝议事", use_container_width=True):
    # 第一阶段：内阁
    with st.status("内阁首辅正在复盘数据...") as s1:
        try:
            m = genai.GenerativeModel(get_best_gemini())
            p = f"你是一位顶级宏观策略分析师。请基于以下奏章数据进行专业深度复盘：\n{knowledge}"
            res = m.generate_content(p)
            st.session_state.cabinet_report = res.text
            s1.update(label="内阁复盘完成", state="complete")
        except Exception as e:
            st.error(f"内阁错误: {e}")

    # 第二阶段：锦衣卫
    if st.session_state.cabinet_report:
        with st.status("锦衣卫正在审计资金异动...") as s2:
            try:
                j_prompt = f"你是一位顶级量化分析师。参考内阁分析：{st.session_state.cabinet_report}\n基于原始数据：{knowledge}\n请指出内阁遗漏的资金面细节。"
                res = deepseek_client.chat.completions.create(
                    model="deepseek-v4-pro", # 若无权限请改为 deepseek-chat
                    messages=[{"role": "user", "content": j_prompt}]
                )
                st.session_state.jinyiwei_report = res.choices[0].message.content
                s2.update(label="锦衣卫审计完成", state="complete")
            except Exception as e:
                st.error(f"锦衣卫错误: {e}")

# --- 7. 展示区 ---
if st.session_state.cabinet_report:
    st.markdown("<span class='header-text'>📜 内阁首辅 (Gemini) 宏观复盘报告</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card cabinet-border'>{st.session_state.cabinet_report}</div>", unsafe_allow_html=True)

if st.session_state.jinyiwei_report:
    st.markdown("<span class='header-text'>🦅 锦衣卫 (DeepSeek) 资金刺探密折</span>", unsafe_allow_html=True)
    st.markdown(f
