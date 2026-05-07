"""临床查房 MCP 服务器 — RikkaHub 通过此服务器读取患者数据"""

import sys
import os

# 将项目根目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.fastmcp import FastMCP
from datetime import date

from core.database import init_database
init_database()

import models.patient as patient_db
import models.daily_card as card_db
from core.calculator import calc_map, calc_oi, calc_balance, calc_postop_days, check_critical
from config import REFERENCE_RANGES, CRITICAL_THRESHOLDS

mcp = FastMCP("临床查房助手")

# ─── 床号映射（按患者创建时间排序编号） ───
def _build_bed_map() -> dict[int, str]:
    """返回 {床号: patient_id} 映射"""
    patients = patient_db.get_all()
    mapping = {}
    for i, p in enumerate(patients, 1):
        mapping[i] = p["id"]
    return mapping


def _patient_with_bed(patient: dict, bed: int) -> dict:
    """给患者信息附加床号"""
    return {
        "bed": bed,
        "id": patient["id"],
        "name": patient["name_abbr"],
        "age": patient.get("age"),
        "gender": patient.get("gender", ""),
        "diagnosis": patient.get("primary_diagnosis", ""),
        "surgery_type": patient.get("surgery_type", ""),
        "surgery_date": patient.get("surgery_date"),
        "postop_day": calc_postop_days(patient.get("surgery_date")),
    }


# ─── 工具 1: 患者列表 ───
@mcp.tool()
def get_patient_list() -> str:
    """列出所有管床患者（床号、姓名、诊断、术后天数）"""
    bed_map = _build_bed_map()
    if not bed_map:
        return "暂无患者数据"

    lines = ["**管床患者列表**\n"]
    for bed in sorted(bed_map.keys()):
        pid = bed_map[bed]
        patient = patient_db.get_by_id(pid)
        if not patient:
            continue
        info = _patient_with_bed(patient, bed)
        pod = f"术后D{info['postop_day']}" if info["postop_day"] is not None else ""
        lines.append(
            f"- **{bed}床**: {info['name']} | {info['age']}岁 | {info['diagnosis'][:20]} | {pod}"
        )
    return "\n".join(lines)


# ─── 工具 2: 查某床 ───
@mcp.tool()
def get_rounds_by_bed(bed: int) -> str:
    """
    返回指定床号患者的完整查房汇报。

    Args:
        bed: 床号（整数，如 1, 2, 3）
    """
    bed_map = _build_bed_map()
    if bed not in bed_map:
        return f"未找到 {bed} 床患者"

    pid = bed_map[bed]
    patient = patient_db.get_by_id(pid)
    if not patient:
        return f"{bed} 床患者数据异常"

    today = date.today().isoformat()
    card = card_db.get_or_create(pid, today)
    info = _patient_with_bed(patient, bed)

    return _format_rounds(info, card)


# ─── 工具 3: 全查 ───
@mcp.tool()
def get_rounds_all() -> str:
    """返回所有患者的查房汇报"""
    bed_map = _build_bed_map()
    if not bed_map:
        return "暂无患者"

    today = date.today().isoformat()
    sections = []
    for bed in sorted(bed_map.keys()):
        pid = bed_map[bed]
        patient = patient_db.get_by_id(pid)
        card = card_db.get_or_create(pid, today)
        if not patient:
            continue
        info = _patient_with_bed(patient, bed)
        sections.append(_format_rounds(info, card))
        sections.append("\n---\n")

    return "\n".join(sections)


# ─── 工具 4: 异常值 ───
@mcp.tool()
def get_abnormal_flags() -> str:
    """列出所有患者当前偏离正常范围的指标"""
    today = date.today().isoformat()
    bed_map = _build_bed_map()
    all_flags = []

    for bed in sorted(bed_map.keys()):
        pid = bed_map[bed]
        patient = patient_db.get_by_id(pid)
        card = card_db.get_or_create(pid, today)
        if not patient or not card:
            continue
        name = patient["name_abbr"]

        for key, ref in REFERENCE_RANGES.items():
            val = card.get(key)
            if val is None or val == "" or val == "正常":
                continue
            try:
                v = float(val)
            except (ValueError, TypeError):
                continue
            flag = None
            if v > ref["hi"]:
                flag = f"↑ 偏高"
            elif v < ref["lo"]:
                flag = f"↓ 偏低"
            if flag:
                all_flags.append(f"- **{bed}床 {name}**: {ref['label']} = {v} {flag} (正常: {ref['lo']}-{ref['hi']} {ref['unit']})")

        # 危急值检查
        for key, crit in CRITICAL_THRESHOLDS.items():
            val = card.get(key)
            if val is None:
                continue
            try:
                v = float(val)
            except (ValueError, TypeError):
                continue
            triggered = False
            if "hi" in crit and v > crit["hi"]:
                triggered = True
            if "lo" in crit and v < crit["lo"]:
                triggered = True
            if triggered:
                all_flags.append(f"- 🚨 **{bed}床 {name}**: {crit['label']} | 当前值: {v}")

    if not all_flags:
        return "✅ 所有指标正常"

    return "**异常/危急值汇总**\n\n" + "\n".join(all_flags)


# ─── 查房汇报格式化 ───
def _format_rounds(info: dict, card: dict) -> str:
    pod = f"术后D{info['postop_day']}" if info["postop_day"] is not None else ""
    lines = [
        f"## {info['bed']}床 | {info['name']} | {info['age']}岁 | {pod}",
        f"诊断: {info['diagnosis']}",
        "",
    ]

    # 生命体征
    bp_sys = card.get("bp_sys")
    bp_dia = card.get("bp_dia")
    hr = card.get("hr")
    spo2 = card.get("spo2")
    temp = card.get("temp")
    rr = card.get("rr")
    intake = card.get("intake_vol")
    output = card.get("output_vol")

    map_val = calc_map(bp_sys, bp_dia)
    bal = calc_balance(intake, output)

    vitals = []
    if bp_sys and bp_dia:
        vitals.append(f"BP {bp_sys}/{bp_dia} mmHg")
    if hr is not None:
        vitals.append(f"HR {hr} bpm")
    if spo2 is not None:
        vitals.append(f"SpO₂ {spo2}%")
    if temp is not None:
        vitals.append(f"体温 {temp}°C")
    if rr is not None:
        vitals.append(f"RR {rr} bpm")

    lines.append("### 📊 生命体征")
    lines.append(" | ".join(vitals) if vitals else "未填写")

    calcs = []
    if map_val:
        calcs.append(f"MAP {map_val} mmHg")
    if bal is not None:
        calcs.append(f"平衡 {bal:+g} mL")
    if calcs:
        lines.append(" | ".join(calcs))

    # 七维
    lines.append("")
    lines.append("### 📋 七维数据")

    dim_data = [
        ("原发病", ["drain_vol", "drain_char", "wound_eval"]),
        ("循环", []),
        ("呼吸/酸碱", ["abg_ph", "abg_pao2", "abg_paco2", "abg_hco3", "abg_lac",
                        "vent_mode", "vent_fio2", "vent_peep", "sputum_char"]),
        ("感染", ["temp", "wbc", "neut_pct", "pct", "il6"]),
        ("脏器", ["urine_vol", "ionized_ca", "bnp"]),
        ("营养", ["nutrition_route", "enteral_vol", "parenteral_vol", "albumin", "prealbumin"]),
        ("VTE", ["vte_prophylaxis", "d_dimer"]),
    ]

    for dim_name, dim_keys in dim_data:
        items = []
        for key in dim_keys:
            val = card.get(key)
            if val is not None and val != "" and val != "正常":
                ref = REFERENCE_RANGES.get(key)
                if ref:
                    label = ref["label"]
                    try:
                        v = float(val)
                        flag = ""
                        if v > ref["hi"]:
                            flag = " 🔴↑"
                        elif v < ref["lo"]:
                            flag = " 🔵↓"
                        items.append(f"{label}: {v}{flag}")
                    except ValueError:
                        items.append(f"{key}: {val}")
                else:
                    items.append(f"{key}: {val}")
        if items:
            lines.append(f"**{dim_name}**: " + " | ".join(items))

    # OI 计算
    oi = calc_oi(card.get("abg_pao2"), card.get("vent_fio2"))
    if oi is not None:
        lines.append(f"↳ OI = {oi}")

    # 治疗方案
    treatment = card.get("treatment_plan", "")
    if treatment:
        lines.append("")
        lines.append(f"### 💊 治疗方案\n{treatment}")

    return "\n".join(lines)


# ─── 启动 ───
if __name__ == "__main__":
    mcp.run(transport="stdio")
