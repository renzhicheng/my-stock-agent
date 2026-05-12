import streamlit as st
import logic
from prompts import ROLE_CHAIN

st.set_page_config(page_title="赛博大明王朝投策堂", layout="centered")

st.markdown("""
    <style>
    .block-container { max-width: 850px; padding-top: 2rem; padding-bottom: 100px; overflow-x: hidden; }
    
    .report-card { 
        padding: 24px; 
        border-radius: 12px; 
        margin-bottom: 24px; 
        background-color: #ffffff; 
        border: 1px solid #eaeaea; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); 
        font-size: 15px; 
        line-height: 1.7; 
        color: #2c3e50; 
        /* 防止卡片自身被内部元素撑破 */
        overflow-x: auto; 
    }
    
    .role-title { font-size: 1rem; font-weight: 600; color: #1a1a1a; margin-bottom: 16px; display: flex; align-items: center; border-bottom: 1px solid #f0f0f0; padding-bottom: 8px; }
    .emperor-decree { background-color: #f7f7f8; padding: 16px 24px; border-radius: 12px; margin-bottom: 30px; color: #1a1a1a; font-weight: 600; border-left: 4px solid #4a5568; }
    .history-divider { border-top: 2px dashed #eaeaea; margin: 40px 0; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    .center-button-wrapper { margin-top: 30px; }

    /* 🔥 新增：专门解决手机端表格左右晃动的核心 CSS */
    .report-card table {
        display: block !important;
        width: 100% !important;
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch; /* 让苹果 iOS 设备的横向滑动更丝滑 */
    }
    
    .report-card th, .report-card td {
        min-width: 80px; /* 避免表格太挤 */
        white-space: nowrap; /* 强制表格内容不换行，保持整齐，配合横向滑动使用 */
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. 初始化记忆盒子 (必须放在最前面)
# ==========================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "execute_flag" not in st.session_state:
    st.session_state.execute_flag = False
if "current_scenario" not in st.session_state:
    st.session_state.current_scenario = "init"
if "current_decree" not in st.session_state:
    st.session_state.current_decree = ""

# ==========================================
# 2. 侧边栏与数据加载
# ==========================================
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

# ==========================================
# 3. 渲染历史对话 (让你能上滑查阅)
# ==========================================
for turn in st.session_state.chat_history:
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{turn['decree']}</div>", unsafe_allow_html=True)
    for res in turn['responses']:
        st.markdown(f"<div class='report-card'><div class='role-title'>{res['title']}</div>{res['content']}</div>", unsafe_allow_html=True)
    st.markdown("<div class='history-divider'></div>", unsafe_allow_html=True)

# ==========================================
# 4. 底部输入框监听
# ==========================================
chat_input = st.chat_input("宣旨 (如：明天XX个股能接吗？)...")

if chat_input:
    st.session_state.current_scenario = "chat"  # 标记为日常追问模式
    st.session_state.current_decree = chat_input
    st.session_state.execute_flag = True

# ==========================================
# 5. 执行大模型推理 (动态追加)
# ==========================================
if st.session_state.execute_flag:
    decree = st.session_state.current_decree
    scenario = st.session_state.current_scenario
    
    # 先把当前的问题印在网页最下方
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{decree}</div>", unsafe_allow_html=True)
    
    current_turn_responses = []
    context_dict = {"user_decree": decree}
    
    # 角色依次接力思考
    for role in ROLE_CHAIN:
        with st.spinner(f"{role['ui_title'].split(' ')[1]} 思考中..."):
            try:
                # 动态选择 Prompt 模板
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
                
                # 思考完一个角色，立刻渲染在网页上
                st.markdown(f"<div class='report-card'><div class='role-title'>{role['ui_title']}</div>{output}</div>", unsafe_allow_html=True)
            except Exception as e:
                st.error(f"调用受阻：{e}")
                context_dict[role['id']] = "微臣不知。"
                current_turn_responses.append({"title": role['ui_title'], "content": "微臣不知。"})
                
    # ★ 最关键的一步：将本次的问答打包，存入历史记忆盒子！
    st.session_state.chat_history.append({
        "decree": decree,
        "responses": current_turn_responses
    })
    
    # 关闭执行锁，并刷新页面（页面刷新后，第三步的历史记录渲染就会把刚才存入的数据画出来）
    st.session_state.execute_flag = False 
    st.rerun()

# ==========================================
# 6. 初始空白页 (没历史记录，也没在执行时显示)
# ==========================================
elif len(st.session_state.chat_history) == 0:
    st.markdown("<h2 style='text-align: center; color: #999; margin-top: 100px; font-weight: 300;'>诸位大臣已就绪</h2>", unsafe_allow_html=True)
    st.markdown("<div class='center-button-wrapper'></div>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if st.button("🌅 上朝 (生成今日简报)", use_container_width=True, type="primary"):
            st.session_state.current_scenario = "init"  # 标记为上朝全景模式
            st.session_state.current_decree = "开始分析当日的行情局势"
            st.session_state.execute_flag = True
            st.rerun()
