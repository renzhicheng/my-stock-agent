# logic.py
import streamlit as st
import pandas as pd
from openai import OpenAI
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

# --- 权限初始化 ---
@st.cache_resource
def init_services():
    try:
        credentials = service_account.Credentials.from_service_account_info(json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"]))
        drive_service = build('drive', 'v3', credentials=credentials)
        ds_client = OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
        return drive_service, ds_client
    except Exception as e:
        st.error(f"❌ 司礼监初始化异常：{e}")
        st.stop()

# --- 核心工具函数 ---
def get_csv_files(drive_service, folder_id):
    q = f"'{folder_id}' in parents and (mimeType = 'text/csv' or mimeType = 'application/vnd.google-apps.folder')"
    res = drive_service.files().list(q=q, fields="files(id, name, mimeType)").execute().get('files', [])
    files = [f for f in res if f['mimeType'] == 'text/csv']
    folders = [f for f in res if f['mimeType'] != 'text/csv']
    for folder in folders: files.extend(get_csv_files(drive_service, folder['id']))
    return files

@st.cache_data(ttl=3600)
def fetch_imperial_data():
    drive_service, _ = init_services()
    kb, fl = "", []
    ids = {"总榜": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t", "分板": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"}
    
    for f_type, f_id in ids.items():
        for f in get_csv_files(drive_service, f_id):
            fl.append(f"{f_type}-{f['name']}")
            try:
                req = drive_service.files().get_media(fileId=f['id'])
                fh = io.BytesIO()
                MediaIoBaseDownload(fh, req).next_chunk() 
                fh.seek(0)
                df = pd.read_csv(fh, encoding='utf-8-sig').head(100) 
                kb += f"\n[{f['name']}]\n{df.to_csv(index=False)}\n"
            except: continue
    return kb, fl

def ask_deepseek(sys_role, base_data, user_prompt, temp=0.3):
    _, ds_client = init_services()
    system_content = f"【全局奏章数据】\n{base_data}\n\n【你的角色】\n{sys_role}"
    
    res = ds_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temp
    )
    return res.choices[0].message.content
