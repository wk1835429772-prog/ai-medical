"""患者主表 CRUD"""

import uuid
from datetime import datetime
from core.database import get_connection
from core.database import auto_export_json as _auto_export


def create(data: dict) -> dict:
    """创建患者"""
    conn = get_connection()
    patient_id = uuid.uuid4().hex[:12]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """INSERT INTO patients (id, name_abbr, age, gender, admission_date,
           primary_diagnosis, surgery_type, surgery_date, is_critical, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            patient_id,
            data.get("name_abbr", ""),
            data.get("age"),
            data.get("gender", ""),
            data.get("admission_date", ""),
            data.get("primary_diagnosis", ""),
            data.get("surgery_type", ""),
            data.get("surgery_date") or None,
            data.get("is_critical", 0),
            data.get("notes", ""),
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    _auto_export()
    return get_by_id(patient_id)


def get_by_id(patient_id: str) -> dict | None:
    """根据ID获取患者"""
    conn = get_connection()
    row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all(search: str = "") -> list[dict]:
    """获取所有患者，支持搜索"""
    conn = get_connection()
    if search:
        q = f"%{search}%"
        rows = conn.execute(
            "SELECT * FROM patients WHERE name_abbr LIKE ? OR primary_diagnosis LIKE ? ORDER BY updated_at DESC",
            (q, q),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM patients ORDER BY updated_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update(patient_id: str, data: dict) -> dict | None:
    """更新患者信息"""
    conn = get_connection()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fields = []
    values = []
    for key in ["name_abbr", "age", "gender", "admission_date", "primary_diagnosis",
                "surgery_type", "surgery_date", "is_critical", "notes"]:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if not fields:
        conn.close()
        return get_by_id(patient_id)
    fields.append("updated_at = ?")
    values.append(now)
    values.append(patient_id)
    conn.execute(f"UPDATE patients SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    _auto_export()
    return get_by_id(patient_id)


def delete(patient_id: str):
    """删除患者（级联删除日卡）"""
    conn = get_connection()
    conn.execute("DELETE FROM daily_cards WHERE patient_id = ?", (patient_id,))
    conn.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    conn.commit()
    conn.close()
    _auto_export()
