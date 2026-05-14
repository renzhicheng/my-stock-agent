# services/llm_service.py
import streamlit as st
from openai import OpenAI

@st.cache_resource
def get_llm_client():
    """初始化并缓存 DeepSeek 客户端"""
    try:
        return OpenAI(api_key=st.secrets["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
    except Exception as e:
        st.error(f"❌ 大模型接口初始化异常：{e}")
        st.stop()

def call_deepseek(sys_role, base_data, user_prompt, temp=0.3):
    """标准的 API 调用封装"""
    client = get_llm_client()
    
    # 将海量基础数据固定在 System Prompt 中，最大化利用缓存降本
    system_content = f"【全局奏章数据】\n{base_data}\n\n【你的角色】\n{sys_role}"
    
    res = client.chat.completions.create(
        model="deepseek-v4-pro",
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temp
    )
    return res.choices[0].message.content
