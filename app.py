import streamlit as st
import pandas as pd
import google.generativeai as genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# 1. 权限初始化
# 从 Secrets 中安全读取 JSON 密钥
gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
credentials = service_account.Credentials.from_service_account_info(gcp_info)
drive_service = build('drive', 'v3', credentials=credentials)

genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-3-flash')

# 2. 从 Google Drive 动态获取文件函数
def get_excel_from_drive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.ExcelFile(fh)

# --- 界面展示 ---
st.title("🚀 A股资金流向云端看板")

# 这里填入你 Google Drive 文件夹中对应文件的 ID
# (在网页版 Drive 打开文件，URL 后面那一串长字符串就是 ID)
FILE_ID = "你的文件ID" 

if st.button("🔄 刷新云端数据并生成分析报告"):
    with st.spinner("正在直接连接 Google Drive..."):
        # 获取最新的 Excel
        excel_data = get_excel_from_drive(FILE_ID)
        # 默认取最后一个 Sheet (最新的日期)
        latest_date = excel_data.sheet_names[-1]
        df = pd.read_excel(excel_data, sheet_name=latest_date)
        
        st.subheader(f"📅 最新数据日期：{latest_date}")
        st.dataframe(df)
        
        # 喂给 Gemini 进行分析
        prompt = f"你是资深策略师，请分析以下数据并给出结论：{df.to_string()}"
        response = model.generate_content(prompt)
        st.markdown("### 🤖 智能诊断报告")
        st.write(response.text)
