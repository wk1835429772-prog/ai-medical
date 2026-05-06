"""历史趋势页面 -- 原始数据表（颜色标注）"""

import streamlit as st
import re
import pandas as pd
from datetime import date, timedelta

from config import REFERENCE_RANGES
from core.database import init_database, get_connection
init_database()

import models.patient as patient_db
import models.daily_card as card_db

# 加载自定义参考范围（优先使用用户在设置页保存的值）
def _load_custom_ranges() -> dict:
    import json
    custom = {}
    try:
        conn = get_connection()
        rows = conn.execute("SELECT key, value FROM settings WHERE key LIKE 'ref_%'").fetchall()
        conn.close()
        for r in rows:
            metric_key = r["key"][4:]
            try:
                custom[metric_key] = dict(json.loads(r["value"]))
            except Exception:
                pass
    except Exception:
        pass
    return custom

_CUSTOM_RANGES = _load_custom_ranges()

def _get_ref(key: str):
    if key in _CUSTOM_RANGES:
        return _CUSTOM_RANGES[key]
    return REFERENCE_RANGES.get(key)

st.set_page_config(page_title="历史数据 - 临床助手", page_icon="📊", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()
st.title("📊 历史数据")

# ─── 患者选择 ───
patients = patient_db.get_all()
if not patients:
    st.warning("暂无患者数据")
    st.stop()

patient_id = st.session_state.get("current_patient_id")
patient_names = {p["id"]: p["name_abbr"] for p in patients}
selected_id = st.selectbox(
    "选择患者",
    options=list(patient_names.keys()),
    format_func=lambda x: patient_names[x],
    index=list(patient_names.keys()).index(patient_id) if patient_id in patient_names else 0,
)
patient = patient_db.get_by_id(selected_id)

# ─── 日期范围 ───
end_date = date.today()
start_date = end_date - timedelta(days=14)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("开始日期", value=start_date)
with col2:
    end_date = st.date_input("结束日期", value=end_date)

# ─── 获取数据 ───
cards = card_db.get_by_date_range(selected_id, start_date.isoformat(), end_date.isoformat())
if not cards:
    st.info("该时间段内暂无日卡数据")
    st.stop()

dates = [c["data_date"] for c in cards]

# 按维度分组
METRIC_GROUPS = [
    {
        "label": "生命体征",
        "metrics": [
            ("bp_sys", "收缩压"), ("bp_dia", "舒张压"), ("hr", "心率"),
            ("spo2", "SpO₂"), ("rr", "RR"), ("temp", "体温"),
            ("intake_vol", "总入量"), ("output_vol", "总出量"), ("stool_vol", "大便量"),
            ("urine_vol", "尿量"),
        ],
    },
    {
        "label": "血气分析",
        "metrics": [
            ("abg_ph", "pH"), ("abg_pao2", "PaO₂"), ("abg_paco2", "PaCO₂"),
            ("abg_hco3", "HCO₃⁻"), ("abg_lac", "乳酸"),
            ("vent_fio2", "FiO₂"), ("vent_peep", "PEEP"),
        ],
    },
    {
        "label": "感染指标",
        "metrics": [
            ("wbc", "WBC"), ("neut_pct", "中性粒%"), ("pct", "PCT"), ("il6", "IL-6"),
        ],
    },
    {
        "label": "脏器功能",
        "metrics": [
            ("ionized_ca", "离子钙"), ("bnp", "BNP"),
        ],
    },
    {
        "label": "营养",
        "metrics": [
            ("albumin", "白蛋白"), ("prealbumin", "前白蛋白"),
        ],
    },
    {
        "label": "VTE",
        "metrics": [
            ("d_dimer", "D-二聚体"),
        ],
    },
]


def _extract_value(card: dict, key: str):
    """从日卡提取指标值，支持特殊字段（OI、肌酐正则提取）"""
    if key == "abg_pao2":
        pao2 = card.get("abg_pao2")
        fio2 = card.get("vent_fio2")
        if pao2 and fio2:
            fio2_dec = fio2 / 100 if fio2 > 1 else fio2
            return round(pao2 / fio2_dec, 1) if fio2_dec > 0 else None
        return None
    if key == "renal_func_cr":
        rf = card.get("renal_func")
        if rf:
            m = re.search(r"Cr[\s:：]*(\d+\.?\d*)", rf)
            if m:
                return float(m.group(1))
        return None
    val = card.get(key)
    if val == "正常":
        return None
    return val


def _format_val(val):
    """格式化数值为两位小数"""
    if val is None or val == "" or val == "正常":
        return ""
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return str(val)


def _color_cell(val, key):
    """根据 REFERENCE_RANGES 返回 CSS 颜色"""
    if val is None or val == "正常" or val == "":
        return ""
    ref = _get_ref(key)
    if not ref:
        return ""
    try:
        v = float(val)
    except (ValueError, TypeError):
        return ""
    if v > ref["hi"]:
        return "color: #dc2626; font-weight: 700"  # 红色 - 偏高
    if v < ref["lo"]:
        return "color: #2563eb; font-weight: 700"  # 蓝色 - 偏低
    return ""


def _ref_hint(key):
    """返回正常范围文字提示"""
    ref = _get_ref(key)
    if not ref:
        return ""
    return f"{ref['lo']}-{ref['hi']} {ref['unit']}"


# ══════════════════════════════════════════════
# 原始数据表（颜色标注）
# ══════════════════════════════════════════════

for group in METRIC_GROUPS:
    group_metrics = group["metrics"]
    rows = []
    for card in cards:
        row = {"日期": card["data_date"]}
        for key, label in group_metrics:
            raw = _extract_value(card, key)
            row[label] = _format_val(raw)
        rows.append(row)

    if not rows:
        continue

    df = pd.DataFrame(rows)
    if df.drop(columns=["日期"]).replace("", pd.NA).dropna(how="all").empty:
        continue

    st.markdown(f"**{group['label']}**")

    # 显示正常范围参考
    ref_texts = []
    for key, label in group_metrics:
        hint = _ref_hint(key)
        if hint:
            ref_texts.append(f"{label}: {hint}")
    if ref_texts:
        st.caption("参考范围 — " + " | ".join(ref_texts))

    # 样式：颜色标注
    def _apply_styles(row, _group_metrics=group_metrics):
        styles = [""] * len(row)
        for key, label in _group_metrics:
            col_idx = df.columns.get_loc(label)
            # 从格式化后的字符串还原原始值用于比较
            raw = row[label]
            styles[col_idx] = _color_cell(raw, key)
        return styles

    styled = df.style.apply(_apply_styles, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)

# ─── 底部 ───
st.divider()
st.caption(f"💡 正常值范围可在「设置」页面调整。颜色说明：红色=偏高，蓝色=偏低。当前患者：{patient['name_abbr']}")
