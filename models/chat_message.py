"""患者级 AI 对话 CRUD"""

import uuid
from datetime import datetime
from core.database import get_connection


def _table_exists() -> bool:
    """检查 chat_messages 表是否存在"""
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'"
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def create(patient_id: str, conversation_id: str, role: str, content: str,
           image_data: str = "", model_used: str = "") -> dict:
    """创建一条对话消息"""
    conn = get_connection()
    msg_id = uuid.uuid4().hex[:12]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT INTO chat_messages (id, patient_id, conversation_id, role, content, image_data, model_used, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (msg_id, patient_id, conversation_id, role, content, image_data, model_used, now),
    )
    conn.commit()
    conn.close()
    return {"id": msg_id, "patient_id": patient_id, "conversation_id": conversation_id,
            "role": role, "content": content, "image_data": image_data,
            "model_used": model_used, "created_at": now}


def get_conversations(patient_id: str) -> list[dict]:
    """获取患者的所有对话列表（按最后消息时间倒序）"""
    if not _table_exists():
        return []
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT conversation_id, "
            "MIN(created_at) as created_at, "
            "MAX(created_at) as last_message_at, "
            "(SELECT content FROM chat_messages m2 "
            " WHERE m2.conversation_id = chat_messages.conversation_id "
            " AND m2.patient_id = chat_messages.patient_id "
            " AND m2.role = 'user' ORDER BY m2.created_at LIMIT 1) as title, "
            "(SELECT content FROM chat_messages m3 "
            " WHERE m3.conversation_id = chat_messages.conversation_id "
            " AND m3.patient_id = chat_messages.patient_id "
            " ORDER BY m3.created_at DESC LIMIT 1) as last_message "
            "FROM chat_messages WHERE patient_id = ? "
            "GROUP BY conversation_id ORDER BY last_message_at DESC",
            (patient_id,),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_messages(patient_id: str, conversation_id: str) -> list[dict]:
    """获取某对话的全部消息"""
    if not _table_exists():
        return []
    try:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE patient_id = ? AND conversation_id = ? ORDER BY created_at ASC",
            (patient_id, conversation_id),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def delete_conversation(patient_id: str, conversation_id: str):
    """删除整条对话"""
    if not _table_exists():
        return
    try:
        conn = get_connection()
        conn.execute(
            "DELETE FROM chat_messages WHERE patient_id = ? AND conversation_id = ?",
            (patient_id, conversation_id),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def new_conversation_id() -> str:
    """生成新对话 ID"""
    return uuid.uuid4().hex[:12]
