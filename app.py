import streamlit as st
import pandas as pd
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 样式配置 ---
st.set_page_config(page_title="赛博大明·圣旨决策链", layout="wide")

st.markdown("""
    <style>
    .report-card { 
        padding: 25px; border-radius: 15px; margin-bottom: 25px; 
        background-color: #fcfaf2; box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
    }
    .cabinet-border { border-left: 10px solid #8b0000; }
    .jinyiwei-border { border-left: 10px solid #2f4f4f; }
    .emperor-decree { 
        background-color: #fffde7; padding: 15px; border-radius: 10px; 
        border: 2px dashed #d4af37; margin-bottom: 20px; color: #5d4037; font-weight: bold;
    }
    .header-text { font-size: 1.2rem; font-weight: bold; margin-bottom: 12px; display: block; }
    .history-divider { border-top: 2px solid #e0e0e0; margin: 40px 0; }
    </style>
""", unsafe_allow_html=True)

# --- 新增：初始化会话状态 (Session State) ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- 2. 权限初始化 ---
try:
    gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(gcp_info)
    drive_service = build('drive', 'v3', credentials=credentials)
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
                kb += f"\n【文件：{f['name']}】\n{df.to_string(index=False)}\n"
            except: continue
    return kb, fl

def ask_deepseek(system_prompt, user_content, model="deepseek-chat", temp=0.3):
    response = deepseek_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        temperature=temp
    )
    return response.choices[0].message.content

# --- 4. 界面逻辑 ---
st.title("🏮 赛博大明·智投决策中心")

with st.sidebar:
    st.header("⚙️ 档案库管理")
    if st.button("🔄 同步最新奏章", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("🧹 清理朝堂记录", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    st.divider()
    knowledge, files = fetch_imperial_data()
    st.success(f"已录入 {len(files)} 份数据")
    for f in files: st.caption(f"📄 {f}")

# --- 5. 宣旨与历史记录展示区 ---
st.subheader("📝 朝堂议政记录")

# 步骤 A：渲染过往的所有历史记录
for i, turn in enumerate(st.session_state.chat_history):
    st.markdown(f"<div class='emperor-decree'>奉天承运，皇帝诏曰：{turn['decree']}</div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1]) # 让历史记录可以并排或上下显示，这里保持上下结构以保证阅读体验
    st.markdown(f"""
        <div class='report-card cabinet-border'>
            <span class='header-text'>📜 第一议：内阁首辅 (宏观复盘)</span>
            {turn['cabinet']}
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
        <div class='report-card jinyiwei-border'>
            <span class='header-text'>🦅 第二议：锦衣卫 (资金刺探与审计)</span>
            {turn['jinyiwei']}
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)

# 步骤 B：处理新的旨意输入
user_decree = st.chat_input("朕有旨意（例如：复盘今日成交额前十、分析半导体异动等）...")

if user_decree:
    # 立即在界面最下方渲染当前最新的问题
    st.markdown(f"<div class='emperor-decree'>奉天承运，皇帝诏曰：{user_decree}</div>", unsafe_allow_html=True)
    
    cabinet_output = ""
    jinyiwei_output = ""

    # --- 第一步：内阁接旨 ---
    with st.container():
        with st.spinner("首辅正在针对旨意拟票..."):
            try:
                cabinet_sys = "你是一位顶级的金融【宏观策略分析师】，现在正在扮演明朝内阁首辅处理政务。"
                cabinet_prompt = f"【万岁爷的旨意】：{user_decree}\n【原始奏章数据】：{knowledge}\n请基于上述数据和旨意进行专业分析，重点关注板块轮动逻辑、大盘宏观趋势。要求：严禁使用文言文，保持现代金融专业口吻，以宏观大局观为主。"
                cabinet_output = ask_deepseek(system_prompt=cabinet_sys, user_content=cabinet_prompt)
                st.markdown(f"<div class='report-card cabinet-border'><span class='header-text'>📜 第一议：内阁首辅 (宏观复盘)</span>{cabinet_output}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"内阁传旨受阻：{e}")
                cabinet_output = "内阁未能给出有效研判。"

    # --- 第二步：锦衣卫领命 ---
    with st.container():
        with st.spinner("都指挥使正在根据内阁结论进行复核与资金刺探..."):
            try:
                jinyiwei_sys = "你是一位顶级的金融【量化资金面分析师】，现在扮演明朝锦衣卫指挥使，负责暗查资金异动并审计内阁的言论。"
                jinyiwei_prompt = f"【万岁爷的旨意】：{user_decree}\n【内阁首辅的初步分析】：{cabinet_output}\n【原始奏章数据】：{knowledge}\n指令：\n1. 针对万岁爷的旨意，通过数据刺探主力资金轨迹、异动标的。\n2. 审计内阁首辅的宏观结论，指出遗漏或更正错误。\n要求：风格专业、冷静、犀利。严禁使用文言文。"
                jinyiwei_output = ask_deepseek(system_prompt=jinyiwei_sys, user_content=jinyiwei_prompt, temp=0.2)
                st.markdown(f"<div class='report-card jinyiwei-border'><span class='header-text'>🦅 第二议：锦衣卫 (资金刺探与审计)</span>{jinyiwei_output}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"锦衣卫探报受阻：{e}")
                jinyiwei_output = "锦衣卫未能给出有效探报。"

    # --- 步骤 C：将本次完整的对话存入历史记录 ---
    st.session_state.chat_history.append({
        "decree": user_decree,
        "cabinet": cabinet_output,
        "jinyiwei": jinyiwei_output
    })
    
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)
elif len(st.session_state.chat_history) == 0:
    st.info("💡 请在下方输入框中下达旨意，开启今日廷议。")
