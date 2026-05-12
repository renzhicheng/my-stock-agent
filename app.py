import streamlit as st
import logic
from prompts import ROLE_CHAIN

# --- 1. 样式与初始化 (DeepSeek 极简风) ---
st.set_page_config(page_title="赛博大明·智投决策", layout="centered")

st.markdown("""
    <style>
    /* 全局极简优化 */
    .block-container { max-width: 850px; padding-top: 2rem; }
    
    /* 角色卡片：微阴影、纯白背景、柔和圆角 */
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
    
    /* 自定义居中大按钮的外边距 */
    .center-button-wrapper { margin-top: 30px; }
    </style>
""", unsafe_allow_html=True)

# 状态管理
if "current_decree" not in st.session_state:
    st.session_state.current_decree = None
if "current_responses" not in st.session_state:
    st.session_state.current_responses = []

# --- 2. 侧边栏 ---
with st.sidebar:
    st.title("🎛️ 控制台")
    
    # 侧边栏现在只保留数据管理功能
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

# 执行推理逻辑
if getattr(st.session_state, "execute_flag", False):
    decree = st.session_state.current_decree
    
    # 清空之前的回复，实现覆盖效果
    st.session_state.current_responses = [] 
    context_dict = {"user_decree": decree}
    
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
                
    st.session_state.execute_flag = False 

# 渲染已有回复
elif st.session_state.current_decree and st.session_state.current_responses:
    st.markdown(f"<div class='emperor-decree'>💬 旨意：{st.session_state.current_decree}</div>", unsafe_allow_html=True)
    for res in st.session_state.current_responses:
        st.markdown(f"""
            <div class='report-card'>
                <div class='role-title'>{res['title']}</div>
                {res['content']}
            </div>
        """, unsafe_allow_html=True)

# --- 4. 初始空白页（新增主视觉引导按钮） ---
else:
    st.markdown("<h2 style='text-align: center; color: #999; margin-top: 100px; font-weight: 300;'>大明智投引擎已就绪</h2>", unsafe_allow_html=True)
    
    st.markdown("<div class='center-button-wrapper'></div>", unsafe_allow_html=True)
    
    # 使用 columns 将按钮居中，比例可以调节按钮的宽度 [左右空白边距, 按钮宽度, 左右空白边距]
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        if st.button("🌅 上朝 (生成今日简报)", use_container_width=True, type="primary"):
            # 点击后直接赋予旨意，并打上执行标记
            st.session_state.current_decree = "开始分析当日的行情局势"
            st.session_state.execute_flag = True
            # 立即强制刷新页面，进入上方的数据处理逻辑
            st.rerun()
