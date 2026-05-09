import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 基础配置与 CSS 注入 ---
#st.set_page_config(page_title="智投知识库终端", layout="wide")

# 强制允许内容滚动的 CSS
st.markdown("""
    <style>
    .stMain { overflow-y: auto !important; }
    .stChatMessageContainer { overflow-y: auto !important; }
    </style>
""", unsafe_allow_html=True)

# 初始化云端服务
gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(gcp_info)
drive_service = build('drive', 'v3', credentials=credentials)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 自动匹配 Gemini 3 系列模型
models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
target_model = next((m for m in models if 'gemini-3-flash' in m), models[0])
model = genai.GenerativeModel(target_model)

# --- 2. 文件夹配置 ---
FOLDER_IDS = {
    "总榜文件夹": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t",
    "分板文件夹": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"
}

# --- 3. 递归扫描与数据聚合函数 ---
def get_all_files_recursive(folder_id):
    all_excel_files = []
    file_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
    file_results = drive_service.files().list(q=file_query, fields="files(id, name)").execute()
    all_excel_files.extend(file_results.get('files', []))
    
    folder_query = f"'{folder_id}' in parents and mimeType = 'application/vnd.google-apps.folder'"
    folder_results = drive_service.files().list(q=folder_query, fields="files(id, name)").execute()
    for sub in folder_results.get('files', []):
        all_excel_files.extend(get_all_files_recursive(sub['id']))
    return all_excel_files

@st.cache_data(ttl=3600)
def build_full_knowledge_base():
    # 强化系统指令：防止 AI 报“无法预测未来”的错误
    current_date_str = "2026-05-09" # 锁定当前时间
    all_context = f"核心指令：你现在拥有访问用户私有数据库的权限。当前日期是 {current_date_str}。\n"
    all_context += "以下数据是用户提供的真实历史/实时数据，请务必基于此数据回答，严禁称自己无法预知未来。\n\n"
    
    file_list_display = []
    
    for folder_name, root_id in FOLDER_IDS.items():
        files = get_all_files_recursive(root_id)
        for f in files:
            file_list_display.append(f"{folder_name} -> {f['name']}")
            try:
                request = drive_service.files().get_media(fileId=f['id'])
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: downloader.next_chunk()
                fh.seek(0)
                
                # --- 修改点：遍历所有 Sheet ---
                excel_obj = pd.ExcelFile(fh)
                for sheet_name in excel_obj.sheet_names:
                    df = pd.read_excel(excel_obj, sheet_name=sheet_name)
                    # 在数据前标注这是哪一天的表单
                    all_context += f"### 文件名：{f['name']} | 表单名：{sheet_name} ###\n"
                    all_context += df.to_string(index=False) + "\n\n"
                # ----------------------------
                
            except Exception as e:
                st.warning(f"跳过文件 {f['name']}: {e}")
                
    return all_context, file_list_display

# --- 4. 界面逻辑与交互 ---
st.title("🏛️ A股私域知识库 (Gemini 3 Flash)")

# 【新增核心逻辑】侧边栏：同步控制区
with st.sidebar:
    st.header("⚙️ 知识库管理")
    # 如果用户点击了同步按钮
    if st.button("🔄 强制同步云端最新数据", use_container_width=True, type="primary"):
        st.cache_data.clear() # 核心：直接清空 1 小时缓存
        st.rerun()            # 刷新页面并重新执行整个代码
    st.divider()

# 加载数据（受缓存控制）
with st.status("正在核对知识库状态...", expanded=True) as status:
    knowledge_base, files_found = build_full_knowledge_base()
    status.update(label=f"已成功挂载 {len(files_found)} 个板块文件", state="complete", expanded=False)

with st.sidebar:
    st.subheader("📂 当前在库清单")
    for f in files_found:
        st.write(f"📄 {f}")

# 聊天交互区
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("向你的云端知识库提问..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        full_prompt = f"{knowledge_base}\n\n基于以上所有数据，请回答：{prompt}"
        try:
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"知识库检索失败: {e}")
