"""SQLite 数据库初始化和连接管理"""

import sqlite3
import os
import shutil
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "app.db")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "backups")


def get_connection():
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_database():
    """首次运行时自动建表"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            name_abbr TEXT NOT NULL,
            age INTEGER,
            gender TEXT DEFAULT '',
            admission_date TEXT,
            primary_diagnosis TEXT DEFAULT '',
            surgery_type TEXT DEFAULT '',
            surgery_date TEXT,
            is_critical INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS daily_cards (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            data_date TEXT NOT NULL,
            -- 循环 - 今日
            bp_sys REAL,
            bp_dia REAL,
            hr REAL,
            spo2 REAL,
            intake_vol REAL,
            output_vol REAL,
            stool_vol REAL,
            abg_ph REAL,
            abg_pao2 REAL,
            abg_paco2 REAL,
            abg_hco3 REAL,
            abg_lac REAL,
            -- 循环 - 昨日
            echo_result TEXT DEFAULT '',
            ecg_result TEXT DEFAULT '',
            cardiac_markers TEXT DEFAULT '',
            bnp REAL,
            -- 呼吸 - 今日
            vent_mode TEXT DEFAULT '',
            vent_fio2 REAL,
            vent_peep REAL,
            sputum_char TEXT DEFAULT '',
            -- 呼吸 - 昨日
            chest_xray TEXT DEFAULT '',
            lung_us TEXT DEFAULT '',
            -- 感染 - 今日
            temp REAL,
            -- 感染 - 昨日
            wbc REAL,
            neut_pct REAL,
            pct REAL,
            il6 REAL,
            pathogen_result TEXT DEFAULT '',
            -- 脏器 - 今日
            urine_vol REAL,
            -- 脏器 - 昨日
            liver_func TEXT DEFAULT '',
            renal_func TEXT DEFAULT '',
            coagulation TEXT DEFAULT '',
            electrolytes TEXT DEFAULT '',
            ionized_ca REAL,
            -- 原发病 - 今日
            drain_vol REAL,
            drain_char TEXT DEFAULT '',
            wound_eval TEXT DEFAULT '',
            -- 营养 - 今日
            nutrition_route TEXT DEFAULT '',
            enteral_vol REAL,
            parenteral_vol REAL,
            -- 营养 - 昨日
            albumin REAL,
            prealbumin REAL,
            -- VTE - 今日
            vte_prophylaxis TEXT DEFAULT '',
            -- VTE - 昨日
            d_dimer REAL,
            leg_us TEXT DEFAULT '',
            -- 元数据
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            UNIQUE(patient_id, data_date)
        );

        CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_daily_cards_patient ON daily_cards(patient_id);
        CREATE INDEX IF NOT EXISTS idx_daily_cards_date ON daily_cards(data_date);
        CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(name_abbr);
        CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active);
    """)

    conn.commit()

    # 迁移：添加 rr 列（如果不存在）
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(daily_cards)").fetchall()}
    if "rr" not in existing_cols:
        cursor.execute("ALTER TABLE daily_cards ADD COLUMN rr REAL")
        conn.commit()

    # 迁移：v1.1.0 新增列
    new_cols = {
        "current_diagnosis": "TEXT DEFAULT ''",
        "treatment_plan": "TEXT DEFAULT ''",
        "circulation_notes": "TEXT DEFAULT ''",
        "respiration_notes": "TEXT DEFAULT ''",
        "infection_notes": "TEXT DEFAULT ''",
        "organs_notes": "TEXT DEFAULT ''",
        "primary_disease_notes": "TEXT DEFAULT ''",
        "nutrition_notes": "TEXT DEFAULT ''",
        "vte_notes": "TEXT DEFAULT ''",
    }
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(daily_cards)").fetchall()}
    for col, col_type in new_cols.items():
        if col not in existing_cols:
            cursor.execute(f"ALTER TABLE daily_cards ADD COLUMN {col} {col_type}")
    conn.commit()

    # 迁移：chat_messages 表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            image_data TEXT DEFAULT '',
            model_used TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_patient ON chat_messages(patient_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_messages(conversation_id)")
    conn.commit()

    conn.close()
    backup_database()
    _seed_default_rules()


def _seed_default_rules():
    """首次运行时从 assets/rules.json 加载默认黄金规则"""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    if count > 0:
        conn.close()
        return
    rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "rules.json")
    if not os.path.exists(rules_path):
        conn.close()
        return
    import json
    with open(rules_path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    for rule in rules:
        conn.execute(
            "INSERT INTO rules (id, title, content, category) VALUES (?, ?, ?, ?)",
            (rule["id"], rule["title"], rule["content"], rule["category"]),
        )
    conn.commit()
    conn.close()


def backup_database():
    """每日自动备份数据库（保留最近30份）"""
    if not os.path.exists(DB_PATH):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    backup_file = os.path.join(BACKUP_DIR, f"app_{today}.db")
    if not os.path.exists(backup_file):
        try:
            shutil.copy2(DB_PATH, backup_file)
        except Exception:
            pass
    # 清理旧备份
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR) if f.startswith("app_") and f.endswith(".db")
    ])
    while len(backups) > 30:
        oldest = backups.pop(0)
        try:
            os.remove(os.path.join(BACKUP_DIR, oldest))
        except Exception:
            pass
