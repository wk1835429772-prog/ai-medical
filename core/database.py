"""数据库连接管理 — 支持 SQLite（本地）和 PostgreSQL/Supabase（云端）双后端"""

import sqlite3
import os
import shutil
import threading
from datetime import datetime
from urllib.parse import urlparse

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "app.db")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "backups")

# ─── 连接复用（同一请求内不重复建连） ───
_local = threading.local()

def _get_cached_sqlite():
    """同一请求内复用 SQLite 连接"""
    conn = getattr(_local, "sqlite_conn", None)
    if conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.sqlite_conn = conn
    return conn


class _PgRef:
    """包装 PgConnection，close 后自动重建"""
    def __init__(self):
        self._conn = None

    def get(self):
        if self._conn is None:
            import pg8000.dbapi
            url_str = _get_supabase_url()
            parsed = urlparse(url_str)
            raw = pg8000.dbapi.connect(
                user=parsed.username or "postgres",
                password=parsed.password or "",
                host=parsed.hostname or "localhost",
                port=parsed.port or 5432,
                database=parsed.path.lstrip("/") if parsed.path else "postgres",
                timeout=30,
            )
            self._conn = PgConnection(raw)
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
        self._conn = None


def _get_cached_pg():
    """同一请求内复用 pg8000 连接"""
    ref = getattr(_local, "pg_ref", None)
    if ref is None:
        ref = _PgRef()
        _local.pg_ref = ref
    return ref.get()

def close_connections():
    """关闭请求内的所有连接（Streamlit session 结束时调用）"""
    ref = getattr(_local, "pg_ref", None)
    if ref:
        ref.close()
        _local.pg_ref = None
    conn = getattr(_local, "sqlite_conn", None)
    if conn:
        try:
            conn.close()
        except Exception:
            pass
        _local.sqlite_conn = None

# ─── 后端检测 ───
def _get_supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL", "")
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("SUPABASE_URL", "")
        except Exception:
            pass
    return url

USE_SUPABASE = bool(_get_supabase_url())


# ─── PostgreSQL 兼容包装（pg8000 驱动） ───
class PgConnection:
    """包装 pg8000 连接，使行为与 sqlite3.Row 兼容（row["column"] 可用）"""

    def __init__(self, conn):
        self._conn = conn
        self._cursor = conn.cursor()
        self._description = None

    def execute(self, sql, params=None):
        # ? 占位符 → %s（PostgreSQL 格式）
        pg_sql = sql.replace("?", "%s")
        self._cursor.execute(pg_sql, params or ())
        self._description = self._cursor.description
        return self

    def executescript(self, script):
        """逐条执行 SQL 脚本"""
        for stmt in script.split(";"):
            stmt = stmt.strip()
            if stmt:
                self._cursor.execute(stmt)
        return self

    class _Row(dict):
        """支持 row[0] 和 row['col'] 两种访问方式"""
        def __init__(self, data, desc):
            super().__init__(data)
            self._desc = desc
        def __getitem__(self, key):
            if isinstance(key, int):
                return list(self.values())[key]
            return super().__getitem__(key)
        def __iter__(self):
            return iter(self.values())

    def _row_to_dict(self, row):
        if row is None or self._description is None:
            return None
        data = {self._description[i][0]: row[i] for i in range(len(row))}
        return self._Row(data, self._description)

    def fetchone(self):
        row = self._cursor.fetchone()
        return self._row_to_dict(row)

    def fetchall(self):
        rows = self._cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]

    def commit(self):
        self._conn.commit()

    def close(self):
        try:
            self._cursor.close()
        except Exception:
            pass
        try:
            self._conn.close()
        except Exception:
            pass

    def cursor(self):
        return self._cursor


# ─── 连接获取 ───
def get_connection():
    """获取数据库连接（同一请求内复用，自动选择后端）"""
    if USE_SUPABASE:
        return _get_cached_pg()
    return _get_cached_sqlite()


def _get_sqlite_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _get_pg_connection():
    try:
        import pg8000.dbapi
    except ImportError:
        raise ImportError("PostgreSQL 后端需要 pg8000：pip install pg8000")
    url_str = _get_supabase_url()
    parsed = urlparse(url_str)
    user = parsed.username or "postgres"
    password = parsed.password or ""
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    database = parsed.path.lstrip("/") if parsed.path else "postgres"
    # 尝试连接，默认 SSL
    conn = pg8000.dbapi.connect(
        user=user, password=password, host=host, port=port,
        database=database, timeout=30,
    )
    return PgConnection(conn)


# ─── 初始化 ───
_init_cache = {}

def init_database():
    """初始化数据库（连接复用缓存）"""
    if _init_cache.get("done"):
        return
    if USE_SUPABASE:
        _init_pg()
    else:
        _init_sqlite()
    _init_cache["done"] = True


def _init_sqlite():
    """SQLite 初始化"""
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
            bp_sys REAL, bp_dia REAL, hr REAL, spo2 REAL,
            intake_vol REAL, output_vol REAL, stool_vol REAL,
            abg_ph REAL, abg_pao2 REAL, abg_paco2 REAL, abg_hco3 REAL, abg_lac REAL,
            echo_result TEXT DEFAULT '', ecg_result TEXT DEFAULT '',
            cardiac_markers TEXT DEFAULT '', bnp REAL,
            vent_mode TEXT DEFAULT '', vent_fio2 REAL, vent_peep REAL,
            sputum_char TEXT DEFAULT '',
            chest_xray TEXT DEFAULT '', lung_us TEXT DEFAULT '',
            temp REAL,
            wbc REAL, neut_pct REAL, pct REAL, il6 REAL,
            pathogen_result TEXT DEFAULT '',
            urine_vol REAL,
            liver_func TEXT DEFAULT '', renal_func TEXT DEFAULT '',
            coagulation TEXT DEFAULT '', electrolytes TEXT DEFAULT '',
            ionized_ca REAL,
            drain_vol REAL, drain_char TEXT DEFAULT '', wound_eval TEXT DEFAULT '',
            nutrition_route TEXT DEFAULT '', enteral_vol REAL, parenteral_vol REAL,
            albumin REAL, prealbumin REAL,
            vte_prophylaxis TEXT DEFAULT '',
            d_dimer REAL, leg_us TEXT DEFAULT '',
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

    # 迁移：添加 rr 列
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

    # chat_messages 表（独立连接）
    conn.commit()
    conn.close()
    try:
        conn2 = get_connection()
        conn2.execute("""
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
        conn2.execute("CREATE INDEX IF NOT EXISTS idx_chat_patient ON chat_messages(patient_id)")
        conn2.execute("CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_messages(conversation_id)")
        conn2.commit()
        conn2.close()
    except Exception:
        pass

    _seed_default_rules()


def _init_pg():
    """PostgreSQL/Supabase 初始化"""
    conn = get_connection()

    tables_sql = """
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
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS daily_cards (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            data_date TEXT NOT NULL,
            bp_sys REAL, bp_dia REAL, hr REAL, spo2 REAL, rr REAL,
            intake_vol REAL, output_vol REAL, stool_vol REAL,
            abg_ph REAL, abg_pao2 REAL, abg_paco2 REAL, abg_hco3 REAL, abg_lac REAL,
            echo_result TEXT DEFAULT '', ecg_result TEXT DEFAULT '',
            cardiac_markers TEXT DEFAULT '', bnp REAL,
            vent_mode TEXT DEFAULT '', vent_fio2 REAL, vent_peep REAL,
            sputum_char TEXT DEFAULT '',
            chest_xray TEXT DEFAULT '', lung_us TEXT DEFAULT '',
            temp REAL,
            wbc REAL, neut_pct REAL, pct REAL, il6 REAL,
            pathogen_result TEXT DEFAULT '',
            urine_vol REAL,
            liver_func TEXT DEFAULT '', renal_func TEXT DEFAULT '',
            coagulation TEXT DEFAULT '', electrolytes TEXT DEFAULT '',
            ionized_ca REAL,
            drain_vol REAL, drain_char TEXT DEFAULT '', wound_eval TEXT DEFAULT '',
            nutrition_route TEXT DEFAULT '', enteral_vol REAL, parenteral_vol REAL,
            albumin REAL, prealbumin REAL,
            vte_prophylaxis TEXT DEFAULT '',
            d_dimer REAL, leg_us TEXT DEFAULT '',
            current_diagnosis TEXT DEFAULT '',
            treatment_plan TEXT DEFAULT '',
            circulation_notes TEXT DEFAULT '',
            respiration_notes TEXT DEFAULT '',
            infection_notes TEXT DEFAULT '',
            organs_notes TEXT DEFAULT '',
            primary_disease_notes TEXT DEFAULT '',
            nutrition_notes TEXT DEFAULT '',
            vte_notes TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(patient_id, data_date)
        );
        CREATE TABLE IF NOT EXISTS rules (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS chat_messages (
            id TEXT PRIMARY KEY,
            patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            image_data TEXT DEFAULT '',
            model_used TEXT DEFAULT '',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """
    for stmt in tables_sql.split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_daily_cards_patient ON daily_cards(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_daily_cards_date ON daily_cards(data_date)",
        "CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(name_abbr)",
        "CREATE INDEX IF NOT EXISTS idx_rules_active ON rules(is_active)",
        "CREATE INDEX IF NOT EXISTS idx_chat_patient ON chat_messages(patient_id)",
        "CREATE INDEX IF NOT EXISTS idx_chat_conversation ON chat_messages(conversation_id)",
    ]
    for idx_sql in indexes:
        try:
            conn.execute(idx_sql)
            conn.commit()
        except Exception:
            pass

    conn.close()
    _seed_default_rules()


# ─── 辅助函数 ───
def upsert_setting(key: str, value: str):
    conn = get_connection()
    if USE_SUPABASE:
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, NOW()) "
            "ON CONFLICT(key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()",
            (key, value),
        )
    else:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
            (key, value),
        )
    conn.commit()
    conn.close()


def table_exists(table_name: str) -> bool:
    conn = get_connection()
    try:
        if USE_SUPABASE:
            row = conn.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = ?",
                (table_name,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        conn.close()


# ─── JSON 自动导出/导入 ───
def export_all_json() -> str:
    import json
    conn = get_connection()
    tables = ["patients", "daily_cards", "rules", "settings", "chat_messages"]
    data = {}
    for table in tables:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            data[table] = [dict(r) for r in rows]
        except Exception:
            data[table] = []
    conn.close()
    return json.dumps(data, ensure_ascii=False, default=str)


def auto_export_json() -> str:
    try:
        json_str = export_all_json()
        backup_path = os.path.join(os.path.dirname(DB_PATH), "app.json")
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(json_str)
        return json_str
    except Exception:
        return ""


def import_all_json(json_str: str):
    import json
    data = json.loads(json_str)
    order = ["patients", "daily_cards", "rules", "settings", "chat_messages"]
    for table in order:
        rows = data.get(table, [])
        for row in rows:
            columns = list(row.keys())
            values = [row[c] for c in columns]
            placeholders = ", ".join(["?" for _ in columns])
            cols_str = ", ".join(columns)
            try:
                conn = get_connection()
                if USE_SUPABASE:
                    conn.execute(
                        f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT(id) DO NOTHING",
                        values,
                    )
                else:
                    conn.execute(
                        f"INSERT OR IGNORE INTO {table} ({cols_str}) VALUES ({placeholders})",
                        values,
                    )
                conn.commit()
                conn.close()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass


# ─── 默认规则种子 ───
def _seed_default_rules():
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) FROM rules").fetchone()
    cnt = row[0] if row else 0
    if cnt > 0:
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


# ─── SQLite 专用备份 ───
def backup_database():
    if USE_SUPABASE:
        return
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
    backups = sorted([
        f for f in os.listdir(BACKUP_DIR) if f.startswith("app_") and f.endswith(".db")
    ])
    while len(backups) > 30:
        oldest = backups.pop(0)
        try:
            os.remove(os.path.join(BACKUP_DIR, oldest))
        except Exception:
            pass
