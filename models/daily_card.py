"""日卡 CRUD"""

import uuid
from datetime import datetime
from core.database import get_connection


def get_or_create(patient_id: str, data_date: str) -> dict:
    """获取指定日期的日卡，不存在则返回空字典"""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM daily_cards WHERE patient_id = ? AND data_date = ?",
        (patient_id, data_date),
    ).fetchone()
    conn.close()
    return dict(row) if row else {"patient_id": patient_id, "data_date": data_date}


def save(patient_id: str, data_date: str, data: dict) -> dict:
    """保存日卡（UPSERT）"""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM daily_cards WHERE patient_id = ? AND data_date = ?",
        (patient_id, data_date),
    ).fetchone()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 所有日卡字段
    fields = [
        "bp_sys", "bp_dia", "hr", "spo2", "intake_vol", "output_vol", "stool_vol",
        "abg_ph", "abg_pao2", "abg_paco2", "abg_hco3", "abg_lac",
        "echo_result", "ecg_result", "cardiac_markers", "bnp",
        "vent_mode", "vent_fio2", "vent_peep", "sputum_char", "rr",
        "chest_xray", "lung_us",
        "temp",
        "wbc", "neut_pct", "pct", "il6", "pathogen_result",
        "urine_vol",
        "liver_func", "renal_func", "coagulation", "electrolytes", "ionized_ca",
        "drain_vol", "drain_char", "wound_eval",
        "nutrition_route", "enteral_vol", "parenteral_vol",
        "albumin", "prealbumin",
        "vte_prophylaxis",
        "d_dimer", "leg_us",
        # v1.1.0 新增
        "current_diagnosis", "treatment_plan",
        "circulation_notes", "respiration_notes", "infection_notes",
        "organs_notes", "primary_disease_notes", "nutrition_notes", "vte_notes",
    ]

    if existing:
        card_id = existing["id"]
        set_clauses = [f"{f} = ?" for f in fields if f in data]
        set_clauses.append("updated_at = ?")
        values = [data.get(f) for f in fields if f in data]
        values.append(now)
        values.append(card_id)
        conn.execute(
            f"UPDATE daily_cards SET {', '.join(set_clauses)} WHERE id = ?", values
        )
    else:
        card_id = uuid.uuid4().hex[:12]
        insert_fields = ["id", "patient_id", "data_date"] + [f for f in fields if f in data]
        placeholders = ["?"] * len(insert_fields)
        values = [card_id, patient_id, data_date] + [data.get(f) for f in fields if f in data]
        conn.execute(
            f"INSERT INTO daily_cards ({', '.join(insert_fields)}) VALUES ({', '.join(placeholders)})",
            values,
        )

    conn.commit()
    conn.close()
    return get_or_create(patient_id, data_date)


def get_history(patient_id: str, limit: int = 30) -> list[dict]:
    """获取患者最近N天的日卡历史"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM daily_cards WHERE patient_id = ? ORDER BY data_date DESC LIMIT ?",
        (patient_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_by_date_range(patient_id: str, start_date: str, end_date: str) -> list[dict]:
    """获取日期范围内的日卡"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM daily_cards WHERE patient_id = ? AND data_date >= ? AND data_date <= ? ORDER BY data_date ASC",
        (patient_id, start_date, end_date),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
