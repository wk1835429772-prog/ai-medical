"""AI 对话页面 — DeepSeek 风格：左侧对话列表 + 右侧聊天 + 语音/图片"""

import streamlit as st
import base64
import io

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
if "_ai_voice_counter" not in st.session_state:
    st.session_state._ai_voice_counter = 0
if "_ai_voice_transcript" not in st.session_state:
    st.session_state._ai_voice_transcript = ""

# ─── 处理语音识别（在 widget 渲染前） ───
voice_key = f"ai_voice_{st.session_state._ai_voice_counter}"
audio_rec = st.session_state.get(voice_key)
if audio_rec and not st.session_state._ai_voice_transcript:
    with st.spinner("识别语音..."):
        try:
            import speech_recognition as sr
            from pydub import AudioSegment
            recognizer = sr.Recognizer()
            audio_bytes = audio_rec.getvalue()
            try:
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
            except Exception:
                audio_segment = AudioSegment.from_wav(io.BytesIO(audio_bytes))
            wav_buffer = io.BytesIO()
            audio_segment.export(wav_buffer, format="wav")
            wav_buffer.seek(0)
            with sr.AudioFile(wav_buffer) as source:
                audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data, language="zh-CN")
            st.session_state._ai_voice_transcript = text
            st.session_state._ai_voice_counter += 1
            st.rerun()
        except ImportError:
            st.error("语音识别依赖未安装：pip install SpeechRecognition pydub")
        except sr.UnknownValueError:
            st.warning("无法识别语音内容，请重试")
            st.session_state._ai_voice_counter += 1
            st.rerun()
        except sr.RequestError as e:
            st.error(f"语音识别服务不可用：{e}")
            st.session_state._ai_voice_counter += 1
            st.rerun()
        except Exception as e:
            st.error(f"音频处理失败：{e}")
            st.session_state._ai_voice_counter += 1
            st.rerun()

# ══════════════════════════════════════════════
# 左侧边栏：对话列表
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

# ══════════════════════════════════════════════
# 主区域
# ══════════════════════════════════════════════

hdr1, hdr2 = st.columns([6, 1])
with hdr1:
    st.markdown("## 🤖 AI 对话")
with hdr2:
    if st.button("➕ 新对话", type="primary"):
        st.session_state.ai_current_conv = None
        st.rerun()

st.divider()

conv_id = st.session_state.ai_current_conv

# ─── 消息历史 ───
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

# ══════════════════════════════════════════════
# 底部：输入区（对话框 + 语音/图片按钮）
# ══════════════════════════════════════════════
st.divider()

# 图片预览
if st.session_state.get("_ai_image"):
    st.image(base64.b64decode(st.session_state._ai_image), width=150, caption="待发送图片")
    if st.button("❌ 移除图片"):
        st.session_state._ai_image = ""
        st.rerun()

# 对话输入框
prompt = st.chat_input("输入医学问题...")

# 语音/图片按钮紧贴对话框下方
btn_c1, btn_c2, btn_c3, btn_c4 = st.columns([1, 1, 1, 5])
with btn_c1:
    st.audio_input("🎤 语音", key=f"ai_voice_{st.session_state._ai_voice_counter}")
with btn_c2:
    uploaded_img = st.file_uploader(
        "📷 图片", type=["jpg", "jpeg", "png", "webp"], key="ai_img",
        label_visibility="visible",
    )
    if uploaded_img:
        st.session_state._ai_image = base64.b64encode(uploaded_img.getvalue()).decode()
        st.rerun()
with btn_c3:
    if st.session_state._ai_voice_transcript:
        if st.button("✖ 清除", key="clear_voice"):
            st.session_state._ai_voice_transcript = ""
            st.rerun()

# 语音识别结果展示 + 发送
if st.session_state._ai_voice_transcript:
    transcript = st.text_area(
        "语音识别结果（可编辑后发送）",
        value=st.session_state._ai_voice_transcript,
        key="_voice_edit",
        height=68,
    )
    if st.button("📤 发送语音内容", type="primary"):
        prompt = transcript
        st.session_state._ai_voice_transcript = ""
        st.session_state._ai_voice_counter += 1

# ─── 处理消息 ───
if prompt:
    if not conv_id:
        conv_id = chat_db.new_conversation_id()
        st.session_state.ai_current_conv = conv_id

    image_b64 = st.session_state.get("_ai_image", "")

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
    from core.deepseek_client import get_api_key, chat_stream, chat_vision_stream

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

        # 清除图片
        st.session_state._ai_image = ""
        st.rerun()

# ─── 无对话时的提示 ───
if not conv_id and not prompt:
    st.info("💬 在下方输入问题开始新对话")
