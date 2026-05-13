# services/drive_service.py
import streamlit as st
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import json

@st.cache_resource
def get_drive_service():
    """初始化并缓存 Google Drive 客户端"""
    try:
        credentials = service_account.Credentials.from_service_account_info(json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"]))
        return build('drive', 'v3', credentials=credentials)
    except Exception as e:
        st.error(f"❌ 谷歌云端硬盘初始化异常：{e}")
        st.stop()

def get_csv_files(drive_service, folder_id):
    """递归获取文件夹下的所有 CSV 文件"""
    q = f"'{folder_id}' in parents and (mimeType = 'text/csv' or mimeType = 'application/vnd.google-apps.folder' or name contains '.csv')"
    res = drive_service.files().list(q=q, fields="files(id, name, mimeType)").execute().get('files', [])
    
    files = [f for f in res if f['mimeType'] == 'text/csv' or f['name'].endswith('.csv')]
    folders = [f for f in res if f['mimeType'] == 'application/vnd.google-apps.folder']
    
    for folder in folders: 
        files.extend(get_csv_files(drive_service, folder['id']))
    return files

def download_csv_as_dataframe(drive_service, file_id, head_n=100):
    """下载 CSV 文件并直接转化为 Pandas DataFrame"""
    req = drive_service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, req)
    
    done = False
    while not done:
        _, done = downloader.next_chunk()
        
    fh.seek(0)
    # 暂时截取前100行省Token，后续你可以按需修改
    return pd.read_csv(fh, encoding='utf-8-sig').head(head_n)
