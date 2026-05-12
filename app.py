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
    .report-card { padding: 25px; border-radius: 15px; margin-bottom: 25px; background-color: #fcfaf2; border-left: 10px solid #d4af37; color: #333; }
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
    st.error(f"❌ 司礼监配置异常：{e}")

# --- 3. 核心功能函数 (加入缓存逻辑) ---
@st.cache_resource
def get_cached_gemini_model():
    """将点将结果缓存，避免重复宣召"""
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = [m for m in models if 'flash' in m.lower()]
        return sorted(flash, reverse=True)[0] if flash else 'models/gemini-1.5-flash'
    except:
        return 'models/gemini-1.5-flash'

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

@st.cache_data(ttl=600) # 缩短缓存时间，确保能读到新奏章
def fetch_imperial_data():
    kb, fl = "", []
    ids = {"总榜文件夹": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t", "分板数据仓": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"}
    for f_type, f_id in ids.items():
        files = get_all_csv_recursive(f_id)
        for f in files:
            fl.append(f"{f_type} -> {f['name']}")
            try:
                request = drive_service.files().get_media(fileId=f['id'])
                fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: _, done = downloader.next_chunk()
                fh.seek(0); df = pd.read_csv(fh, encoding='utf-8-sig')
                kb += f"\n【奏章：{f['name']}】\n{df.to_string(index=False)}\n"
            except: continue
    return kb, fl

# --- 4. 状态初始化 ---
if "cab_res" not in st.session_state: st.session_state.cab_res = ""
if "jiy_res" not in st.session_state: st.session_state.jiy_res = ""
if "chat_log" not in st.session_state: st.session_state.chat_log = []

# --- 5. 侧边栏 ---
with st.sidebar:
    st.title("🏮 赛博大明")
    if st.button("🔄 同步奏章", type="primary"):
        st.cache_data.clear()
        st.session_state.cab_res = ""; st.session_state.jiy_res = ""; st.session_state.chat_log = []
        st.rerun()
    knowledge, files = fetch_imperial_data()
    st.success(f"已录入 {len(files)} 份奏章")

# --- 6. 廷议按钮 ---
if st.button("🏮 宣：文武百官上朝议事", use_container_width=True):
    # 第一阶段：内阁 (Gemini)
    with st.status("内阁首辅正在审阅奏章...", expanded=True) as status:
        try:
            m_name = get_cached_gemini_model()
            st.write(f"已锁定官阶：{m_name}")
            m = genai.GenerativeModel(m_name)
            
            # 数据量预警
            if len(knowledge) > 30000:
                st.write("⚠️ 奏章堆积如山（数据量大），首辅批复可能稍慢...")
            
            st.write("正在撰写复盘研报...")
            prompt = f"你是一位顶级宏观策略分析师。请基于以下奏章数据进行专业深度复盘：\n{knowledge}"
            res = m.generate_content(prompt)
            st.session_state.cab_res = res.text
            status.update(label="✅ 内阁复盘完毕", state="complete")
        except Exception as e:
            st.error(f"内阁受阻：{e}")

    # 第二阶段：锦衣卫 (DeepSeek)
    if st.session_state.cab_res:
        with st.status("锦衣卫正在密核数据...") as status:
            try:
                j_p = f"你是一位量化分析师。参考内阁分析：{st.session_state.cab_res}\n数据：{knowledge}\n请指出内阁遗漏的资金面细节。"
                res = deepseek_client.chat.completions.create(model="deepseek-v4-pro", messages=[{"role": "user", "content": j_p}])
                st.session_state.jiy_res = res.choices[0].message.content
                status.update(label="✅ 锦衣卫刺探完毕", state="complete")
            except Exception as e:
                st.error(f"锦衣卫受阻：{e}")

# --- 7. 展示与对话 ---
if st.session_state.cab_res:
    st.markdown("<span class='header-text'>📜 内阁复盘报告</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card'>{st.session_state.cab_res}</div>", unsafe_allow_html=True)

if st.session_state.jiy_res:
    st.markdown("<span class='header-text'>🦅 锦衣卫密折</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card' style='border-left:10px solid #2f4f4f;'>{st.session_state.jiy_res}</div>", unsafe_allow_html=True)

    st.divider(); st.subheader("💬 圣裁互动")
    for chat in st.session_state.chat_log:
        with st.chat_message(chat["role"]): st.markdown(chat["content"])

    if ask := st.chat_input("朕还有话要问..."):
        st.session_state.chat_log.append({"role": "user", "content": ask})
        with st.chat_message("user"): st.markdown(ask)
        with st.chat_message("assistant"):
            try:
                m = genai.GenerativeModel(get_cached_gemini_model())
                res = m.generate_content(f"基于奏章：\n{knowledge}\n及复盘：\n{st.session_state.jiy_res}\n回答：{ask}")
                st.markdown(res.text); st.session_state.chat_log.append({"role": "assistant", "content": res.text})
            except Exception as e: st.error(f"对话受阻：{e}")
