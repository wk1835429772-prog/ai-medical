"""今日评估页面 - 核心：七维日卡录入 + AI 八项汇报"""

import streamlit as st
from datetime import date, timedelta
from config import DIMENSIONS
import models.patient as patient_db
import models.daily_card as card_db
from core.calculator import calc_map, calc_oi, calc_balance, calc_postop_days, check_critical

st.set_page_config(page_title="今日评估 - 临床助手", page_icon="📝", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()

st.title("📝 今日评估")

# --- 患者选择 ---
patient_id = st.session_state.get("current_patient_id")
patients = patient_db.get_all()
if not patients:
    st.warning("暂无患者，请先在「患者管理」中添加。")
    st.stop()

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

# --- 日期导航 ---
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

# 加载/创建日卡
data_date_str = card_date.isoformat()
daily_card = card_db.get_or_create(selected_id, data_date_str)

st.divider()

# 辅助函数：检查危急值
def show_critical(key, value):
    is_crit, label = check_critical(key, value)
    if is_crit:
        st.error(label)

# --- 左右两栏布局 ---
left_col, right_col = st.columns([3, 2])

with left_col:
    st.subheader(f"📋 {data_date_str} 日卡数据")

    # 保存按钮放在顶部
    if st.button("💾 保存日卡", type="primary", use_container_width=True):
        # 收集所有输入数据
        save_data = {}
        for dim in DIMENSIONS:
            for f in dim["today_fields"]:
                key = f"{dim['key']}_{f['key']}"
                if key in st.session_state:
                    save_data[f["key"]] = st.session_state[key]
            for f in dim["yesterday_fields"]:
                key = f"{dim['key']}_{f['key']}"
                if key in st.session_state:
                    save_data[f["key"]] = st.session_state[key]
        card_db.save(selected_id, data_date_str, save_data)
        st.success("✅ 日卡已保存")
        st.rerun()

    st.divider()

    # 七维折叠卡片
    for dim in DIMENSIONS:
        with st.expander(f"{dim['icon']} {dim['name']}", expanded=False):
            # 今日晨7:00
            if dim["today_fields"]:
                st.markdown("##### 🌅 今日晨7:00")
                cols = st.columns(min(4, len(dim["today_fields"])))
                for i, f in enumerate(dim["today_fields"]):
                    with cols[i % 4]:
                        field_key = f"{dim['key']}_{f['key']}"
                        current_val = daily_card.get(f["key"]) if daily_card else None

                        if f["type"] == "number":
                            val = st.number_input(
                                f["label"],
                                value=float(current_val) if current_val is not None else None,
                                step=f.get("step", 1.0),
                                format=f"%.{len(str(f.get('step',1)).split('.')[-1])}f" if '.' in str(f.get('step',1)) else "%g",
                                key=field_key,
                                placeholder="未填",
                            )
                            show_critical(f["key"], val)
                        else:
                            val = st.text_input(
                                f["label"],
                                value=str(current_val) if current_val else "",
                                key=field_key,
                                placeholder="未填",
                            )

            # 昨日结果
            if dim["yesterday_fields"]:
                st.markdown("##### 🌙 昨日结果")
                cols = st.columns(min(4, len(dim["yesterday_fields"])))
                for i, f in enumerate(dim["yesterday_fields"]):
                    with cols[i % 4]:
                        field_key = f"{dim['key']}_{f['key']}"
                        current_val = daily_card.get(f["key"]) if daily_card else None

                        if f["type"] == "number":
                            val = st.number_input(
                                f["label"],
                                value=float(current_val) if current_val is not None else None,
                                step=f.get("step", 1.0),
                                format=f"%.{len(str(f.get('step',1)).split('.')[-1])}f" if '.' in str(f.get('step',1)) else "%g",
                                key=field_key,
                                placeholder="未填",
                            )
                            show_critical(f["key"], val)
                        else:
                            val = st.text_input(
                                f["label"],
                                value=str(current_val) if current_val else "",
                                key=field_key,
                                placeholder="未填",
                            )
    # 自动计算显示
    st.divider()
    st.subheader("🔢 自动计算")

    # 从 session_state 读取当前输入值
    bp_sys = st.session_state.get("circulation_bp_sys")
    bp_dia = st.session_state.get("circulation_bp_dia")
    pao2 = st.session_state.get("circulation_abg_pao2")
    fio2 = st.session_state.get("respiration_vent_fio2")
    intake = st.session_state.get("circulation_intake_vol")
    output = st.session_state.get("circulation_output_vol")

    map_val = calc_map(bp_sys, bp_dia)
    oi_val = calc_oi(pao2, fio2)
    balance_val = calc_balance(intake, output)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("MAP", f"{map_val} mmHg" if map_val else "—",
                  delta="计算中" if bp_sys and bp_dia and not map_val else None)
    with col2:
        st.metric("氧合指数", f"{oi_val}" if oi_val else "—",
                  delta="需FiO₂" if pao2 and not fio2 else None)
    with col3:
        bal_display = f"{balance_val:+.0f} mL" if balance_val is not None else "—"
        st.metric("出入量平衡", bal_display)

with right_col:
    st.subheader("🤖 AI 汇报")

    # 模型选择
    report_model = st.radio(
        "模型",
        ["deepseek-chat", "deepseek-reasoner"],
        horizontal=True,
        index=0,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 生成今日汇报", type="primary", use_container_width=True):
            from prompts.prompt_builder import build_system_prompt, build_report_prompt
            from core.deepseek_client import chat_stream

            # 先保存当前输入
            save_data = {}
            for dim in DIMENSIONS:
                for f in dim["today_fields"]:
                    key = f"{dim['key']}_{f['key']}"
                    if key in st.session_state:
                        save_data[f["key"]] = st.session_state[key]
                for f in dim["yesterday_fields"]:
                    key = f"{dim['key']}_{f['key']}"
                    if key in st.session_state:
                        save_data[f["key"]] = st.session_state[key]
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

        # 操作按钮
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

# --- 底部：信息缺口清单可视化 ---
st.divider()
st.caption(f"💡 提示：所有数据保存在本地 SQLite，AI 调用仅发送脱敏后的临床文本。当前患者：{patient['name_abbr']} | 日期：{data_date_str}")
