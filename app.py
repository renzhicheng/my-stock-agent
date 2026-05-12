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
    }
    .cabinet-border { border-left: 10px solid #8b0000; }
    .jinyiwei-border { border-left: 10px solid #2f4f4f; }
    .header-text { font-size: 1.2rem; font-weight: bold; margin-bottom: 8px; display: block; }
    .chat-bubble { padding: 15px; border-radius: 10px; margin-bottom: 10px; }
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
    # 🚨 已更新为万岁爷提供的新 ID 🚨
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
                kb += f"\n【奏章：{f['name']}】\n{df.to_string(index=False)}\n"
            except: continue
    return kb, fl

def get_best_gemini():
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        flash = [m for m in models if 'flash' in m.lower()]
        return sorted(flash, reverse=True)[0] if flash else 'models/gemini-1.5-flash'
    except: return 'models/gemini-1.5-flash'

# --- 4. 状态保持 ---
if "cabinet_report" not in st.session_state: st.session_state.cabinet_report = ""
if "jinyiwei_report" not in st.session_state: st.session_state.jinyiwei_report = ""
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# --- 5. 界面展示 ---
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

# --- 6. 朝议大典按钮 ---
if st.button("🏮 宣：文武百官上朝议事 (全量初始复盘)", use_container_width=True):
    # 第一步：内阁宏观复盘
    with st.status("内阁首辅正在拟票...") as status:
        try:
            m = genai.GenerativeModel(get_best_gemini())
            cab_prompt = f"你是一位顶级宏观策略分析师。请基于以下全量 A 股奏章数据进行深度复盘：\n{knowledge}"
            res = m.generate_content(cab_prompt)
            st.session_state.cabinet_report = res.text
            status.update(label="内阁复盘完毕", state="complete")
        except Exception as e:
            st.error(f"内阁受阻: {e}")

    # 第二步：锦衣卫资金刺探
    with st.status("锦衣卫正在秘密复核...") as status:
        try:
            j_prompt = f"""
            你是一位顶级量化资金面分析师。
            【内阁结论】：{st.session_state.cabinet_report}
            【原始奏章数据】：{knowledge}
            指令：参考内阁结论并刺探数据中的主力异常轨迹，指出内阁遗漏的细节。
            """
            res = deepseek_client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[{"role": "user", "content": j_prompt}]
            )
            st.session_state.jinyiwei_report = res.choices[0].message.content
            status.update(label="锦衣卫刺探完毕", state="complete")
        except Exception as e:
            st.error(f"锦衣卫受阻: {e}")

# --- 7. 渲染朝议结果 ---
if st.session_state.cabinet_report:
    st.markdown("<span class='header-text'>📜 内阁首辅 (Gemini) 宏观复盘</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card cabinet-border'>{st.session_state.cabinet_report}</div>", unsafe_allow_html=True)

if st.session_state.jinyiwei_report:
    st.markdown("<span class='header-text'>🦅 锦衣卫 (DeepSeek) 资金刺探与审计</span>", unsafe_allow_html=True)
    st.markdown(f"<div class='report-card jinyiwei-border'>{st.session_state.jinyiwei_report}</div>", unsafe_allow_html=True)

# --- 8. 互动批复区 ---
st.divider()
if st.session_state.jinyiwei_report:
    st.subheader("💬 圣裁与对话")
    
    # 展示历史对话
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    if prompt := st.chat_input("朕还有一事不明..."):
        # 用户提问
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        # 重臣联合回答
        with st.chat_message("assistant"):
            with st.spinner("重臣商议中..."):
                try:
                    # 追问逻辑：内阁先答，锦衣卫补充
                    m = genai.GenerativeModel(get_best_gemini())
                    follow_up_prompt = f"""
                    【背景】：之前的复盘结论和奏章数据已存在。
                    【内阁结论】：{st.session_state.cabinet_report}
                    【锦衣卫结论】：{st.session_state.jinyiwei_report}
                    【皇帝追问】：{prompt}
                    请以专业分析师的身份回答，先由内阁给出逻辑，再由锦衣卫指出风险或资金细节。
                    """
                    res = m.generate_content(follow_up_prompt)
                    ans = res.text
                    st.markdown(ans)
                    st.session_state.chat_history.append({"role": "assistant", "content": ans})
                except Exception as e:
                    st.error(f"对话受阻: {e}")
else:
    st.info("💡 请先点击上方【宣：文武百官上朝议事】获取今日复盘，随后即可进行圣裁互动。")
else:
    st.info("💡 请在下方输入框中下达旨意，开启今日廷议。")

st.divider()
