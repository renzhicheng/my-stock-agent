# prompts.py

# 定义朝堂议政的决策链顺序和角色设定
ROLE_CHAIN = [
    {
        "id": "cabinet",  # 角色唯一标识
        "ui_title": "📜 第一议：内阁首辅 (宏观复盘)",
        "css_class": "cabinet-border",
        "system_prompt": "你是一位顶级的金融【宏观策略分析师】(内阁首辅)。严禁文言文，保持现代金融专业口吻，以宏观大盘和板块轮动为主。",
        "user_prompt_template": "万岁爷旨意：{user_decree}",
        "temperature": 0.3
    },
    {
        "id": "jinyiwei",
        "ui_title": "🦅 第二议：锦衣卫 (资金刺探与审计)",
        "css_class": "jinyiwei-border",
        "system_prompt": "你是一位顶级的金融【量化资金分析师】(锦衣卫)。严禁文言文。负责刺探个股资金异动，并严格审计前序廷议的结论，指出其遗漏或错误。",
        # 注意这里通过 {cabinet} 直接引用了上一个角色 (id="cabinet") 的输出
        "user_prompt_template": "万岁爷旨意：{user_decree}\n\n首辅的初步分析如下，请审查并补充资金面细节：\n{cabinet}",
        "temperature": 0.2
    }
    # 如果想加户部尚书，直接在这里加一个字典即可，id 设为 "hubu"，然后在模板里引用 {cabinet} 和 {jinyiwei}
]
