"""历史趋势页面 — Plotly 多指标折线图"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import date, timedelta
from config import TREND_METRICS
import models.patient as patient_db
import models.daily_card as card_db

st.set_page_config(page_title="历史趋势 - 临床助手", page_icon="📊", layout="wide")
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

# 默认日期范围：最近30天
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

# 准备绘图数据
dates = [c["data_date"] for c in cards]

# 计算氧合指数（需要单独计算）
# 使用 Plotly 子图
fig = make_subplots(specs=[[{"secondary_y": False}]])
fig.update_layout(
    title=f"{patient['name_abbr']} 历史趋势",
    xaxis_title="日期",
    hovermode="x unified",
    height=500,
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
)

for key in selected_keys:
    meta = metric_options[key]
    values = []
    for c in cards:
        if key == "abg_pao2":
            # 氧合指数 = PaO2/FiO2
            pao2 = c.get("abg_pao2") if c.get("abg_pao2") else None
            fio2 = c.get("vent_fio2") if c.get("vent_fio2") else None
            if pao2 and fio2:
                fio2_decimal = fio2 / 100 if fio2 > 1 else fio2
                val = round(pao2 / fio2_decimal, 1) if fio2_decimal > 0 else None
            else:
                val = None
        elif key == "renal_func_cr":
            # 尝试从 renal_func 文本中提取肌酐值
            rf = c.get("renal_func")
            val = None
            if rf:
                import re
                m = re.search(r"Cr[\s:：]*(\d+\.?\d*)", rf)
                if m:
                    val = float(m.group(1))
        else:
            val = c.get(key)
        values.append(val)

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines+markers",
            name=meta["label"],
            line=dict(color=meta.get("color", "#0077b6"), width=2),
            marker=dict(size=6),
            hovertemplate=f"{meta['label']}: %{{y}}<br>日期: %{{x}}<extra></extra>",
        )
    )

# 术后天数标注
if patient.get("surgery_date"):
    surg_date = patient["surgery_date"]
    fig.add_vline(
        x=surg_date,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"手术日 {surg_date}",
    )

st.plotly_chart(fig, use_container_width=True)

# 数据表格
st.divider()
st.subheader("📋 原始数据")
if st.checkbox("显示数据表格"):
    table_data = []
    for c in cards:
        row = {"日期": c["data_date"]}
        for key in selected_keys:
            meta = metric_options[key]
            row[meta["label"]] = c.get(key, "-")
        table_data.append(row)
    st.dataframe(table_data, use_container_width=True)
