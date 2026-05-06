"""AI 对话页面 — DeepSeek 风格：对话列表 + 语音/图片上传 + 对话框发送"""

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

st.markdown("""
<style>
/* 紧凑按钮样式 */
div[data-testid="stHorizontalBlock"] .stButton > button {
    padding: 4px 12px !important;
    font-size: 0.85rem !important;
    min-height: 36px !important;
    border-radius: 18px !important;
}
/* popover 触发按钮 */
div[data-testid="stPopover"] > div > button {
    padding: 4px 14px !important;
    font-size: 0.85rem !important;
    min-height: 36px !important;
    border-radius: 18px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Session state ───
if "ai_current_conv" not in st.session_state:
    st.session_state.ai_current_conv = None
if "_ai_voice_counter" not in st.session_state:
    st.session_state._ai_voice_counter = 0
if "_ai_voice_transcript" not in st.session_state:
    st.session_state._ai_voice_transcript = ""
if "_ai_voice_recorder_visible" not in st.session_state:
    st.session_state._ai_voice_recorder_visible = False
if "_ai_voice_pending" not in st.session_state:
    st.session_state._ai_voice_pending = False
if "_ai_image" not in st.session_state:
    st.session_state._ai_image = ""

# ─── 处理语音识别（widget 渲染前） ───
if st.session_state._ai_voice_pending:
    voice_key = f"_voice_rec_{st.session_state._ai_voice_counter}"
    audio_rec = st.session_state.get(voice_key)
    if audio_rec:
        with st.spinner("识别中..."):
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
                st.session_state._ai_voice_pending = False
                st.session_state._ai_voice_recorder_visible = False
                st.session_state._ai_voice_counter += 1
                st.rerun()
            except ImportError:
                st.error("语音识别依赖未安装：pip install SpeechRecognition pydub")
                st.session_state._ai_voice_pending = False
                st.session_state._ai_voice_recorder_visible = False
            except sr.UnknownValueError:
                st.warning("无法识别，请重新录制")
                st.session_state._ai_voice_pending = False
                st.session_state._ai_voice_recorder_visible = False
                st.session_state._ai_voice_counter += 1
                st.rerun()
            except sr.RequestError as e:
                st.error(f"语音服务不可用：{e}")
                st.session_state._ai_voice_pending = False
                st.session_state._ai_voice_recorder_visible = False
            except Exception as e:
                st.error(f"处理失败：{e}")
                st.session_state._ai_voice_pending = False
                st.session_state._ai_voice_recorder_visible = False

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
        "模型", ["deepseek-v4-flash", "deepseek-v4-pro"],
        horizontal=True, index=0,
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
        st.session_state._ai_voice_transcript = ""
        st.session_state._ai_image = ""
        st.session_state._ai_voice_recorder_visible = False
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

# ─── 无对话提示 ───
if not conv_id:
    st.info("💬 在下方输入问题开始新对话")

# ══════════════════════════════════════════════
# 底部输入区
# ══════════════════════════════════════════════
st.divider()

# ─── 语音录制器（点击麦克风后展开） ───
if st.session_state._ai_voice_recorder_visible:
    voice_widget_key = f"_voice_rec_{st.session_state._ai_voice_counter}"
    recorder_c1, recorder_c2 = st.columns([4, 1])
    with recorder_c1:
        st.audio_input("录制语音", key=voice_widget_key, label_visibility="visible")
    with recorder_c2:
        if st.button("识别", key="_voice_recognize", use_container_width=True):
            st.session_state._ai_voice_pending = True
            st.rerun()

# ─── 图片预览 ───
if st.session_state._ai_image:
    preview_c1, preview_c2 = st.columns([3, 1])
    with preview_c1:
        st.image(base64.b64decode(st.session_state._ai_image), width=150, caption="待发送")
    with preview_c2:
        if st.button("❌ 移除"):
            st.session_state._ai_image = ""
            st.rerun()

# ─── 主输入行：对话框 + 语音/图片按钮 ───
input_c1, input_c2, input_c3 = st.columns([6, 1, 1])

with input_c1:
    prompt = st.chat_input("输入医学问题...")

with input_c2:
    # 麦克风按钮 — 切换录制器显隐
    if st.button("🎤", key="_btn_mic", help="语音输入"):
        st.session_state._ai_voice_recorder_visible = not st.session_state._ai_voice_recorder_visible
        st.rerun()

with input_c3:
    # 图片上传 — popover 弹出选择器
    with st.popover("➕", use_container_width=True):
        uploaded_img = st.file_uploader(
            "选择图片", type=["jpg", "jpeg", "png", "webp"],
            key="_img_upload",
            label_visibility="visible",
        )
        if uploaded_img:
            st.session_state._ai_image = base64.b64encode(uploaded_img.getvalue()).decode()
            st.rerun()

# ─── 语音识别结果 ───
if st.session_state._ai_voice_transcript:
    voice_text = st.text_area(
        "语音识别结果（可编辑）",
        value=st.session_state._ai_voice_transcript,
        key="_voice_edit",
        height=68,
    )
    vc1, vc2 = st.columns([4, 1])
    with vc1:
        if st.button("📤 发送语音内容", type="primary", use_container_width=True):
            prompt = voice_text
            st.session_state._ai_voice_transcript = ""
            st.session_state._ai_voice_counter += 1
    with vc2:
        if st.button("清除", use_container_width=True):
            st.session_state._ai_voice_transcript = ""
            st.rerun()

# ══════════════════════════════════════════════
# 处理消息
# ══════════════════════════════════════════════
if prompt:
    if not conv_id:
        conv_id = chat_db.new_conversation_id()
        st.session_state.ai_current_conv = conv_id

    image_b64 = st.session_state.get("_ai_image", "")
    chat_db.create("general", conv_id, "user", prompt, image_data=image_b64, model_used=model)

    from prompts.prompt_builder import build_system_prompt
    mode_instructions = {
        "command": "请以指令模式回复：直接、简洁，只给出核心答案和行动建议。",
        "discussion": "请以讨论模式回复：展开分析，列出依据和考量因素。",
        "teaching": "请以教学模式回复：系统性讲解，从基础到临床应用，如同教学查房。",
    }
    system_prompt = build_system_prompt(include_rules=False)
    system_prompt += "\n\n## 教学模式指令\n" + mode_instructions.get(teaching_mode, "")

    all_msgs = chat_db.get_messages("general", conv_id)
    api_messages = [{"role": m["role"], "content": m["content"]} for m in all_msgs if m["role"] in ("user", "assistant")]

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
        st.session_state._ai_image = ""
        st.rerun()
