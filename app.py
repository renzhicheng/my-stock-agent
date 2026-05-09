import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 1. 初始化 ---
st.set_page_config(page_title="智投知识库终端", layout="wide")

# 加载 GCP 与 Gemini (Paid Tier 自动识别模型)
gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(gcp_info)
drive_service = build('drive', 'v3', credentials=credentials)
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# 自动获取当前可用的 Gemini 3 Flash 模型
models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
target_model = next((m for m in models if 'gemini-3-flash' in m), models[0])
model = genai.GenerativeModel(target_model)

# --- 2. 工程核心：多文件夹扫描逻辑 ---
# 这里填入你两个文件夹的 ID
FOLDER_IDS = {
    "总榜文件夹": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t",
    "分板文件夹": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"
}

@st.cache_data(ttl=3600) # 缓存 1 小时，避免频繁请求 API
def build_full_knowledge_base():
    all_context = "你现在的身份是 A股智投专家。以下是来自 Google Drive 知识库的所有实时数据：\n\n"
    file_list_display = []
    
    for folder_name, f_id in FOLDER_IDS.items():
        # 扫描文件夹内的所有 Excel 文件
        query = f"'{f_id}' in parents and mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        
        for f in files:
            file_list_display.append(f"{folder_name} -> {f['name']}")
            # 读取文件内容
            request = drive_service.files().get_media(fileId=f['id'])
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            
            # 读取 Excel (自动取最新 Sheet)
            excel_obj = pd.ExcelFile(fh)
            df = pd.read_excel(excel_obj, sheet_name=excel_obj.sheet_names[-1])
            
            # 转换为文本加入大背景
            all_context += f"### 数据来源：{folder_name} - {f['name']} ###\n"
            all_context += df.to_string(index=False) + "\n\n"
            
    return all_context, file_list_display

# --- 3. 界面显示 ---
st.title("🏛️ A股私域知识库对话 (Gemini 3 Flash)")

with st.status("正在扫描并同步云端知识库...", expanded=True) as status:
    knowledge_base, files_found = build_full_knowledge_base()
    st.write(f"✅ 已成功挂载 {len(files_found)} 个板块文件。")
    status.update(label="知识库同步完成！", state="complete", expanded=False)

# 在侧边栏显示当前加载的“知识清单”
with st.sidebar:
    st.header("📂 当前挂载知识点")
    for f in files_found:
        st.write(f"📄 {f}")

# --- 4. 聊天区 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("基于全量知识库，请问你想分析什么？"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # 极其关键：将整个知识库塞进上下文
        full_prompt = f"{knowledge_base}\n\n根据以上所有板块的数据，请回答：{prompt}"
        
        try:
            # Gemini 3 Flash 的百万 Token 窗口足够支撑这种“全量喂养”
            response = model.generate_content(full_prompt)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
        except Exception as e:
            st.error(f"分析失败: {e}")
