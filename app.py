import streamlit as st
import logic
from prompts import ROLE_CHAIN

# --- 1. 样式与初始化 (DeepSeek 极简风) ---
st.set_page_config(page_title="赛博大明·智投决策", layout="centered")

st.markdown("""
    <style>
    /* 全局极简优化 */
    .block-container { max-width: 850px; padding-top: 2rem; }
    
    /* 角色卡片：去除彩色边框，采用微阴影、纯白背景、柔和圆角 */
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
    }
    
    /* 角色抬头标签 */
    .role-title { 
        font-size: 1rem; 
        font-weight: 600; 
        color: #1a1a1a; 
        margin-bottom: 16px; 
        display: flex;
        align-items: center;
        border-bottom: 1px solid #f0f0f0;
        padding-bottom: 8px;
    }
    
    /* 旨意卡片：极简气泡风格 */
    .emperor-decree { 
        background-color: #f7f7f8; 
        padding: 16px 24px; 
        border-radius: 12px; 
        margin-bottom: 30px; 
        color: #1a1a1a; 
        font-weight: 600;
        border-left: 4px solid #4a5568;
    }
    
    /* 隐藏默认多余元素 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# 状态管理：只保留当前对话，不再无限堆叠历史
if "current_decree" not in st.session_state:
    st.session_state.current_decree = None
if "current_responses" not in st.session_state:
    st.session_state.current_responses = []

# --- 2. 侧边栏 ---
with st.sidebar:
    st.title("🎛️ 控制台")
    
    # 新增：上朝按钮（点击后自动下达旨意并触发大模型）
    if st.button("🌅 升座上朝 (生成简报)", use_container_width=True, type="primary"):
        st.session_state.current_decree = "开始分析当日的行情局势"
        st.session_state.execute_flag = True
        
    if st.button("🔄 同步最新数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
        
    st.divider()
    knowledge, files = logic.fetch_imperial_data()
    st.caption(f"已挂载 {len(files)} 份 CSV 数据源")
    for f in files: 
        st.caption(f"📄 {f}")

# --- 3. 核心流转逻辑 ---
# 监听输入框
chat_input = st.chat_input("输入新的旨意...")
if chat_input:
    st.session_state.current_decree = chat_input
    st.session_state.execute_flag = True

# 执行推理逻辑 (只在收到新旨意或点击上朝时执行)
if getattr(st.session_state, "execute_flag", False):
    decree = st.session_state.current_decree
    
    # 清空之前的回复，实现“覆盖”效果
    st.session_state.current_responses = [] 
    context_dict = {"user_decree": decree}
    
    # 渲染当前旨意
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{decree}</div>", unsafe_allow_html=True)
    
    for role in ROLE_CHAIN:
        with st.spinner(f"{role['ui_title'].split(' ')[1]} 思考中..."):
            try:
                formatted_user_prompt = role['user_prompt_template'].format(**context_dict)
                output = logic.ask_deepseek(
                    sys_role=role['system_prompt'], 
                    base_data=knowledge, 
                    user_prompt=formatted_user_prompt, 
                    temp=role['temperature']
                )
                
                # 存入状态并实时渲染
                st.session_state.current_responses.append({
                    "title": role['ui_title'],
                    "content": output
                })
                context_dict[role['id']] = output
                
                st.markdown(f"""
                    <div class='report-card'>
                        <div class='role-title'>{role['ui_title']}</div>
                        {output}
                    </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"调用受阻：{e}")
                
    # 执行完毕，重置标记
    st.session_state.execute_flag = False 

# 如果没有在执行，但存在已经生成的回复，将其渲染出来（保证刷新网页不白屏）
elif st.session_state.current_decree and st.session_state.current_responses:
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{st.session_state.current_decree}</div>", unsafe_allow_html=True)
    for res in st.session_state.current_responses:
        st.markdown(f"""
            <div class='report-card'>
                <div class='role-title'>{res['title']}</div>
                {res['content']}
            </div>
        """, unsafe_allow_html=True)
else:
    # 初始空白页面的欢迎引导
    st.markdown("<h2 style='text-align: center; color: #bbb; margin-top: 120px; font-weight: 400;'>大明智投引擎已就绪</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #aaa;'>点击左侧「升座上朝」或在下方输入框下达旨意</p>", unsafe_allow_html=True)
