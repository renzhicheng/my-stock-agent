import streamlit as st
import pandas as pd
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 样式配置 ---
st.set_page_config(page_title="赛博大明·圣旨", layout="wide")
st.markdown("""
    <style>
    .report-card { padding: 25px; border-radius: 15px; margin-bottom: 25px; background-color: #fcfaf2; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }
    .cabinet-border { border-left: 10px solid #8b0000; }
    .jinyiwei-border { border-left: 10px solid #2f4f4f; }
    .emperor-decree { background-color: #fffde7; padding: 15px; border-radius: 10px; border: 2px dashed #d4af37; margin-bottom: 20px; color: #5d4037; font-weight: bold; }
    .header-text { font-size: 1.2rem; font-weight: bold; margin-bottom: 12px; display: block; }
    .history-divider { border-top: 2px solid #e0e0e0; margin: 40px 0; }
    </style>
""", unsafe_allow_html=True)

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
                
                # [优化点 3]：数据截断。如果你的表很长，只取前 200 行，大幅缩减 Token。如果不需要可以注释掉。
                if len(df) > 200:
                    df = df.head(200)
                
                # [优化点 2]：改用 to_csv。消除 to_string 带来的海量空格 Token 浪费
                kb += f"\n【文件：{f['name']}】\n{df.to_csv(index=False)}\n"
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

# [优化点 1]：构建全局静态数据前缀，最大化命中 DeepSeek 的提示词缓存（Prompt Cache）
# 只要这段字符串在多次请求中一字不差地放在最前面，DeepSeek 就会自动对这部分数据进行缓存，费用极低且速度极快。
BASE_IMPERIAL_DATA_PREFIX = f"【以下是今日朝堂的固定奏章数据库，请仔细阅读，后续分析均基于此】：\n{knowledge}\n\n====================\n\n"

st.subheader("📝 朝堂议政记录")

for i, turn in enumerate(st.session_state.chat_history):
    st.markdown(f"<div class='emperor-decree'>奉天承运，皇帝诏曰：{turn['decree']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card cabinet-border'><span class='header-text'>📜 第一议：内阁首辅 (宏观复盘)</span>{turn['cabinet']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card jinyiwei-border'><span class='header-text'>🦅 第二议：锦衣卫 (资金刺探与审计)</span>{turn['jinyiwei']}</div>", unsafe_allow_html=True)
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)

user_decree = st.chat_input("朕有旨意（例如：复盘今日成交额前十、分析半导体异动等）...")

if user_decree:
    st.markdown(f"<div class='emperor-decree'>奉天承运，皇帝诏曰：{user_decree}</div>", unsafe_allow_html=True)
    cabinet_output = ""
    jinyiwei_output = ""

    with st.container():
        with st.spinner("首辅正在针对旨意拟票..."):
            try:
                # 把基础数据放在 system 提示词的最前面，接着再宣告角色
                cabinet_sys = BASE_IMPERIAL_DATA_PREFIX + "你是顶级的金融【宏观策略分析师】，正在扮演明朝内阁首辅。基于上述数据，分析板块轮动逻辑和大盘宏观趋势。严禁文言文，保持现代金融专业口吻。"
                cabinet_prompt = f"【万岁爷的旨意】：{user_decree}"
                
                cabinet_output = ask_deepseek(system_prompt=cabinet_sys, user_content=cabinet_prompt)
                st.markdown(f"<div class='report-card cabinet-border'><span class='header-text'>📜 第一议：内阁首辅 (宏观复盘)</span>{cabinet_output}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"内阁传旨受阻：{e}")

    with st.container():
        with st.spinner("都指挥使正在根据内阁结论进行复核与资金刺探..."):
            try:
                # 锦衣卫同样复用一模一样的基础数据前缀，大幅度提升缓存命中率
                jinyiwei_sys = BASE_IMPERIAL_DATA_PREFIX + "你是顶级的金融【量化资金面分析师】，正在扮演明朝锦衣卫指挥使。基于上述数据，刺探主力资金轨迹并审计内阁首辅的言论。严禁文言文，风格冷静犀利。"
                # 传入首辅的结论供锦衣卫批判
                jinyiwei_prompt = f"【万岁爷的旨意】：{user_decree}\n\n【内阁首辅的初步分析】：\n{cabinet_output}\n\n请针对旨意刺探个股异常，并指出内阁首辅宏观结论中的遗漏或错误。"
                
                jinyiwei_output = ask_deepseek(system_prompt=jinyiwei_sys, user_content=jinyiwei_prompt, temp=0.2)
                st.markdown(f"<div class='report-card jinyiwei-border'><span class='header-text'>🦅 第二议：锦衣卫 (资金刺探与审计)</span>{jinyiwei_output}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"锦衣卫探报受阻：{e}")

    st.session_state.chat_history.append({"decree": user_decree, "cabinet": cabinet_output, "jinyiwei": jinyiwei_output})
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)

elif len(st.session_state.chat_history) == 0:
    st.info("💡 请在下方输入框中下达旨意，开启今日廷议。")
