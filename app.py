# app.py
import streamlit as st
import logic
import court_engine  # 引入抽离的推演引擎
import streamlit.components.v1 as components
from services import sheets_service
from prompts import ROLE_CHAIN
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="赛博大明投策堂", layout="centered", page_icon="🏯")

# ==========================================
# ⏰ 核心时区与时间状态计算 (东八区北京时间)
# ==========================================
bj_tz = timezone(timedelta(hours=8))
now = datetime.now(bj_tz)
today_str = now.strftime("%Y-%m-%d")
# 判断当前是否处于：15:00 之后 且 00:00 之前
is_session_time = 15 <= now.hour <= 23 

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
st.stop() 

# ==========================================
# 👑 宫门内：已登录状态（主朝堂）
# ==========================================
username = st.session_state.username

# --- 侧边栏：机要控制台与档案袋 ---
with st.sidebar:
    st.title(f"👑 {username} 陛下，欢迎上朝")
    st.caption("赛博大明智投引擎 v2.0")
    
    if st.button("🚪 退出朝堂", use_container_width=True):
        st.session_state.username = None
        st.session_state.chat_history = []
        st.rerun()
        
    st.divider()
    
    # 提取所有有记录的日期用于侧边栏归档
    history_all = st.session_state.chat_history
    all_dates = sorted(list(set(t['timestamp'][:10] for t in history_all)), reverse=True)
    
    st.subheader("📅 调阅往日档案")
    if all_dates:
        view_date = st.selectbox("选择日期查看起居注", ["今日朝堂"] + all_dates, index=0)
    else:
        view_date = "今日朝堂"
        
    st.divider()
    with st.spinner("东厂情报加载中..."):
        knowledge, files = logic.fetch_imperial_data()
        
    st.caption(f"📦 当前挂载 {len(files)} 份密报卷宗")
    if st.button("🔄 强制刷新最新密报", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ==========================================
# 📅 渲染逻辑：根据选择的日期显示内容
# ==========================================
target_date = today_str if view_date == "今日朝堂" else view_date
display_history = [turn for turn in history_all if turn.get('timestamp', '').startswith(target_date)]

if display_history:
    for turn in display_history:
        st.caption(f"🕒 {turn.get('timestamp')}")
        st.markdown(f"<div class='emperor-decree'>💬 旨意：{turn['decree']}</div>", unsafe_allow_html=True)
        for res in turn['responses']:
            st.markdown(f"<div class='report-card'><div class='role-title'>{res['title']}</div>{res['content']}</div>", unsafe_allow_html=True)
        st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)
elif view_date != "今日朝堂":
    st.markdown("<h3 style='text-align: center; color: #999; margin-top: 100px;'>此日无奏章记录</h3>", unsafe_allow_html=True)

# ==========================================
# 🚀 底部行为逻辑：时间锁 + 唯一性校验
# ==========================================
has_assembled_today = any(turn['scenario'] == 'init' and turn['timestamp'].startswith(today_str) for turn in history_all)

if view_date == "今日朝堂":
    if not has_assembled_today:
        if is_session_time:
            st.markdown("<h2 style='text-align: center; color: #999; margin-top: 50px; font-weight: 300;'>申时已到，今日密报已汇聚</h2>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 1.5, 1])
            with col2:
                if st.button("🌅 升座上朝 (生成今日简报)", use_container_width=True, type="primary"):
                    st.session_state.current_scenario = "init"
                    st.session_state.current_decree = "开始分析当日的行情局势"
                    st.session_state.execute_flag = True
                    st.rerun()
        else:
            st.warning(f"🏮 当前时间 {now.strftime('%H:%M')}。未到申时（15:00），今日密报尚未全量汇聚，请待收盘后再行奏报。")
            st.info("💡 您可以从侧边栏调阅往日档案进行复盘。")
    else:
        chat_input = st.chat_input("今日简报已呈递，请下达进一步追问旨意...")
        if chat_input:
            st.session_state.current_scenario = "chat"
            st.session_state.current_decree = chat_input
            st.session_state.execute_flag = True

# ==========================================
# ⚙️ 核心大模型推演引擎 (已解耦)
# ==========================================
if st.session_state.execute_flag:
    court_engine.process_imperial_decree(
        username=username, 
        scenario=st.session_state.current_scenario, 
        decree=st.session_state.current_decree, 
        knowledge=knowledge
    )
    
    st.session_state.execute_flag = False 
    st.rerun()

# ==========================================
# 📜 页面底部自动滚动脚本 (终极锚点版)
# ==========================================
st.markdown("<div id='page-bottom'></div>", unsafe_allow_html=True)
components.html(
    """
    <script>
        setTimeout(function() {
            var bottom = window.parent.document.getElementById('page-bottom');
            if (bottom) {
                bottom.scrollIntoView({ behavior: 'smooth', block: 'end' });
            } else {
                var appContainer = window.parent.document.querySelector('[data-testid="stAppViewContainer"]') || window.parent.document.querySelector('.main');
                if (appContainer) {
                    appContainer.scrollTo({ top: appContainer.scrollHeight, behavior: 'smooth' });
                }
            }
        }, 500); 
    </script>
    """,
    height=0
)
