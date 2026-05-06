"""AI 对话页面 — DeepSeek 风格：左侧对话列表 + 右侧聊天"""

import streamlit as st
import base64

from core.database import init_database
init_database()

from config import TEACHING_MODES
import models.chat_message as chat_db

st.set_page_config(page_title="AI对话 - 临床助手", page_icon="🤖", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()

# ─── Session state ───
if "ai_current_conv" not in st.session_state:
    st.session_state.ai_current_conv = None

# ══════════════════════════════════════════════
# 左侧边栏：对话列表
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 💬 AI 对话")

    # 通用模式（无患者绑定）
    convs = chat_db.get_conversations("general")

    with st.expander("📜 历史对话", expanded=True):
        if not convs:
            st.caption("暂无历史对话")
        for conv in convs:
            cid = conv["conversation_id"]
            title = conv.get("title") or "新对话"
            display_title = (title[:25] + "...") if len(title) > 25 else title

            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                if st.button(display_title, key=f"sel_{cid}", use_container_width=True):
                    st.session_state.ai_current_conv = cid
                    st.rerun()
            with c2:
                if st.button("📌", key=f"pin_{cid}", help="置顶"):
                    st.toast(f"已置顶：{display_title}")
            with c3:
                if st.button("🗑️", key=f"del_{cid}", help="删除"):
                    chat_db.delete_conversation("general", cid)
                    if st.session_state.ai_current_conv == cid:
                        st.session_state.ai_current_conv = None
                    st.rerun()

    st.divider()

    # 教学模式
    teaching_mode = st.select_slider(
        "教学深度",
        options=list(TEACHING_MODES.keys()),
        format_func=lambda x: TEACHING_MODES[x]["label"],
        value="discussion",
    )
    st.caption(TEACHING_MODES[teaching_mode]["description"])

    # 模型选择
    model = st.radio(
        "模型",
        ["deepseek-v4-flash", "deepseek-v4-pro"],
        horizontal=True,
        index=0,
    )

# ══════════════════════════════════════════════
# 主区域
# ══════════════════════════════════════════════

# 顶栏：标题 + 新对话按钮
hdr1, hdr2 = st.columns([6, 1])
with hdr1:
    st.markdown("## 🤖 AI 对话")
with hdr2:
    if st.button("➕ 新对话", type="primary"):
        st.session_state.ai_current_conv = None
        st.rerun()

st.divider()

conv_id = st.session_state.ai_current_conv

# 消息历史
if conv_id:
    messages = chat_db.get_messages("general", conv_id)
    for msg in messages:
        with st.chat_message(msg["role"]):
            if msg.get("image_data"):
                try:
                    st.image(base64.b64decode(msg["image_data"]), width=300)
                except Exception:
                    pass
            if msg.get("content"):
                st.markdown(msg["content"])
else:
    st.info("👋 在下方输入问题开始新对话，或从左侧选择历史对话。")

# 底部输入区
st.divider()

# 图片上传 + 语音输入（右下角风格）
upload_col1, upload_col2, upload_col3 = st.columns([5, 1, 1])
with upload_col2:
    uploaded_img = st.file_uploader("📷", type=["jpg", "jpeg", "png", "webp"],
                                     key="ai_img", label_visibility="collapsed")
with upload_col3:
    audio_bytes = None
    try:
        audio_rec = st.audio_input("🎤", key="ai_voice", label_visibility="collapsed")
        if audio_rec:
            audio_bytes = audio_rec.getvalue()
    except AttributeError:
        audio_file = st.file_uploader("🎤", type=["wav", "mp3", "m4a"],
                                       key="ai_audio", label_visibility="collapsed")
        if audio_file:
            audio_bytes = audio_file.getvalue()

# 图片预览
if uploaded_img:
    img_bytes = uploaded_img.getvalue()
    st.image(img_bytes, caption="待发送图片", width=200)

# 聊天输入
if prompt := st.chat_input("输入医学问题..."):
    # 自动创建新对话
    if not conv_id:
        conv_id = chat_db.new_conversation_id()
        st.session_state.ai_current_conv = conv_id

    # 处理图片
    image_b64 = ""
    if uploaded_img:
        image_b64 = base64.b64encode(uploaded_img.getvalue()).decode()

    # 保存用户消息
    chat_db.create("general", conv_id, "user", prompt, image_data=image_b64, model_used=model)

    # 构建 system prompt
    from prompts.prompt_builder import build_system_prompt

    mode_instructions = {
        "command": "请以指令模式回复：直接、简洁，只给出核心答案和行动建议。",
        "discussion": "请以讨论模式回复：展开分析，列出依据和考量因素。",
        "teaching": "请以教学模式回复：系统性讲解，从基础到临床应用，如同教学查房。",
    }
    system_prompt = build_system_prompt(include_rules=False)
    system_prompt += "\n\n## 教学模式指令\n" + mode_instructions.get(teaching_mode, "")

    # 加载对话历史
    all_msgs = chat_db.get_messages("general", conv_id)
    api_messages = []
    for m in all_msgs:
        if m["role"] in ("user", "assistant"):
            api_messages.append({"role": m["role"], "content": m["content"]})

    # 调用 API
    from core.deepseek_client import get_api_key, get_client, chat_stream, chat_vision_stream

    if not get_api_key():
        st.error("请先在「设置」页面配置 API Key")
    else:
        with st.chat_message("user"):
            if image_b64:
                st.image(base64.b64decode(image_b64), width=200)
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""

            if image_b64:
                stream = chat_vision_stream(system_prompt, prompt, image_b64, model=model)
            else:
                stream = chat_stream(system_prompt, messages=api_messages, model=model)

            for chunk in stream:
                full_response += chunk
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        chat_db.create("general", conv_id, "assistant", full_response, model_used=model)
        st.rerun()
