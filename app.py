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

@st.cache_data(ttl=600)
def fetch_imperial_data():
    kb, fl = "", []
    # 🚨 已应用万岁爷最新的 ID 🚨
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
                fh = io.BytesIO(); downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: _, done = downloader.next_chunk()
                fh.seek(0); df = pd.read_csv(fh, encoding='utf-8-sig')
                kb += f"\n【文件：{f['name']}】\n{df.to_string(index=False)}\n"
            except: continue
    return kb, fl

@st.cache_resource
def get_best_model():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = [m for m in models if 'flash' in m.lower()]
        return sorted(flash, reverse=True)[0] if flash else 'models/gemini-1.5-flash'
    except: return 'models/gemini-1.5-flash'

# --- 4. 历史记录初始化 ---
# 关键：创建一个 history 列表，用来存储每一次互动的“全家桶”
if "decree_history" not in st.session_state:
    st.session_state.decree_history = []

# --- 5. 界面逻辑 ---
st.title("🏮 赛博大明·智投决策中心")

with st.sidebar:
    st.header("⚙️ 档案库")
    if st.button("🔄 同步并清空记录", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.session_state.decree_history = []
        st.rerun()
    st.divider()
    knowledge, files = fetch_imperial_data()
    st.success(f"已录入 {len(files)} 份奏章")
    for f in files: st.caption(f"📄 {f}")

# --- 6. 圣旨发布区 ---
st.subheader("📝 宣旨与批复")
user_input = st.chat_input("朕有旨意（例如：复盘今日成交额前十，对比昨日异动）...")

if user_input:
    # 这一步会触发 AI 计算，并将结果打包存入历史
    with st.status("重臣正在接旨商议中...") as status:
        try:
            # 1. 内阁首辅 (Gemini) 响应
            st.write("内阁正在拟票...")
            m_name = get_best_model()
            m = genai.GenerativeModel(m_name)
            cab_p = f"你是一位顶级金融策略分析师。万岁爷旨意：{user_input}\n数据：\n{knowledge}\n请给出宏观与板块分析，严禁文言文。"
            cab_res = m.generate_content(cab_p).text
            
            # 2. 锦衣卫 (DeepSeek) 审计
            st.write("锦衣卫正在审计...")
            j_p = f"你是一位量化资金面分析师。参考内阁意见：{cab_res}\n旨意：{user_input}\n数据：\n{knowledge}\n请指出内阁遗漏的资金博弈细节，犀利指出风险。"
            j_res = deepseek_client.chat.completions.create(
                model="deepseek-v4-pro", # 或 deepseek-chat
                messages=[{"role": "user", "content": j_p}]
            ).choices[0].message.content
            
            # 3. 将这一组对话存入历史记录
            st.session_state.decree_history.append({
                "decree": user_input,
                "cabinet": cab_res,
                "jinyiwei": j_res
            })
            status.update(label="✅ 朝议完毕", state="complete")
        except Exception as e:
            st.error(f"传旨异常: {e}")

# --- 7. 渲染全量历史记录 ---
# 像“帖子列表”一样，从旧到新展示所有互动
for idx, entry in enumerate(st.session_state.decree_history):
    # 展示圣旨
    st.markdown(f"<div class='decree-box'>第 {idx+1} 议 · 奉天承运：{entry['decree']}</div>", unsafe_allow_html=True)
    
    # 展示内阁回复
    st.markdown("<span class='header-text'>📜 内阁首辅 (Gemini) 复盘意见</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card cabinet-border'>{entry['cabinet']}</div>", unsafe_allow_html=True)
    
    # 展示锦衣卫回复
    st.markdown("<span class='header-text'>🦅 锦衣卫 (DeepSeek) 资金刺探</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card jinyiwei-border'>{entry['jinyiwei']}</div>", unsafe_allow_html=True)
    
    st.divider()

if not st.session_state.decree_history:
    st.info("💡 请在下方输入框中发布首道圣旨，开启今日廷议。")

if not st.session_state.decree_history:
    st.info("💡 请在下方输入框中发布圣旨。")

if not st.session_state.decree_history:
    st.info("💡 请在下方输入框中发布首道圣旨，开启今日廷议。")
