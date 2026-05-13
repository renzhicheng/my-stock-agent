# app.py
import streamlit as st
import logic
from services import sheets_service
from prompts import ROLE_CHAIN

st.set_page_config(page_title="赛博大明投策堂", layout="centered", page_icon="🏯")

# ==========================================
# 🎨 核心 UI 样式
# ==========================================
st.markdown("""
    <style>
    .block-container { max-width: 850px; padding-top: 2rem; padding-bottom: 100px; overflow-x: hidden; }
    .report-card { padding: 24px; border-radius: 12px; margin-bottom: 24px; background-color: #ffffff; border: 1px solid #eaeaea; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); font-size: 15px; line-height: 1.7; color: #2c3e50; overflow-x: auto; }
    .report-card table { display: block !important; width: 100% !important; overflow-x: auto !important; -webkit-overflow-scrolling: touch; }
    .report-card th, .report-card td { min-width: 80px; white-space: nowrap; }
    .role-title { font-size: 1rem; font-weight: 600; color: #1a1a1a; margin-bottom: 16px; display: flex; align-items: center; border-bottom: 1px solid #f0f0f0; padding-bottom: 8px; }
    .emperor-decree { background-color: #f7f7f8; padding: 16px 24px; border-radius: 12px; margin-bottom: 30px; color: #1a1a1a; font-weight: 600; border-left: 4px solid #4a5568; }
    .history-divider { border-top: 2px dashed #eaeaea; margin: 40px 0; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .auth-box { max-width: 400px; margin: 0 auto; margin-top: 50px; padding: 30px; border-radius: 10px; border: 1px solid #eee; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 🧠 会话状态初始化
# ==========================================
if "username" not in st.session_state:
    st.session_state.username = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "execute_flag" not in st.session_state:
    st.session_state.execute_flag = False
if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = "init"
if "current_decree" not in st.session_state:
    st.session_state.current_decree = ""

# ==========================================
# 🚪 宫门外：未登录状态（注册/登录页面）
# ==========================================
if not st.session_state.username:
    st.markdown("<h1 style='text-align: center; margin-top: 50px;'>🏯 赛博大明·内阁机要室</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #666;'>推演国运，洞察先机</p>", unsafe_allow_html=True)
    
    st.markdown("<div class='auth-box'>", unsafe_allow_html=True)
    tab1, tab2 = st.tabs(["🔑 登入朝堂", "📜 领取告身 (注册)"])
    
    with tab1:
        login_user = st.text_input("名号 (账号)", key="log_user")
        login_pwd = st.text_input("通关文牒 (密码)", type="password", key="log_pwd")
        if st.button("升座", use_container_width=True, type="primary"):
            if sheets_service.verify_user(login_user, login_pwd):
                st.session_state.username = login_user
                # 登录成功，立刻去史馆调取他以前的所有聊天记录
                with st.spinner("正在调取起居注档案..."):
                    st.session_state.chat_history = sheets_service.load_chat_history(login_user)
                st.rerun()
            else:
                st.error("名号或密码有误，通传失败。")
                
    with tab2:
        reg_user = st.text_input("拟定名号", key="reg_user")
        reg_pwd = st.text_input("设置密码", type="password", key="reg_pwd")
        if st.button("注册", use_container_width=True):
            success, msg = sheets_service.register_user(reg_user, reg_pwd)
            if success:
                st.success(msg)
            else:
                st.error(msg)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop() # 拦截执行，未登录者到此为止

# ==========================================
# 👑 宫门内：已登录状态（主朝堂）
# ==========================================
username = st.session_state.username

# --- 侧边栏：机要控制台 ---
with st.sidebar:
    st.title(f"👑 {username} 陛下，欢迎上朝")
    st.caption("赛博大明智投引擎 v2.0")
    
    if st.button("🚪 退出朝堂", use_container_width=True):
        st.session_state.username = None
        st.session_state.chat_history = []
        st.rerun()
        
    st.divider()
    
    # 悄悄在后台加载数据
    with st.spinner("东厂情报加载中..."):
        knowledge, files = logic.fetch_imperial_data()
        
    st.caption(f"📦 当前挂载 {len(files)} 份密报卷宗")
    if st.button("🔄 强制刷新最新密报", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 主界面：渲染史官记录 ---
for turn in st.session_state.chat_history:
    st.caption(f"🕒 {turn.get('timestamp', '过往记录')}")
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{turn['decree']}</div>", unsafe_allow_html=True)
    for res in turn['responses']:
        st.markdown(f"<div class='report-card'><div class='role-title'>{res['title']}</div>{res['content']}</div>", unsafe_allow_html=True)
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)

# --- 底部：聆听圣意 (聊天输入框) ---
chat_input = st.chat_input("输入新的旨意 (如：明日半导体能接吗？)...")

if chat_input:
    st.session_state.current_scenario = "chat"
    st.session_state.current_decree = chat_input
    st.session_state.execute_flag = True

# --- 核心大模型推演引擎 ---
if st.session_state.execute_flag:
    decree = st.session_state.current_decree
    scenario = st.session_state.current_scenario
    
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{decree}</div>", unsafe_allow_html=True)
    current_turn_responses = []
    context_dict = {"user_decree": decree}
    
    for role in ROLE_CHAIN:
        with st.spinner(f"{role['ui_title'].split(' ')[1]} 思考中..."):
            try:
                template_key = "init_prompt_template" if scenario == "init" else "chat_prompt_template"
                formatted_prompt = role[template_key].format(**context_dict)
                
                output = logic.ask_deepseek(
                    sys_role=role['system_prompt'], 
                    base_data=knowledge, 
                    user_prompt=formatted_prompt, 
                    temp=role['temperature']
                )
                
                context_dict[role['id']] = output
                current_turn_responses.append({"title": role['ui_title'], "content": output})
                st.markdown(f"<div class='report-card'><div class='role-title'>{role['ui_title']}</div>{output}</div>", unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"调用受阻：{e}")
                err_msg = "微臣不知。"
                context_dict[role['id']] = err_msg
                current_turn_responses.append({"title": role['ui_title'], "content": err_msg})
                
    # ★ 写入本地内存
    st.session_state.chat_history.append({
        "timestamp": "刚刚",
        "scenario": scenario,
        "decree": decree,
        "responses": current_turn_responses
    })
    
    # ★ 写入云端史馆 (Google 表格)
    with st.spinner("史官正在记录入库..."):
        sheets_service.save_chat_history(username, scenario, decree, current_turn_responses)
    
    st.session_state.execute_flag = False 
    st.rerun()

# --- 初始空白页 (没历史记录时显示) ---
elif len(st.session_state.chat_history) == 0:
    st.markdown("<h2 style='text-align: center; color: #999; margin-top: 100px; font-weight: 300;'>众位大臣已就绪</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if st.button("🌅 上朝 (生成今日简报)", use_container_width=True, type="primary"):
            st.session_state.current_scenario = "init"
            st.session_state.current_decree = "开始分析当日的行情局势"
            st.session_state.execute_flag = True
            st.rerun()
