import streamlit as st
import logic
from prompts import ROLE_CHAIN

st.set_page_config(page_title="赛博大明·智投决策", layout="centered")

st.markdown("""
    <style>
    .block-container { max-width: 850px; padding-top: 2rem; }
    .report-card { padding: 24px; border-radius: 12px; margin-bottom: 24px; background-color: #ffffff; border: 1px solid #eaeaea; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); font-size: 15px; line-height: 1.7; color: #2c3e50; }
    .role-title { font-size: 1rem; font-weight: 600; color: #1a1a1a; margin-bottom: 16px; display: flex; align-items: center; border-bottom: 1px solid #f0f0f0; padding-bottom: 8px; }
    .emperor-decree { background-color: #f7f7f8; padding: 16px 24px; border-radius: 12px; margin-bottom: 30px; color: #1a1a1a; font-weight: 600; border-left: 4px solid #4a5568; }
    .history-divider { border-top: 1px solid #eee; margin: 40px 0; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .center-button-wrapper { margin-top: 30px; }
    </style>
""", unsafe_allow_html=True)

# 状态管理：引入 chat_history 数组，保留互动记录
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "execute_flag" not in st.session_state:
    st.session_state.execute_flag = False

# --- 侧边栏 ---
with st.sidebar:
    st.title("🎛️ 控制台")
    if st.button("🔄 同步最新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    if st.button("🧹 清空朝堂记录", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
        
    st.divider()
    knowledge, files = logic.fetch_imperial_data()
    st.caption(f"已挂载 {len(files)} 份 CSV 数据源")
    for f in files: st.caption(f"📄 {f}")

# --- 历史记录渲染 ---
for turn in st.session_state.chat_history:
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{turn['decree']}</div>", unsafe_allow_html=True)
    for res in turn['responses']:
        st.markdown(f"<div class='report-card'><div class='role-title'>{res['title']}</div>{res['content']}</div>", unsafe_allow_html=True)
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)

# --- 动作监听 ---
chat_input = st.chat_input("输入新的旨意...")

if chat_input:
    st.session_state.current_scenario = "chat"  # 输入框触发日常对话
    st.session_state.current_decree = chat_input
    st.session_state.execute_flag = True

# --- 执行推理逻辑 ---
if st.session_state.execute_flag:
    decree = st.session_state.current_decree
    scenario = st.session_state.current_scenario
    
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{decree}</div>", unsafe_allow_html=True)
    
    current_turn_responses = []
    context_dict = {"user_decree": decree}
    
    for role in ROLE_CHAIN:
        with st.spinner(f"{role['ui_title'].split(' ')[1]} 思考中..."):
            try:
                # 动态选择模板：如果 scenario 是 init，就用 init_prompt_template
                template_key = "init_prompt_template" if scenario == "init" else "chat_prompt_template"
                formatted_user_prompt = role[template_key].format(**context_dict)
                
                output = logic.ask_deepseek(
                    sys_role=role['system_prompt'], 
                    base_data=knowledge, 
                    user_prompt=formatted_user_prompt, 
                    temp=role['temperature']
                )
                
                context_dict[role['id']] = output
                current_turn_responses.append({
                    "title": role['ui_title'],
                    "content": output
                })
                
                st.markdown(f"<div class='report-card'><div class='role-title'>{role['ui_title']}</div>{output}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"调用受阻：{e}")
                context_dict[role['id']] = "微臣不知。"
                
    # 将本次对话存入记忆，不再覆盖
    st.session_state.chat_history.append({
        "decree": decree,
        "responses": current_turn_responses
    })
    
    st.session_state.execute_flag = False 
    st.rerun()

# --- 初始空白页 ---
elif len(st.session_state.chat_history) == 0:
    st.markdown("<h2 style='text-align: center; color: #999; margin-top: 100px; font-weight: 300;'>大明智投引擎已就绪</h2>", unsafe_allow_html=True)
    st.markdown("<div class='center-button-wrapper'></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if st.button("🌅 升座上朝 (生成今日简报)", use_container_width=True, type="primary"):
            st.session_state.current_scenario = "init"  # 按钮触发全景汇报
            st.session_state.current_decree = "开始分析当日的行情局势"
            st.session_state.execute_flag = True
            st.rerun()
