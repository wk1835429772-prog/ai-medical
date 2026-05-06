"""AI 对话页面 — 仿 LobeChat/DeepSeek：输入框 + 语音/图片按钮"""

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

# ─── 页面专属 CSS：覆盖全局移动端堆叠，让输入按钮始终并排 ───
st.markdown("""
<style>
/* 输入按钮行：桌面 + 移动端都保持并排 */
.chat-input-row {
    display: flex !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 8px !important;
    width: 100% !important;
}
.chat-input-row > div {
    flex: none !important;
    min-width: 0 !important;
    max-width: none !important;
}
.chat-input-row > div:first-child {
    flex: 1 1 0% !important;
}
.chat-input-row > div:not(:first-child) {
    width: 44px !important;
    flex: 0 0 44px !important;
}
.chat-input-row .stButton > button {
    padding: 4px 8px !important;
    font-size: 1.1rem !important;
    min-height: 38px !important;
    min-width: 38px !important;
    border-radius: 50% !important;
    line-height: 1 !important;
}
.chat-input-row .stPopover > div > button {
    padding: 4px 8px !important;
    font-size: 1.1rem !important;
    min-height: 38px !important;
    min-width: 38px !important;
    border-radius: 50% !important;
    line-height: 1 !important;
}
/* 录制器行 */
.voice-recorder-row {
    display: flex !important;
    flex-wrap: nowrap !important;
    align-items: center !important;
    gap: 8px !important;
}
.voice-recorder-row > div:first-child {
    flex: 1 1 0% !important;
}
.voice-recorder-row > div:not(:first-child) {
    width: 60px !important;
    flex: 0 0 60px !important;
}
</style>
""", unsafe_allow_html=True)

# ─── Session state ───
_defaults = {
    "ai_current_conv": None,
    "_ai_voice_counter": 0,
    "_ai_voice_transcript": "",
    "_ai_voice_recording": False,
    "_ai_voice_processing": False,
    "_ai_image": "",
    "_ai_processed_prompts": set(),
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── 语音自动识别（widget 渲染前处理） ───
if st.session_state._ai_voice_processing:
    voice_key = f"_vrec_{st.session_state._ai_voice_counter}"
    audio_rec = st.session_state.get(voice_key)
    if audio_rec:
        with st.spinner("正在识别语音..."):
            try:
                import speech_recognition as sr
                from pydub import AudioSegment
                recognizer = sr.Recognizer()
                audio_bytes = audio_rec.getvalue()
                try:
                    seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
                except Exception:
                    seg = AudioSegment.from_wav(io.BytesIO(audio_bytes))
                buf = io.BytesIO()
                seg.export(buf, format="wav")
                buf.seek(0)
                with sr.AudioFile(buf) as src:
                    audio_data = recognizer.record(src)
                text = recognizer.recognize_google(audio_data, language="zh-CN")
                st.session_state._ai_voice_transcript = text
            except ImportError:
                st.error("请安装语音依赖：pip install SpeechRecognition pydub")
            except sr.UnknownValueError:
                st.warning("无法识别语音内容，请重新录制")
            except sr.RequestError as e:
                st.error(f"语音服务不可用：{e}")
            except Exception as e:
                st.error(f"音频处理失败：{e}")
        # 无论成功失败，结束处理状态，重置录制器
        st.session_state._ai_voice_processing = False
        st.session_state._ai_voice_recording = False
        st.session_state._ai_voice_counter += 1
        st.rerun()
    else:
        st.session_state._ai_voice_processing = False

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
                    st.session_state._ai_voice_transcript = ""
                    st.session_state._ai_processed_prompts = set()
                    st.rerun()
            with c2:
                if st.button("📌", key=f"pin_{cid}", help="置顶"):
                    st.toast(f"已置顶")
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
        st.session_state._ai_voice_transcript = ""
        st.session_state._ai_image = ""
        st.session_state._ai_voice_recording = False
        st.session_state._ai_processed_prompts = set()
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
if not conv_id and not st.session_state._ai_voice_transcript:
    st.info("💬 在下方输入问题开始新对话")

# ══════════════════════════════════════════════
# 底部输入区
# ══════════════════════════════════════════════
st.divider()

# ─── 语音录制器（点🎤后展开） ───
if st.session_state._ai_voice_recording:
    wkey = f"_vrec_{st.session_state._ai_voice_counter}"
    st.markdown('<div class="voice-recorder-row">', unsafe_allow_html=True)
    rec_c1, rec_c2 = st.columns([5, 1])
    with rec_c1:
        audio_data = st.audio_input("录制语音", key=wkey, label_visibility="collapsed")
    with rec_c2:
        if st.button("✔", key="_voice_ok", help="完成录制，开始识别", use_container_width=True):
            if audio_data:
                st.session_state._ai_voice_processing = True
                st.rerun()
            else:
                st.warning("请先录制语音")
    st.markdown('</div>', unsafe_allow_html=True)
    # 如果音频录制完成且用户点了✔，会在下次 rerun 时处理
    # 如果用户录制完但没点✔，也可以自动检测到音频变化
    if audio_data and not st.session_state._ai_voice_processing:
        # 有录音数据但还没点确认，显示提示
        st.caption("🎤 已录制，点击 ✔ 开始识别")

# ─── 图片预览 ───
if st.session_state._ai_image:
    pv1, pv2 = st.columns([4, 1])
    with pv1:
        st.image(base64.b64decode(st.session_state._ai_image), width=140, caption="待发送图片")
    with pv2:
        if st.button("✖", key="_rm_img", help="移除图片"):
            st.session_state._ai_image = ""
            st.rerun()

# ─── 语音识别结果（可编辑） ───
if st.session_state._ai_voice_transcript:
    voice_text = st.text_area(
        "语音识别结果（可编辑后发送）",
        value=st.session_state._ai_voice_transcript,
        key="_vtxt", height=60,
    )
    vt1, vt2 = st.columns([4, 1])
    with vt1:
        if st.button("📤 发送语音内容", type="primary", use_container_width=True):
            prompt_to_send = voice_text
            st.session_state._ai_voice_transcript = ""
            # 标记为需要处理
            st.session_state["_pending_voice_prompt"] = prompt_to_send
            st.rerun()
    with vt2:
        if st.button("清除", key="_clr_voice", use_container_width=True):
            st.session_state._ai_voice_transcript = ""
            st.rerun()

# ─── 主输入行：对话框 + 🎤 + ➕ ───
st.markdown('<div class="chat-input-row">', unsafe_allow_html=True)
in_c1, in_c2, in_c3 = st.columns([6, 1, 1])
with in_c1:
    prompt = st.chat_input("输入医学问题...")
with in_c2:
    if st.button("🎤", key="_mic_btn", help="语音输入"):
        st.session_state._ai_voice_recording = not st.session_state._ai_voice_recording
        st.rerun()
with in_c3:
    with st.popover("➕", use_container_width=True):
        uploaded_img = st.file_uploader("选择图片", type=["jpg","jpeg","png","webp"],
                                        key="_img_up", label_visibility="visible")
        if uploaded_img:
            st.session_state._ai_image = base64.b64encode(uploaded_img.getvalue()).decode()
            st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════
# 统一处理消息发送
# ══════════════════════════════════════════════
# 确定要发送的内容
send_prompt = None
if prompt:
    send_prompt = prompt
elif "_pending_voice_prompt" in st.session_state:
    send_prompt = st.session_state.pop("_pending_voice_prompt")

if send_prompt:
    processed = st.session_state._ai_processed_prompts
    # 防重复：跳过已处理的消息
    _dedup_key = f"{conv_id}|{send_prompt[:100]}"
    if _dedup_key in processed:
        send_prompt = None

if send_prompt:
    if not conv_id:
        conv_id = chat_db.new_conversation_id()
        st.session_state.ai_current_conv = conv_id

    image_b64 = st.session_state.get("_ai_image", "")
    chat_db.create("general", conv_id, "user", send_prompt, image_data=image_b64, model_used=model)

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

    from core.deepseek_client import get_api_key, chat_stream, chat_vision_stream

    if not get_api_key():
        st.error("请先在「设置」页面配置 API Key")
    else:
        with st.chat_message("user"):
            if image_b64:
                st.image(base64.b64decode(image_b64), width=200)
            st.markdown(send_prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""
            if image_b64:
                stream = chat_vision_stream(system_prompt, send_prompt, image_b64, model=model)
            else:
                stream = chat_stream(system_prompt, messages=api_messages, model=model)
            for chunk in stream:
                full_response += chunk
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        chat_db.create("general", conv_id, "assistant", full_response, model_used=model)
        st.session_state._ai_image = ""
        st.session_state._ai_processed_prompts.add(_dedup_key)
        st.rerun()
