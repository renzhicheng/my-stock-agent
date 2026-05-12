# app.py
import streamlit as st
import logic
from prompts import ROLE_CHAIN

# --- 1. 样式与初始化 ---
st.set_page_config(page_title="赛博大明·圣旨决策链", layout="wide")
st.markdown("""
    <style>
    .report-card { padding: 20px; border-radius: 10px; margin-bottom: 20px; background-color: #fcfaf2; }
    .cabinet-border { border-left: 6px solid #8b0000; }
    .jinyiwei-border { border-left: 6px solid #2f4f4f; }
    /* 未来加角色，只需在这里补充边框颜色，例如：.hubu-border { border-left: 6px solid #006400; } */
    .emperor-decree { background-color: #fffde7; padding: 15px; border-radius: 8px; border: 2px dashed #d4af37; margin-bottom: 20px; font-weight: bold; }
    .history-divider { border-top: 1px solid #ddd; margin: 30px 0; }
    </style>
""", unsafe_allow_html=True)

if "chat_history" not in st.session_state: st.session_state.chat_history = []

# --- 2. 侧边栏 ---
with st.sidebar:
    if st.button("🔄 同步奏章 (清理缓存)", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("🧹 退朝 (清空记录)", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    knowledge, files = logic.fetch_imperial_data()
    st.success(f"已录入 {len(files)} 份数据 (截取前100行)")
    for f in files: st.caption(f"📄 {f}")

# --- 3. 历史记录渲染 ---
for turn in st.session_state.chat_history:
    st.markdown(f"<div class='emperor-decree'>旨意：{turn['decree']}</div>", unsafe_allow_html=True)
    # 动态渲染历史记录中的角色卡片
    for role_res in turn['responses']:
        st.markdown(f"<div class='report-card {role_res['css']}'><b>{role_res['title']}</b><br>{role_res['content']}</div>", unsafe_allow_html=True)
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)

# --- 4. 宣旨处理 (动态角色生成链) ---
if user_decree := st.chat_input("朕有旨意..."):
    st.markdown(f"<div class='emperor-decree'>旨意：{user_decree}</div>", unsafe_allow_html=True)
    
    current_turn_responses = [] # 存储本次问答的各角色回复，用于存入历史
    context_dict = {"user_decree": user_decree} # 动态上下文，随着角色回答不断丰富
    
    with st.container():
        # 遍历配置表中的角色，自动接力回答
        for role in ROLE_CHAIN:
            with st.spinner(f"{role['ui_title'].split(' ')[1]} 正在拟票..."):
                try:
                    # 格式化当前角色的提问 prompt（将之前角色的答案填入）
                    formatted_user_prompt = role['user_prompt_template'].format(**context_dict)
                    
                    # 发送请求给 DeepSeek
                    output = logic.ask_deepseek(
                        sys_role=role['system_prompt'], 
                        base_data=knowledge, 
                        user_prompt=formatted_user_prompt, 
                        temp=role['temperature']
                    )
                    
                    # 渲染界面
                    st.markdown(f"<div class='report-card {role['css_class']}'><b>{role['ui_title']}</b><br>{output}</div>", unsafe_allow_html=True)
                    
                    # 将本角色的回答加入上下文字典，供下一个角色使用
                    context_dict[role['id']] = output
                    current_turn_responses.append({
                        "title": role['ui_title'],
                        "css": role['css_class'],
                        "content": output
                    })
                except Exception as e:
                    st.error(f"{role['ui_title']} 传旨受阻：{e}")
                    context_dict[role['id']] = "未能有效研判。"

    # 保存整条动态生成的决策链到历史中
    st.session_state.chat_history.append({
        "decree": user_decree, 
        "responses": current_turn_responses
    })
    st.rerun()
