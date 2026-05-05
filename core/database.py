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
    conn.close()
    backup_database()


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
