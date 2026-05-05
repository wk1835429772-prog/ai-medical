"""PDF / 文本导出功能"""

import os
from datetime import date


def export_report_text(patient: dict, daily_card: dict, ai_report: str = "") -> str:
    """导出为纯文本格式"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"临床助手 - 查房汇报")
    lines.append("=" * 60)
    lines.append(f"患者：{patient.get('name_abbr', '未知')}")
    lines.append(f"年龄：{patient.get('age', '')} | 性别：{patient.get('gender', '')}")
    lines.append(f"主要诊断：{patient.get('primary_diagnosis', '')}")
    lines.append(f"数据日期：{daily_card.get('data_date', '')}")
    lines.append("=" * 60)
    lines.append("")

    if ai_report:
        lines.append(ai_report)
    else:
        # 手动构建基本汇报
        sections = [
            ("循环", ["bp_sys", "bp_dia", "hr", "spo2", "intake_vol", "output_vol",
                      "abg_ph", "abg_pao2", "abg_paco2", "abg_hco3", "abg_lac"]),
            ("呼吸", ["vent_mode", "vent_fio2", "vent_peep", "sputum_char"]),
            ("感染", ["temp", "wbc", "neut_pct", "pct", "il6", "pathogen_result"]),
            ("脏器", ["urine_vol", "liver_func", "renal_func", "coagulation", "electrolytes", "ionized_ca"]),
            ("原发病", ["drain_vol", "drain_char", "wound_eval"]),
            ("营养", ["nutrition_route", "enteral_vol", "parenteral_vol", "albumin", "prealbumin"]),
            ("VTE", ["vte_prophylaxis", "d_dimer", "leg_us"]),
        ]
        for section, fields in sections:
            values = {k: daily_card.get(k) for k in fields if daily_card.get(k) is not None
                      and daily_card.get(k) != ""}
            if values:
                lines.append(f"## {section}")
                for k, v in values.items():
                    lines.append(f"  {k}: {v}")
                lines.append("")

    lines.append("=" * 60)
    lines.append(f"生成时间：{date.today().isoformat()}")
    lines.append("本报告由「临床助手」生成，仅供临床参考。")
    return "\n".join(lines)


def export_patient_summary(patient: dict, cards: list[dict]) -> str:
    """导出患者病程摘要"""
    lines = []
    lines.append("# 患者病程摘要")
    lines.append(f"姓名缩写：{patient.get('name_abbr', '')}")
    lines.append(f"年龄：{patient.get('age', '')} | 性别：{patient.get('gender', '')}")
    lines.append(f"入院日期：{patient.get('admission_date', '')}")
    lines.append(f"主要诊断：{patient.get('primary_diagnosis', '')}")
    if patient.get("surgery_type"):
        lines.append(f"手术：{patient.get('surgery_type')} ({patient.get('surgery_date', '')})")
    lines.append("")

    for card in cards:
        lines.append(f"## {card.get('data_date', '')}")
        # 简要关键数据
        vitals = []
        for k, label in [("bp_sys", "BP"), ("hr", "HR"), ("temp", "T"), ("spo2", "SpO2")]:
            if card.get(k):
                vitals.append(f"{label}: {card[k]}")
        if vitals:
            lines.append(" | ".join(vitals))
        labs = []
        for k, label in [("wbc", "WBC"), ("pct", "PCT"), ("abg_lac", "乳酸"), ("abg_ph", "pH"),
                          ("ionized_ca", "iCa"), ("d_dimer", "D-dimer")]:
            if card.get(k):
                labs.append(f"{label}: {card[k]}")
        if labs:
            lines.append(" | ".join(labs))
        lines.append("")

    return "\n".join(lines)
