# logic.py
import streamlit as st
from services.drive_service import get_drive_service, get_csv_files, download_csv_as_dataframe
from services.llm_service import call_deepseek

@st.cache_data(ttl=3600)
def fetch_imperial_data():
    """业务层：统筹拉取并组装大明帝国的盘面奏章"""
    drive_service = get_drive_service()
    kb = ""
    fl = []
    
    ids = {
        "总榜文件夹": "1bcO3nIarKPKK8J3VK9n0nnzDobuP3i5t", 
        "分板数据仓": "1HwQpIGSf5ggs-a-xWGa8deXEhF5sDNtv"
    }
    
    for f_type, f_id in ids.items():
        for f in get_csv_files(drive_service, f_id):
            fl.append(f"{f_type}-{f['name']}")
            try:
                # 调用下载服务获取 DataFrame
                df = download_csv_as_dataframe(drive_service, f['id'])
                # 转为 CSV 文本拼接进知识库
                kb += f"\n[{f['name']}]\n{df.to_csv(index=False)}\n"
            except Exception as e:
                print(f"解析 {f['name']} 失败: {e}")
                continue
    return kb, fl

def ask_deepseek(sys_role, base_data, user_prompt, temp=0.3):
    """业务层：对接前端的透传函数"""
    return call_deepseek(sys_role, base_data, user_prompt, temp)
