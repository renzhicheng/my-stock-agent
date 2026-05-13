# services/sheets_service.py
import streamlit as st
import json
import hashlib
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 1. 核心底座：连接 Google 表格 ---
@st.cache_resource
def get_sheets_service():
    """初始化 Google Sheets API 客户端"""
    try:
        gcp_info = json.loads(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
        # 必须同时申请 Drive 和 Sheets 的权限
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets', 
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = service_account.Credentials.from_service_account_info(gcp_info, scopes=scopes)
        return build('sheets', 'v4', credentials=credentials)
    except Exception as e:
        st.error(f"❌ 户部档案局 (Google Sheets) 初始化失败：{e}")
        st.stop()

def get_sheet_id():
    return st.secrets["SPREADSHEET_ID"]

# --- 2. 密码加密小工具 ---
def hash_password(password):
    """使用 SHA-256 进行不可逆加密，哪怕是你去看表格，也看不到家人的明文密码"""
    salt = "cyber_ming_salt_2026" # 加盐，增加安全性
    return hashlib.sha256((password + salt).encode()).hexdigest()

# ==========================================
# 3. 户部业务：注册与登录
# ==========================================
def get_all_users():
    """获取所有用户，返回 {用户名: 密码乱码} 的字典"""
    service = get_sheets_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=get_sheet_id(), range="Users!A:C"
        ).execute()
        rows = result.get('values', [])
        # 排除表头，把用户名和密码组装成字典
        return {row[0]: row[1] for row in rows if len(row) >= 2 and row[0] != "Username"}
    except Exception as e:
        print(f"读取用户列表失败: {e}")
        return {}

def register_user(username, password):
    """注册新用户，写入表格"""
    # 如果没填，防呆拦截
    if not username or not password:
        return False, "名号与通关文牒（密码）不可为空！"
        
    users = get_all_users()
    if username in users:
        return False, "该名号已被占用，请换一个。"
        
    hashed_pw = hash_password(password)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 按照 [用户名, 密码哈希, 注册时间] 的顺序打包
    body = {"values": [[username, hashed_pw, now_str]]}
    try:
        service = get_sheets_service()
        service.spreadsheets().values().append(
            spreadsheetId=get_sheet_id(), range="Users!A:C",
            valueInputOption="USER_ENTERED", body=body
        ).execute()
        return True, "册封成功！可以上朝了。"
    except Exception as e:
        return False, f"写入户部黄册失败: {e}"

def verify_user(username, password):
    """验证登录"""
    users = get_all_users()
    if username not in users:
        return False
    # 比对加密后的密码是否一致
    return users[username] == hash_password(password)

# ==========================================
# 4. 史官业务：保存与读取聊天记录
# ==========================================
def save_chat_history(username, scenario, decree, responses_list):
    """将一轮完整的对话存入表格的 History 标签页"""
    service = get_sheets_service()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # ★ 核心技巧：把三大角色的回答列表，压缩成一个字符串
    responses_json = json.dumps(responses_list, ensure_ascii=False)
    
    # 按 [时间, 操作人, 场景, 旨意, 压缩后的回答] 打包
    body = {"values": [[now_str, username, scenario, decree, responses_json]]}
    service.spreadsheets().values().append(
        spreadsheetId=get_sheet_id(), range="History!A:E",
        valueInputOption="USER_ENTERED", body=body
    ).execute()

def load_chat_history(username):
    """启动时调用，从表格读取属于自己的过往历史"""
    service = get_sheets_service()
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=get_sheet_id(), range="History!A:E"
        ).execute()
        rows = result.get('values', [])
        
        history = []
        for row in rows:
            # 数据格式不全、或者不是当前登录人的记录、或者是表头，全部跳过
            if len(row) < 5 or row[1] != username or row[0] == "Timestamp":
                continue 
                
            # ★ 核心技巧：把字符串重新解压成三大角色的 Python 列表
            responses_list = json.loads(row[4])
            
            history.append({
                "timestamp": row[0],
                "scenario": row[2],
                "decree": row[3],
                "responses": responses_list
            })
        return history
    except Exception as e:
        print(f"读取大明起居注失败: {e}")
        return []
