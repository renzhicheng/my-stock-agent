# court_engine.py
import streamlit as st
import logic
from services import sheets_service
from prompts import ROLE_CHAIN
from datetime import datetime

def process_imperial_decree(username, scenario, decree, knowledge):
    """
    核心推演引擎：负责展示用户旨意、调度大模型、渲染结果卡片，并存入起居注。
    """
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{decree}</div>", unsafe_allow_html=True)
    current_turn_responses = []
    context_dict = {"user_decree": decree}
    
    # 1. 遍历群臣，依次问对
    for role in ROLE_CHAIN:
        with st.spinner(f"{role['ui_title'].split(' ')[1]} 思考中..."):
            try:
                # 判断是开局全景汇报，还是日常追问
                template_key = "init_prompt_template" if scenario == "init" else "chat_prompt_template"
                formatted_prompt = role[template_key].format(**context_dict)
                
                # 调用业务层的 DeepSeek 接口
                output = logic.ask_deepseek(
                    sys_role=role['system_prompt'], 
                    base_data=knowledge, 
                    user_prompt=formatted_prompt, 
                    temp=role['temperature']
                )
                
                # 将回答加入上下文字典，供下一位大臣参考
                context_dict[role['id']] = output
                current_turn_responses.append({"title": role['ui_title'], "content": output})
                
                # 在前端渲染该大臣的奏章卡片
                st.markdown(f"<div class='report-card'><div class='role-title'>{role['ui_title']}</div>{output}</div>", unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"调用受阻：{e}")
                err_msg = "微臣不知。"
                context_dict[role['id']] = err_msg
                current_turn_responses.append({"title": role['ui_title'], "content": err_msg})
                
    # 2. 写入本地内存 (Session State)
    st.session_state.chat_history.append({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scenario": scenario,
        "decree": decree,
        "responses": current_turn_responses
    })
    
    # 3. 写入云端史馆 (Google 表格)
    with st.spinner("史官正在记录入库..."):
        sheets_service.save_chat_history(username, scenario, decree, current_turn_responses)
