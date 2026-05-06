"""AI 对话页面 — 独立医学问答 + 教学深度滑块"""

import streamlit as st

from core.database import init_database
init_database()

from config import TEACHING_MODES

st.set_page_config(page_title="AI对话 - 临床助手", page_icon="🤖", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()
st.title("🤖 AI 对话")

# 侧边配置
with st.sidebar:
    st.subheader("AI 配置")

    teaching_mode = st.select_slider(
        "教学深度",
        options=list(TEACHING_MODES.keys()),
        format_func=lambda x: TEACHING_MODES[x]["label"],
        value="discussion",
    )
    st.caption(TEACHING_MODES[teaching_mode]["description"])

    model = st.radio(
        "模型",
        ["deepseek-v4-flash", "deepseek-v4-pro"],
        horizontal=True,
        index=0,
    )

    st.divider()
    st.caption("💡 此对话窗口与患者数据隔离，用于通用医学问题探讨。")

# 对话历史
if "ai_messages" not in st.session_state:
    st.session_state.ai_messages = []

# 显示历史
for msg in st.session_state.ai_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入区
if prompt := st.chat_input("输入医学问题..."):
    # 添加用户消息
    st.session_state.ai_messages.append({"role": "user", "content": prompt})

    # 构建 system prompt
    from prompts.prompt_builder import build_system_prompt

    mode_instructions = {
        "command": "请以指令模式回复：直接、简洁，只给出核心答案和行动建议，不展开讨论。",
        "discussion": "请以讨论模式回复：展开分析，列出依据和考量因素，帮助master理解临床决策背后的逻辑。",
        "teaching": "请以教学模式回复：系统性讲解相关知识，从基础原理到临床应用，如同给住院医师进行教学查房。",
    }

    system_prompt = build_system_prompt(include_rules=False)
    system_prompt += "\n\n## 教学模式指令\n" + mode_instructions.get(teaching_mode, "")

    # 构建对话历史
    messages = [{"role": "system", "content": system_prompt}]
    for msg in st.session_state.ai_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # 调用 API
    from core.deepseek_client import get_client, get_api_key
    if not get_api_key():
        st.error("请先在「规则配置」页面设置 API Key")
    else:
        client = get_client()
        if client:
            with st.chat_message("assistant"):
                placeholder = st.empty()
                full_response = ""
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True,
                        max_tokens=4096,
                        temperature=0.7 if teaching_mode == "teaching" else 0.3,
                    )
                    for chunk in response:
                        if chunk.choices[0].delta.content:
                            full_response += chunk.choices[0].delta.content
                            placeholder.markdown(full_response + "▌")
                    placeholder.markdown(full_response)
                except Exception as e:
                    placeholder.error(f"API 调用失败：{str(e)}")
                    full_response = f"❌ 错误：{str(e)}"

            st.session_state.ai_messages.append({"role": "assistant", "content": full_response})
            st.rerun()

# 清除按钮
if st.session_state.ai_messages:
    st.divider()
    if st.button("🗑️ 清除对话历史"):
        st.session_state.ai_messages = []
        st.rerun()
