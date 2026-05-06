"""历史趋势页面 — 每个指标独立图表（不同单位/量程）"""

import streamlit as st
import re
import plotly.graph_objects as go
from datetime import date, timedelta
from config import TREND_METRICS
from core.database import init_database
init_database()

import models.patient as patient_db
import models.daily_card as card_db

st.set_page_config(page_title="历史趋势 - 临床助手", page_icon="📊", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()
st.title("📊 历史趋势")

# 患者选择
patient_id = st.session_state.get("current_patient_id")
patients = patient_db.get_all()
if not patients:
    st.warning("暂无患者数据")
    st.stop()

patient_names = {p["id"]: p["name_abbr"] for p in patients}
selected_id = st.selectbox(
    "选择患者",
    options=list(patient_names.keys()),
    format_func=lambda x: f"{patient_names[x]}",
    index=list(patient_names.keys()).index(patient_id) if patient_id in patient_names else 0,
)
patient = patient_db.get_by_id(selected_id)

# 日期范围
end_date = date.today()
start_date = end_date - timedelta(days=30)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("开始日期", value=start_date)
with col2:
    end_date = st.date_input("结束日期", value=end_date)

# 指标多选
metric_options = {m["key"]: m for m in TREND_METRICS}
selected_keys = st.multiselect(
    "选择指标",
    options=list(metric_options.keys()),
    format_func=lambda x: f"{metric_options[x]['label']}",
    default=["abg_lac", "pct", "ionized_ca"],
)

if not selected_keys:
    st.info("请选择至少一个指标")
    st.stop()

# 获取数据
cards = card_db.get_by_date_range(selected_id, start_date.isoformat(), end_date.isoformat())
if not cards:
    st.info("该时间段内暂无日卡数据")
    st.stop()

dates = [c["data_date"] for c in cards]

# 术后日期标注
surg_date = patient.get("surgery_date")

# 每个指标独立图表
for key in selected_keys:
    meta = metric_options[key]
    values = []
    for c in cards:
        if key == "abg_pao2":
            pao2 = c.get("abg_pao2")
            fio2 = c.get("vent_fio2")
            if pao2 and fio2:
                fio2_decimal = fio2 / 100 if fio2 > 1 else fio2
                val = round(pao2 / fio2_decimal, 1) if fio2_decimal > 0 else None
            else:
                val = None
        elif key == "renal_func_cr":
            rf = c.get("renal_func")
            val = None
            if rf:
                m = re.search(r"Cr[\s:：]*(\d+\.?\d*)", rf)
                if m:
                    val = float(m.group(1))
        else:
            val = c.get(key)
        values.append(val)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines+markers",
            name=meta["label"],
            line=dict(color=meta.get("color", "#0077b6"), width=2.5),
            marker=dict(size=7),
            hovertemplate=f"{meta['label']}: %{{y}}<br>日期: %{{x}}<extra></extra>",
            fill="tozeroy",
            fillcolor=f"rgba({int(meta.get('color', '#0077b6')[1:3], 16)}, "
                      f"{int(meta.get('color', '#0077b6')[3:5], 16)}, "
                      f"{int(meta.get('color', '#0077b6')[5:7], 16)}, 0.08)",
        )
    )

    if surg_date:
        fig.add_vline(
            x=surg_date,
            line_dash="dash",
            line_color="gray",
            annotation_text="手术日",
        )

    fig.update_layout(
        title=dict(text=meta["label"], font=dict(size=16)),
        xaxis_title="日期",
        yaxis_title=meta["label"],
        hovermode="x unified",
        height=350,
        margin=dict(l=60, r=30, t=50, b=40),
        showlegend=False,
    )

    st.plotly_chart(fig, use_container_width=True)

# 数据表格
st.divider()
with st.expander("📋 原始数据表格", expanded=False):
    table_data = []
    for c in cards:
        row = {"日期": c["data_date"]}
        for key in selected_keys:
            meta = metric_options[key]
            row[meta["label"]] = c.get(key, "—")
        table_data.append(row)
    st.dataframe(table_data, use_container_width=True)
