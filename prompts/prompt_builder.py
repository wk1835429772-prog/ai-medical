"""动态组装提示词：基础系统提示词 + 黄金规则 + 患者上下文"""

import json
from datetime import date
from prompts.system_prompts import FULL_SYSTEM_PROMPT
from core.database import get_connection
from core.calculator import calc_postop_days


def load_active_rules() -> list[dict]:
    """从数据库加载所有活跃的黄金规则"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, title, content, category FROM rules WHERE is_active = 1 ORDER BY category, title"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_system_prompt(include_rules: bool = True) -> str:
    """构建完整系统提示词（基础 + 动态规则）"""
    prompt = FULL_SYSTEM_PROMPT
    if include_rules:
        rules = load_active_rules()
        if rules:
            rules_text = "\n\n## 用户自定义黄金规则\n"
            for i, rule in enumerate(rules, 1):
                rules_text += f"\n### 规则{i}：{rule['title']}\n{rule['content']}\n"
            prompt += rules_text
    return prompt


def build_patient_context(patient: dict, daily_card: dict = None) -> str:
    """构建患者上下文（供AI对话使用）"""
    postop_days = calc_postop_days(patient.get("surgery_date"))
    ctx = f"""## 当前患者信息
- 姓名缩写：{patient.get('name_abbr', '未知')}
- 年龄：{patient.get('age', '未知')}
- 性别：{patient.get('gender', '未知')}
- 入院日期：{patient.get('admission_date', '未知')}
- 主要诊断：{patient.get('primary_diagnosis', '未填')}
- 危重级别：{'⚠️ 危重' if patient.get('is_critical') == 2 else '⚡ 关注' if patient.get('is_critical') == 1 else '✅ 稳定'}
"""
    if patient.get("surgery_type"):
        ctx += f"- 手术方式：{patient.get('surgery_type')}\n"
    if postop_days is not None:
        ctx += f"- 术后日数：D{postop_days}\n"

    if daily_card:
        ctx += f"\n### 今日晨7:00数据（{daily_card.get('data_date', '')}）\n"
        # 循环
        vitals = []
        if daily_card.get("bp_sys"):
            vitals.append(f"血压 {daily_card['bp_sys']}/{daily_card.get('bp_dia','')} mmHg")
        if daily_card.get("hr"):
            vitals.append(f"心率 {daily_card['hr']} bpm")
        if daily_card.get("spo2"):
            vitals.append(f"SpO₂ {daily_card['spo2']}%")
        if daily_card.get("temp"):
            vitals.append(f"体温 {daily_card['temp']}°C")
        if vitals:
            ctx += "生命体征：" + "，".join(vitals) + "\n"

        if daily_card.get("intake_vol") is not None:
            ctx += f"入量：{daily_card['intake_vol']} mL，"
        if daily_card.get("output_vol") is not None:
            ctx += f"出量：{daily_card['output_vol']} mL\n"

        # ABG
        abg_parts = []
        for k, label in [("abg_ph", "pH"), ("abg_pao2", "PaO₂"), ("abg_paco2", "PaCO₂"),
                          ("abg_hco3", "HCO₃⁻"), ("abg_lac", "乳酸")]:
            if daily_card.get(k) is not None:
                abg_parts.append(f"{label} {daily_card[k]}")
        if abg_parts:
            ctx += "血气：" + "，".join(abg_parts) + "\n"

        # 呼吸
        if daily_card.get("vent_mode"):
            ctx += f"呼吸机：{daily_card['vent_mode']}，FiO₂ {daily_card.get('vent_fio2','')}%，PEEP {daily_card.get('vent_peep','')}\n"

        ctx += f"\n### 昨日结果（{daily_card.get('data_date', '')}）\n"
        labs = []
        for k, label in [("wbc", "WBC"), ("neut_pct", "中性粒%"), ("pct", "PCT"), ("il6", "IL-6"),
                          ("bnp", "BNP"), ("ionized_ca", "离子钙"), ("albumin", "白蛋白"),
                          ("d_dimer", "D-二聚体")]:
            if daily_card.get(k) is not None:
                labs.append(f"{label} {daily_card[k]}")
        if labs:
            ctx += "化验：" + "，".join(labs) + "\n"

        for k, label in [("echo_result", "心超"), ("chest_xray", "胸片"), ("pathogen_result", "病原学"),
                          ("liver_func", "肝功能"), ("renal_func", "肾功能"), ("coagulation", "凝血")]:
            if daily_card.get(k):
                ctx += f"{label}：{daily_card[k]}\n"

    return ctx


def build_report_prompt(patient: dict, daily_card: dict) -> str:
    """构建查房汇报的用户提示词"""
    ctx = build_patient_context(patient, daily_card)
    return f"""查房：

{ctx}

请按八项模板（诊断→原发病→循环→呼吸→感染→脏器→营养→VTE）进行今日汇报。
同时在末尾列出：1) 信息缺口清单 2) 跨维度矛盾分析 3) 优先级行动清单。"""
