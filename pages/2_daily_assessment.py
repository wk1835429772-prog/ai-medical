"""今日评估页面 - 核心：生命体征概览 + 七维日卡 + 治疗方案 + AI 对话"""

import streamlit as st
from datetime import date, timedelta
import base64

from core.database import init_database
init_database()

from config import DIMENSIONS
import models.patient as patient_db
import models.daily_card as card_db
import models.chat_message as chat_db
from core.calculator import calc_map, calc_oi, calc_balance, calc_postop_days, check_critical

st.set_page_config(page_title="今日评估 - 临床助手", page_icon="📝", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()

# ─── Session state defaults ───
if "current_conv_id" not in st.session_state:
    st.session_state.current_conv_id = None
if "chat_image" not in st.session_state:
    st.session_state.chat_image = None

# ─── Helper functions ───

def show_critical(key, value):
    is_crit, label = check_critical(key, value)
    if is_crit:
        st.error(label)


def get_field_val(field_key: str):
    for d in DIMENSIONS:
        key = f"{d['key']}_{field_key}"
        if key in st.session_state:
            return st.session_state[key]
    return None


def render_field_input(dim_key: str, f: dict, current_val):
    field_key = f"{dim_key}_{f['key']}"
    step = float(f.get("step", 1.0))
    if f["type"] == "number":
        decimal_places = len(str(step).split(".")[-1]) if "." in str(step) else 0
        val = st.number_input(
            f["label"],
            value=float(current_val) if current_val is not None else None,
            step=step,
            format=f"%.{decimal_places}f" if decimal_places else "%g",
            key=field_key,
            placeholder="未填",
        )
        show_critical(f["key"], val)
    else:
        st.text_input(
            f["label"],
            value=str(current_val) if current_val else "",
            key=field_key,
            placeholder="未填",
        )


VITAL_FIELD_KEYS = {"bp_sys", "bp_dia", "hr", "spo2", "rr", "temp", "intake_vol", "output_vol", "stool_vol"}


def collect_save_data() -> dict:
    save_data = {}
    # 生命体征概览区的值（vital_* 前缀）
    for vk in VITAL_FIELD_KEYS:
        widget_key = f"vital_{vk}"
        if widget_key in st.session_state:
            save_data[vk] = st.session_state[widget_key]
    # 七维字段
    for dim in DIMENSIONS:
        for f in dim["today_fields"]:
            key = f"{dim['key']}_{f['key']}"
            if key in st.session_state:
                save_data[f["key"]] = st.session_state[key]
        for f in dim["yesterday_fields"]:
            key = f"{dim['key']}_{f['key']}"
            if key in st.session_state:
                save_data[f["key"]] = st.session_state[key]
        notes_key = dim.get("notes_key")
        if notes_key:
            widget_key = f"{dim['key']}_notes"
            if widget_key in st.session_state:
                save_data[notes_key] = st.session_state[widget_key]
    if "current_diagnosis" in st.session_state:
        save_data["current_diagnosis"] = st.session_state.current_diagnosis
    if "treatment_plan" in st.session_state:
        save_data["treatment_plan"] = st.session_state.treatment_plan
    return save_data


def render_inline_calc(calculate_fn, *args):
    result = calculate_fn(*args)
    if result is not None:
        if isinstance(result, dict):
            st.caption(f"**{result['main']}**")
        else:
            st.caption(f"**{result}**")


# ══════════════════════════════════════════════
# 顶部：患者选择 + 日期导航
# ══════════════════════════════════════════════
patients = patient_db.get_all()
if not patients:
    st.warning("暂无患者，请先在「患者管理」中添加。")
    st.stop()

patient_id = st.session_state.get("current_patient_id")
patient_names = {p["id"]: p["name_abbr"] for p in patients}
selected_id = st.selectbox(
    "选择患者",
    options=list(patient_names.keys()),
    format_func=lambda x: f"{patient_names[x]} ({'🔴' if next((p for p in patients if p['id']==x), {}).get('is_critical')==2 else '🟢'})",
    index=list(patient_names.keys()).index(patient_id) if patient_id in patient_names else 0,
)
patient = patient_db.get_by_id(selected_id)
if not patient:
    st.error("患者不存在")
    st.stop()

# 日期导航
col1, col2, col3, col4 = st.columns([1, 2, 2, 1])
with col1:
    if "card_date" not in st.session_state:
        st.session_state.card_date = date.today()
    if st.button("◀ 前一天"):
        st.session_state.card_date = st.session_state.card_date - timedelta(days=1)
        st.rerun()
with col2:
    card_date = st.date_input("数据日期", value=st.session_state.card_date, key="date_picker")
    st.session_state.card_date = card_date
with col3:
    postop = calc_postop_days(patient.get("surgery_date"))
    if postop is not None:
        st.metric("术后日数", f"D{postop}")
with col4:
    if st.button("后一天 ▶"):
        st.session_state.card_date = st.session_state.card_date + timedelta(days=1)
        st.rerun()

# 加载日卡
data_date_str = card_date.isoformat()
daily_card = card_db.get_or_create(selected_id, data_date_str)

st.divider()

# ══════════════════════════════════════════════
# 保存按钮
# ══════════════════════════════════════════════
if st.button("💾 保存所有数据", type="primary", use_container_width=True):
    save_data = collect_save_data()
    card_db.save(selected_id, data_date_str, save_data)
    st.success("✅ 所有数据已保存")
    st.rerun()

st.divider()

# ══════════════════════════════════════════════
# 左右两栏布局
# ══════════════════════════════════════════════
left_col, right_col = st.columns([3, 2])

with left_col:

    # ─── 生命体征概览（可编辑） ───
    st.subheader("📊 生命体征")

    cols = st.columns(6)
    vitals_config = [
        ("bp_sys", "收缩压", 1, "%.0f"),
        ("bp_dia", "舒张压", 1, "%.0f"),
        ("hr", "心率", 1, "%.0f"),
        ("spo2", "SpO₂", 1, "%.0f"),
        ("rr", "RR", 1, "%.0f"),
        ("temp", "体温", 0.1, "%.1f"),
    ]
    for i, (key, label, step, fmt) in enumerate(vitals_config):
        with cols[i]:
            st.number_input(
                label,
                value=float(daily_card.get(key)) if daily_card.get(key) is not None else None,
                step=float(step),
                format=fmt,
                key=f"vital_{key}",
                placeholder="—",
            )

    # 第二行：出入量
    io_cols = st.columns(3)
    io_config = [
        ("intake_vol", "总入量 (mL)", 50, "%.0f"),
        ("output_vol", "总出量 (mL)", 50, "%.0f"),
        ("stool_vol", "大便量 (mL)", 50, "%.0f"),
    ]
    for i, (key, label, step, fmt) in enumerate(io_config):
        with io_cols[i]:
            st.number_input(
                label,
                value=float(daily_card.get(key)) if daily_card.get(key) is not None else None,
                step=float(step),
                format=fmt,
                key=f"vital_{key}",
                placeholder="—",
            )

    # 内联计算：MAP + 出入量 + OI
    bp_sys_val = st.session_state.get("vital_bp_sys")
    bp_dia_val = st.session_state.get("vital_bp_dia")
    map_val = calc_map(bp_sys_val, bp_dia_val)
    intake_val = st.session_state.get("vital_intake_vol")
    output_val = st.session_state.get("vital_output_vol")
    bal_val = calc_balance(intake_val, output_val)

    calc_parts = []
    if map_val is not None:
        calc_parts.append(f"MAP **{map_val}** mmHg")
    if bal_val is not None:
        calc_parts.append(f"出入量平衡 **{bal_val:+.0f}** mL")
    if calc_parts:
        st.caption(" | ".join(calc_parts))

    st.divider()

    # ─── 当前诊断 ───
    st.subheader("🏥 当前诊断")
    st.text_area(
        "今日诊断",
        value=daily_card.get("current_diagnosis", "") or "",
        key="current_diagnosis",
        height=80,
        placeholder="输入今日诊断...",
        label_visibility="collapsed",
    )

    st.divider()

    # ─── 七大维度折叠卡片 ───
    st.subheader("📋 临床数据")

    for dim in DIMENSIONS:
        with st.expander(f"{dim['icon']} {dim['name']}", expanded=False):

            # 今日晨 7:00 数据（跳过已在生命体征概览中渲染的字段）
            today_groups = dim.get("today_groups", [])
            if today_groups:
                st.markdown("##### 🌅 今日晨7:00")
                for group in today_groups:
                    fields = [f for f in group["fields"] if f["key"] not in VITAL_FIELD_KEYS]
                    if not fields:
                        continue
                    if group.get("label"):
                        st.markdown(f'<p class="group-label">{group["label"]}</p>', unsafe_allow_html=True)
                    cols = st.columns(min(4, max(1, len(fields))))
                    for i, f in enumerate(fields):
                        with cols[i % min(4, max(1, len(fields)))]:
                            current_val = daily_card.get(f["key"])
                            render_field_input(dim["key"], f, current_val)

            # 昨日结果
            if dim["yesterday_fields"]:
                st.markdown("##### 🌙 昨日结果")
                cols = st.columns(min(4, len(dim["yesterday_fields"])))
                for i, f in enumerate(dim["yesterday_fields"]):
                    with cols[i % min(4, len(dim["yesterday_fields"]))]:
                        current_val = daily_card.get(f["key"])
                        render_field_input(dim["key"], f, current_val)

            # 自由文本备注
            notes_key = dim.get("notes_key")
            if notes_key:
                st.text_area(
                    f"{dim['name']}备注",
                    value=daily_card.get(notes_key, "") or "",
                    key=f"{dim['key']}_notes",
                    height=80,
                    placeholder=f"输入{dim['name']}相关补充说明...",
                    label_visibility="collapsed",
                )

    st.divider()

    # ─── 治疗方案 ───
    st.subheader("💊 治疗方案")
    st.text_area(
        "今日治疗方案",
        value=daily_card.get("treatment_plan", "") or "",
        key="treatment_plan",
        height=120,
        placeholder="输入今日治疗方案...",
        label_visibility="collapsed",
    )

# ══════════════════════════════════════════════
# 右栏：AI 对话面板
# ══════════════════════════════════════════════
with right_col:
    st.subheader("🤖 AI 对话")

    # 对话管理
    convs = chat_db.get_conversations(selected_id)
    conv_map = {c["conversation_id"]: c for c in convs}

    c1, c2, c3 = st.columns([3, 1, 1])
    with c1:
        conv_options = [None] + [c["conversation_id"] for c in convs]
        conv_labels = {None: "➕ 新对话"}
        for c in convs:
            title = c.get("title", "新对话") or "新对话"
            conv_labels[c["conversation_id"]] = (title[:30] + "...") if len(title) > 30 else title
        sel_conv = st.selectbox(
            "对话",
            options=conv_options,
            format_func=lambda x: conv_labels.get(x, "新对话"),
            key="conv_selector",
            label_visibility="collapsed",
        )
    with c2:
        if st.button("➕", help="新建对话"):
            st.session_state.current_conv_id = None
            st.rerun()
    with c3:
        if sel_conv and st.button("🗑️", help="删除此对话"):
            chat_db.delete_conversation(selected_id, sel_conv)
            st.session_state.current_conv_id = None
            st.rerun()

    # 模型选择
    report_model = st.radio(
        "模型",
        ["deepseek-v4-flash", "deepseek-v4-pro"],
        horizontal=True,
        index=0,
    )

    st.divider()

    # 消息历史
    if sel_conv:
        st.session_state.current_conv_id = sel_conv
        messages = chat_db.get_messages(selected_id, sel_conv)
        for msg in messages:
            with st.chat_message(msg["role"]):
                if msg.get("image_data"):
                    st.image(base64.b64decode(msg["image_data"]), width=300)
                if msg.get("content"):
                    st.markdown(msg["content"])
    else:
        st.session_state.current_conv_id = None
        st.info("输入问题开始新对话，AI 将自动关联当前患者数据。")

    # 图片/语音上传区
    upload_cols = st.columns(2)
    with upload_cols[0]:
        uploaded_img = st.file_uploader("📷 上传图片", type=["jpg", "jpeg", "png", "webp"], key="chat_img_upload")
    with upload_cols[1]:
        audio_bytes = None
        try:
            audio_rec = st.audio_input("🎤 语音输入", key="chat_voice")
            if audio_rec:
                audio_bytes = audio_rec.getvalue()
        except AttributeError:
            audio_file = st.file_uploader("🎤 上传音频", type=["wav", "mp3", "m4a"], key="chat_audio_upload")
            if audio_file:
                audio_bytes = audio_file.getvalue()

    # 处理图片上传
    if uploaded_img:
        img_bytes = uploaded_img.getvalue()
        st.session_state.chat_image = base64.b64encode(img_bytes).decode()
        st.image(img_bytes, caption="待发送图片", width=200)

    # 聊天输入
    if prompt := st.chat_input("输入问题..."):
        # 自动创建新对话
        if not sel_conv:
            conv_id = chat_db.new_conversation_id()
            st.session_state.current_conv_id = conv_id
        else:
            conv_id = sel_conv

        # 准备图片
        image_b64 = st.session_state.chat_image if st.session_state.chat_image else ""

        # 保存用户消息
        chat_db.create(selected_id, conv_id, "user", prompt, image_data=image_b64, model_used=report_model)

        # 构建 system prompt
        from prompts.prompt_builder import build_system_prompt, build_patient_context

        daily_card_data = card_db.get_or_create(selected_id, data_date_str)
        patient_ctx = build_patient_context(patient, daily_card_data)
        system_prompt = build_system_prompt(include_rules=True)
        system_prompt += f"\n\n{patient_ctx}"

        # 加载对话历史
        all_msgs = chat_db.get_messages(selected_id, conv_id)
        api_messages = []
        for m in all_msgs:
            if m["role"] in ("user", "assistant"):
                api_messages.append({"role": m["role"], "content": m["content"]})

        # 调用 API
        from core.deepseek_client import chat_stream, chat_vision_stream

        st.session_state.chat_image = None

        with st.chat_message("user"):
            if image_b64:
                st.image(base64.b64decode(image_b64), width=200)
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            full_response = ""

            if image_b64:
                stream = chat_vision_stream(system_prompt, prompt, image_b64, model=report_model)
            else:
                stream = chat_stream(system_prompt, messages=api_messages, model=report_model)

            for chunk in stream:
                full_response += chunk
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)

        # 保存 assistant 回复
        chat_db.create(selected_id, conv_id, "assistant", full_response, model_used=report_model)
        st.rerun()

# ─── 底部 ───
st.divider()
st.caption(f"💡 所有数据保存在本地 SQLite，AI 调用仅发送脱敏后的临床文本。当前患者：{patient['name_abbr']} | 日期：{data_date_str}")
