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
st.set_page_config(page_title="赛博大明·廷议接龙", layout="wide")

st.markdown("""
    <style>
    .report-card { 
        padding: 25px; border-radius: 15px; margin-bottom: 25px; border-left: 10px solid #d4af37;
        background-color: #fcfaf2; box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .cabinet-header { color: #8b0000; font-size: 1.5rem; font-weight: bold; margin-bottom: 10px; }
    .jinyiwei-header { color: #2f4f4f; font-size: 1.5rem; font-weight: bold; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 权限初始化 (保持不变) ---
try:
    gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(gcp_info)
    drive_service = build('drive', 'v3', credentials=credentials)
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    deepseek_client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
except Exception as e:
    st.error(f"❌ 司礼监初始化异常：{e}")

# --- 3. 核心工具函数 (保持不变) ---
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
    ids = {"总榜文件夹": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t", "分板数据仓": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"}
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
                kb += f"\n【奏章：{f['name']}】\n{df.to_string(index=False)}\n"
            except: continue
    return kb, fl

def get_best_gemini():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = [m for m in models if 'flash' in m.lower()]
        return sorted(flash, reverse=True)[0] if flash else 'models/gemini-1.5-flash'
    except: return 'models/gemini-1.5-flash'

# --- 4. 专业级廷议 Prompt (接龙专用) ---

CABINET_PROMPT = """你是一位顶级的金融【宏观策略分析师】。
任务：请基于 A 股全量奏章数据，进行深度复盘。
要求：重点分析板块轮动逻辑与行业基本面，给出专业的研判结论。
风格：严禁使用古风，保持现代、干练。"""

JINYIWEI_PROMPT = """你是一位顶级的金融【量化资金面分析师】。
任务：
1. 审核并刺探原始数据中的异动（主力轨迹、异常标的）。
2. 【核心任务】参考并评估刚才“内阁首辅”给出的分析结论。指出他是否遗漏了资金面的博弈细节，或者是否被表象迷惑。
要求：像情报员一样冷酷犀利，发现风险请标记为【红色警告】。
风格：严禁使用古风。"""

# --- 5. 界面逻辑 ---

st.title("🏮 赛博大明·双臣廷议链")

with st.sidebar:
    st.header("⚙️ 档案库")
    if st.button("🔄 宣：同步最新奏章", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    knowledge, files = fetch_imperial_data()
    st.success(f"已录入 {len(files)} 份奏章")

# 廷议主流程
if st.button("🏮 宣：文武百官廷议接龙", use_container_width=True):
    
    # --- 第一阶段：内阁发言 ---
    with st.container():
        st.markdown("<div class='cabinet-header'>📜 第一篇：内阁首辅 (Gemini) 宏观复盘</div>", unsafe_allow_html=True)
        with st.spinner("首辅正在拟票..."):
            try:
                m = genai.GenerativeModel(get_best_gemini())
                cabinet_res = m.generate_content(f"{CABINET_PROMPT}\n\n奏章数据：\n{knowledge}")
                cabinet_output = cabinet_res.text
                st.markdown(f"<div class='report-card'>{cabinet_output}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"内阁传旨受阻：{e}")
                cabinet_output = "（内阁因故未能发表意见）"

    # --- 第二阶段：锦衣卫发言 (依赖第一阶段结论) ---
    with st.container():
        st.markdown("<div class='jinyiwei-header'>🦅 第二篇：锦衣卫 (DeepSeek) 资金刺探与审计</div>", unsafe_allow_html=True)
        with st.spinner("都指挥使正在秘密复核..."):
            try:
                # 核心：将 Gemini 的结论喂给 DeepSeek
                combined_prompt = f"""
                【参考内阁结论】：
                {cabinet_output}
                
                【原始数据】：
                {knowledge}
                
                【执行指令】：
                {JINYIWEI_PROMPT}
                """
                res = deepseek_client.chat.completions.create(
                    model="deepseek-v4-pro", # 或使用 deepseek-chat
                    messages=[{"role": "user", "content": combined_prompt}],
                    temperature=0.3
                )
                st.markdown(f"<div class='report-card'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"锦衣卫探报受阻：{e}")

st.divider()
# 追问区（略，保持原样即可）
