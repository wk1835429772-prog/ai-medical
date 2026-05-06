"""AI 对话页面 — 纯文本对话"""

import streamlit as st

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
if "_ai_processed_prompts" not in st.session_state:
    st.session_state._ai_processed_prompts = set()

# ══════════════════════════════════════════════
# 左侧边栏
# ══════════════════════════════════════════════
with st.sidebar:
    st.markdown("### 💬 AI 对话")
    convs = chat_db.get_conversations("general")
    with st.expander("📜 历史对话", expanded=True):
        if not convs:
            st.caption("暂无历史对话")
        for conv in convs:
            cid = conv["conversation_id"]
            title = conv.get("title") or "新对话"
            dt = (title[:22] + "...") if len(title) > 22 else title
            c1, c2, c3 = st.columns([5, 1, 1])
            with c1:
                if st.button(dt, key=f"sel_{cid}", use_container_width=True):
                    st.session_state.ai_current_conv = cid
                    st.session_state._ai_processed_prompts = set()
                    st.rerun()
            with c2:
                if st.button("📌", key=f"pin_{cid}", help="置顶"):
                    st.toast("已置顶")
            with c3:
                if st.button("🗑️", key=f"del_{cid}", help="删除"):
                    chat_db.delete_conversation("general", cid)
                    if st.session_state.ai_current_conv == cid:
                        st.session_state.ai_current_conv = None
                    st.rerun()
    st.divider()
    teaching_mode = st.select_slider(
        "教学深度", options=list(TEACHING_MODES.keys()),
        format_func=lambda x: TEACHING_MODES[x]["label"], value="discussion",
    )
    st.caption(TEACHING_MODES[teaching_mode]["description"])
    model = st.radio("模型", ["deepseek-v4-flash", "deepseek-v4-pro"], horizontal=True, index=0)

# ══════════════════════════════════════════════
# 主区域
# ══════════════════════════════════════════════
hdr1, hdr2 = st.columns([6, 1])
with hdr1:
    st.markdown("## 🤖 AI 对话")
with hdr2:
    if st.button("➕ 新对话", type="primary"):
        st.session_state.ai_current_conv = None
        st.session_state._ai_processed_prompts = set()
        st.rerun()

st.divider()

conv_id = st.session_state.ai_current_conv

# ─── 消息历史 ───
if conv_id:
    messages = chat_db.get_messages("general", conv_id)
    for msg in messages:
        with st.chat_message(msg["role"]):
            if msg.get("content"):
                st.markdown(msg["content"])

# ─── 对话输入 ───
prompt = st.chat_input("输入医学问题...")

if prompt:
    if not conv_id:
        conv_id = chat_db.new_conversation_id()
        st.session_state.ai_current_conv = conv_id

    _dedup_key = f"{conv_id}|{prompt[:100]}"
    if _dedup_key in st.session_state._ai_processed_prompts:
        st.stop()

    chat_db.create("general", conv_id, "user", prompt, model_used=model)

    from prompts.prompt_builder import build_system_prompt
    mode_map = {
        "command": "请以指令模式回复：直接、简洁，只给出核心答案和行动建议。",
        "discussion": "请以讨论模式回复：展开分析，列出依据和考量因素。",
        "teaching": "请以教学模式回复：系统性讲解，从基础到临床应用，如同教学查房。",
    }
    system_prompt = build_system_prompt(include_rules=False)
    system_prompt += "\n\n## 教学模式指令\n" + mode_map.get(teaching_mode, "")

    all_msgs = chat_db.get_messages("general", conv_id)
    api_messages = [{"role": m["role"], "content": m["content"]}
                    for m in all_msgs if m["role"] in ("user", "assistant")]

    from core.deepseek_client import get_api_key, chat_stream

    if not get_api_key():
        st.error("请先在「设置」页面配置 API Key")
    else:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            stream = chat_stream(system_prompt, messages=api_messages, model=model)
            for chunk in stream:
                full_response += chunk
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        chat_db.create("general", conv_id, "assistant", full_response, model_used=model)
        st.session_state._ai_processed_prompts.add(_dedup_key)
        st.rerun()
