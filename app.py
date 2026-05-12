import streamlit as st
import pandas as pd
import google.generativeai as genai
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 帝国基调与样式 ---
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
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 令牌与权限初始化 ---
try:
    gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
    credentials = service_account.Credentials.from_service_account_info(gcp_info)
    drive_service = build('drive', 'v3', credentials=credentials)

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    deepseek_client = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"], 
        base_url="https://api.deepseek.com"
    )
except Exception as e:
    st.error(f"❌ 司礼监初始化失败，请检查 Secrets 配置：{e}")

# --- 3. 核心工具函数 ---

def get_all_csv_recursive(folder_id):
    """深度穿透扫描所有子目录下的 CSV 奏章"""
    all_files = []
    query = f"'{folder_id}' in parents and mimeType = 'text/csv'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    all_files.extend(results.get('files', []))
    
    folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    folder_results = drive_service.files().list(q=folder_query, fields="files(id, name)").execute()
    for sub in folder_results.get('files', []):
        all_files.extend(get_all_csv_recursive(sub['id']))
    return all_files

@st.cache_data(ttl=3600)
def fetch_imperial_data():
    """聚合全量奏章数据"""
    kb = ""
    fl = []
    ids = {
        "总榜文件夹": "1AeX5t-DngAZaVPpIJogEpU0M9-Q_bNj0",
        "分板数据仓": "1xJu7ukLQ7li5jNVhdlISehkogxxvW_Vg"
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
                kb += f"\n### 奏章：{f['name']} ###\n{df.to_string(index=False)}\n"
            except:
                continue
    return kb, fl

def get_valid_gemini_model():
    """动态获取当前可用的最强官衔"""
    try:
        # 刺探当前 API 权限下所有可用模型
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        # 优先选择 Flash 家族（速度快，额度稳）
        flash_models = [m for m in models if 'flash' in m.lower()]
        return sorted(flash_models, reverse=True)[0] if flash_models else 'models/gemini-1.5-flash'
    except:
        return 'models/gemini-1.5-flash'

# --- 4. 界面展示 ---

st.title("🏮 赛博大明·双臣廷议系统")

with st.sidebar:
    st.header("⚙️ 司礼监")
    if st.button("🔄 宣：同步最新奏章", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    knowledge, files = fetch_imperial_data()
    for f in files:
        st.caption(f"📄 {f}")

# 上朝按钮
if st.button("🏮 宣：文武百官上朝议事", use_container_width=True):
    tab1, tab2 = st.tabs(["📜 内阁 (Gemini)", "🦅 锦衣卫 (DeepSeek)"])
    
    with tab1:
        st.subheader("内阁首辅意见 (深度复盘)")
        with st.spinner("首辅拟票中..."):
            try:
                # 动态获取官衔
                model_name = get_valid_gemini_model()
                m = genai.GenerativeModel(model_name)
                prompt = f"你是一位顶级的【宏观策略分析师】。

                【核心任务】
                请基于用户提供的 A 股全量奏章（数据），进行专业的深度复盘。
                
                【分析侧重】
                1. 行业逻辑：分析今日成交额最集中的板块，解释其背后的产业逻辑或政策驱动。
                2. 跨表对比：对比不同板块的数据，指出当前市场的主流进攻方向和防守阵地。
                3. 估值研判：从基本面视角出发，判断当前放量板块的可持续性。
                
                【输出规范】
                - 语言风格：专业、干练、结构化的现代金融术语。
                - 重点信息使用加粗显示，结论要明确。"
                response = m.generate_content(prompt)
                st.markdown(f"<div class='minister-box'>{response.text}</div>", unsafe_allow_html=True)
                st.caption(f"✨ 已调遣官衔：{model_name}")
            except Exception as e:
                st.error(f"内阁传旨受阻：{e}")

    with tab2:
        st.subheader("锦衣卫密折 (资金刺探)")
        with st.spinner("锦衣卫密探中..."):
            try:
                prompt = f"你是一位极其敏锐的【量化资金面分析师】。

                【核心任务】
                请针对提供的 A 股数据，像情报员一样刺探数据背后隐藏的“筹码秘密”。
                
                【分析侧重】
                1. 异动刺探：找出成交额异常放大的个股，判断是主力建仓、机构调仓还是散户踩踏。
                2. 资金博弈：分析头部标的的换手与价格关系，揭示“聪明钱”的真实意图。
                3. 情绪监控：通过数据反馈市场的情绪水位，预警可能的流动性陷阱或情绪顶峰。
                
                【输出规范】
                - 语言风格：冷静、犀利、穿透力强的专业量化分析语言。
                - 发现风险点请用“红色警告”或“高亮”提示。"
                res = deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[{"role": "user", "content": prompt}]
                )
                st.markdown(f"<div class='minister-box'>{res.choices[0].message.content}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"锦衣卫探报受阻：{e}")

st.divider()

# 追问区
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt_in := st.chat_input("朕还有话要问..."):
    st.session_state.messages.append({"role": "user", "content": prompt_in})
    with st.chat_message("user"):
        st.markdown(prompt_in)
    with st.chat_message("assistant"):
        try:
            m = genai.GenerativeModel(get_valid_gemini_model())
            res = m.generate_content(f"基于奏章：\n{knowledge}\n回答追问：{prompt_in}")
            st.markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})
        except Exception as e:
            st.error(f"回复失败：{e}")
