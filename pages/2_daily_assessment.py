"""今日评估页面 - 核心：生命体征概览 + 七维日卡 + 治疗方案 + AI 汇报"""

import streamlit as st
from datetime import date, timedelta

from core.database import init_database
init_database()

from config import DIMENSIONS
import models.patient as patient_db
import models.daily_card as card_db
from core.calculator import calc_map, calc_oi, calc_balance, calc_postop_days, check_critical

st.set_page_config(page_title="今日评估 - 临床助手", page_icon="📝", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()

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
                    # 内联 OI 计算（血气分析组之后）
                    if dim["key"] == "respiration" and group.get("label") == "血气分析":
                        pao2_val = get_field_val("abg_pao2")
                        fio2_val = get_field_val("vent_fio2")
                        oi = calc_oi(pao2_val, fio2_val)
                        if oi is not None:
                            st.caption(f"↳ 氧合指数 OI = **{oi}**")

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
# 右栏：AI 汇报
# ══════════════════════════════════════════════
with right_col:
    st.subheader("🤖 AI 汇报")

    # 模型选择
    report_model = st.radio(
        "模型",
        ["deepseek-v4-flash", "deepseek-v4-pro"],
        horizontal=True,
        index=0,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 生成今日汇报", type="primary", use_container_width=True):
            from prompts.prompt_builder import build_system_prompt, build_report_prompt
            from core.deepseek_client import chat_stream

            save_data = collect_save_data()
            if save_data:
                daily_card = card_db.save(selected_id, data_date_str, save_data)
            else:
                daily_card = card_db.get_or_create(selected_id, data_date_str)

            system_prompt = build_system_prompt(include_rules=True)
            user_prompt = build_report_prompt(patient, daily_card)

            st.session_state["report_stream"] = chat_stream(system_prompt, user_prompt, report_model)
            st.session_state["report_content"] = ""

    with col2:
        if st.button("🔄 生成交班报告", use_container_width=True):
            from prompts.prompt_builder import build_system_prompt, build_patient_context
            from core.deepseek_client import chat_stream

            daily_card_data = card_db.get_or_create(selected_id, data_date_str)
            ctx = build_patient_context(patient, daily_card_data)
            user_prompt = f"请根据以下患者信息生成规范的交班报告：\n\n{ctx}"
            system_prompt = build_system_prompt(include_rules=True)
            st.session_state["report_stream"] = chat_stream(system_prompt, user_prompt, report_model)
            st.session_state["report_content"] = ""

    st.divider()

    # 流式输出面板
    if "report_content" not in st.session_state:
        st.session_state["report_content"] = ""

    output_placeholder = st.empty()

    if "report_stream" in st.session_state and st.session_state["report_stream"]:
        report_iter = st.session_state["report_stream"]
        content = ""
        for chunk in report_iter:
            content += chunk
            output_placeholder.markdown(content)
        st.session_state["report_content"] = content
        st.session_state["report_stream"] = None

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 下载汇报",
                content,
                file_name=f"report_{patient['name_abbr']}_{data_date_str}.txt",
                mime="text/plain",
            )
        with col2:
            if st.button("📋 一键复制"):
                st.code(content, language=None)
                st.success("已显示纯文本格式，可手动复制")
    elif st.session_state["report_content"]:
        output_placeholder.markdown(st.session_state["report_content"])
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 下载汇报",
                st.session_state["report_content"],
                file_name=f"report_{patient['name_abbr']}_{data_date_str}.txt",
                mime="text/plain",
            )
    else:
        output_placeholder.info("点击「生成今日汇报」开始 AI 分析")

# ─── 底部 ───
st.divider()
st.caption(f"💡 所有数据保存在本地 SQLite，AI 调用仅发送脱敏后的临床文本。当前患者：{patient['name_abbr']} | 日期：{data_date_str}")
