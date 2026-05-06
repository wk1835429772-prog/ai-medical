"""临床助手 - 全局配置常量"""

# 应用信息
APP_NAME = "临床助手"
APP_VERSION = "1.1.0"

# DeepSeek API 配置
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL_FAST = "deepseek-v4-flash"
DEEPSEEK_MODEL_PRO = "deepseek-v4-pro"
DEEPSEEK_MAX_TOKENS = 4096

# 数据库
DB_PATH = "data/app.db"


def _build_groups(dim):
    """为 today_fields 构建默认分组（如果未显式定义 today_groups）"""
    if "today_groups" not in dim and dim["today_fields"]:
        dim["today_groups"] = [{"label": "", "fields": dim["today_fields"]}]


# 七维框架定义（顺序：原发病 → 循环 → 呼吸 → 感染 → 脏器 → 营养 → VTE）
DIMENSIONS = [
    {
        "key": "primary_disease",
        "name": "原发病",
        "icon": "🩹",
        "notes_key": "primary_disease_notes",
        "today_fields": [
            {"key": "drain_vol", "label": "引流量 (mL)", "type": "number", "step": 10},
            {"key": "drain_char", "label": "引流性状", "type": "text"},
            {"key": "wound_eval", "label": "伤口/皮瓣评估", "type": "text"},
        ],
        "yesterday_fields": [],
    },
    {
        "key": "circulation",
        "name": "循环",
        "icon": "❤️",
        "notes_key": "circulation_notes",
        "today_fields": [
            {"key": "bp_sys", "label": "收缩压 (mmHg)", "type": "number", "step": 1},
            {"key": "bp_dia", "label": "舒张压 (mmHg)", "type": "number", "step": 1},
            {"key": "hr", "label": "心率 (bpm)", "type": "number", "step": 1},
            {"key": "spo2", "label": "SpO₂ (%)", "type": "number", "step": 1},
            {"key": "intake_vol", "label": "总入量 (mL)", "type": "number", "step": 50},
            {"key": "output_vol", "label": "总出量 (mL)", "type": "number", "step": 50},
            {"key": "stool_vol", "label": "大便量 (mL)", "type": "number", "step": 50},
        ],
        "today_groups": [
            {
                "label": "生命体征",
                "fields": [
                    {"key": "bp_sys", "label": "收缩压 (mmHg)", "type": "number", "step": 1},
                    {"key": "bp_dia", "label": "舒张压 (mmHg)", "type": "number", "step": 1},
                    {"key": "hr", "label": "心率 (bpm)", "type": "number", "step": 1},
                    {"key": "spo2", "label": "SpO₂ (%)", "type": "number", "step": 1},
                ],
            },
            {
                "label": "出入量",
                "fields": [
                    {"key": "intake_vol", "label": "总入量 (mL)", "type": "number", "step": 50},
                    {"key": "output_vol", "label": "总出量 (mL)", "type": "number", "step": 50},
                    {"key": "stool_vol", "label": "大便量 (mL)", "type": "number", "step": 50},
                ],
            },
        ],
        "yesterday_fields": [
            {"key": "echo_result", "label": "心超结果", "type": "text"},
            {"key": "ecg_result", "label": "心电图", "type": "text"},
            {"key": "cardiac_markers", "label": "心肌标志物", "type": "text"},
            {"key": "bnp", "label": "BNP (pg/mL)", "type": "number", "step": 1},
        ],
    },
    {
        "key": "respiration",
        "name": "呼吸 / 酸碱",
        "icon": "🫁",
        "notes_key": "respiration_notes",
        "today_fields": [
            {"key": "abg_ph", "label": "pH", "type": "number", "step": 0.01},
            {"key": "abg_pao2", "label": "PaO₂ (mmHg)", "type": "number", "step": 0.1},
            {"key": "abg_paco2", "label": "PaCO₂ (mmHg)", "type": "number", "step": 0.1},
            {"key": "abg_hco3", "label": "HCO₃⁻ (mmol/L)", "type": "number", "step": 0.1},
            {"key": "abg_lac", "label": "乳酸 (mmol/L)", "type": "number", "step": 0.1},
            {"key": "vent_mode", "label": "呼吸机模式", "type": "text"},
            {"key": "vent_fio2", "label": "FiO₂ (%)", "type": "number", "step": 5},
            {"key": "vent_peep", "label": "PEEP (cmH₂O)", "type": "number", "step": 1},
            {"key": "sputum_char", "label": "痰液性状", "type": "text"},
            {"key": "rr", "label": "RR (bpm)", "type": "number", "step": 1},
        ],
        "today_groups": [
            {
                "label": "血气分析",
                "fields": [
                    {"key": "abg_ph", "label": "pH", "type": "number", "step": 0.01},
                    {"key": "abg_pao2", "label": "PaO₂ (mmHg)", "type": "number", "step": 0.1},
                    {"key": "abg_paco2", "label": "PaCO₂ (mmHg)", "type": "number", "step": 0.1},
                    {"key": "abg_hco3", "label": "HCO₃⁻ (mmol/L)", "type": "number", "step": 0.1},
                    {"key": "abg_lac", "label": "乳酸 (mmol/L)", "type": "number", "step": 0.1},
                ],
            },
            {
                "label": "呼吸支持",
                "fields": [
                    {"key": "vent_mode", "label": "呼吸机模式", "type": "text"},
                    {"key": "vent_fio2", "label": "FiO₂ (%)", "type": "number", "step": 5},
                    {"key": "vent_peep", "label": "PEEP (cmH₂O)", "type": "number", "step": 1},
                    {"key": "sputum_char", "label": "痰液性状", "type": "text"},
                ],
            },
            {
                "label": "呼吸频率",
                "fields": [
                    {"key": "rr", "label": "RR (bpm)", "type": "number", "step": 1},
                ],
            },
        ],
        "yesterday_fields": [
            {"key": "chest_xray", "label": "胸片结果", "type": "text"},
            {"key": "lung_us", "label": "肺超结果", "type": "text"},
        ],
    },
    {
        "key": "infection",
        "name": "感染",
        "icon": "🌡️",
        "notes_key": "infection_notes",
        "today_fields": [
            {"key": "temp", "label": "体温 (°C)", "type": "number", "step": 0.1},
        ],
        "yesterday_fields": [
            {"key": "wbc", "label": "WBC (×10⁹/L)", "type": "number", "step": 0.1},
            {"key": "neut_pct", "label": "中性粒% (%)", "type": "number", "step": 0.1},
            {"key": "pct", "label": "PCT (ng/mL)", "type": "number", "step": 0.01},
            {"key": "il6", "label": "IL-6 (pg/mL)", "type": "number", "step": 0.1},
            {"key": "pathogen_result", "label": "病原学结果", "type": "text"},
        ],
    },
    {
        "key": "organs",
        "name": "脏器",
        "icon": "🫘",
        "notes_key": "organs_notes",
        "today_fields": [
            {"key": "urine_vol", "label": "尿量 (mL)", "type": "number", "step": 50},
        ],
        "yesterday_fields": [
            {"key": "liver_func", "label": "肝功能", "type": "text"},
            {"key": "renal_func", "label": "肾功能 (Cr/BUN)", "type": "text"},
            {"key": "coagulation", "label": "凝血象", "type": "text"},
            {"key": "electrolytes", "label": "电解质", "type": "text"},
            {"key": "ionized_ca", "label": "离子钙 (mmol/L)", "type": "number", "step": 0.01},
        ],
    },
    {
        "key": "nutrition",
        "name": "营养",
        "icon": "🍽️",
        "notes_key": "nutrition_notes",
        "today_fields": [
            {"key": "nutrition_route", "label": "营养途径", "type": "text"},
            {"key": "enteral_vol", "label": "肠内入量 (mL)", "type": "number", "step": 50},
            {"key": "parenteral_vol", "label": "肠外入量 (mL)", "type": "number", "step": 50},
        ],
        "yesterday_fields": [
            {"key": "albumin", "label": "白蛋白 (g/L)", "type": "number", "step": 0.1},
            {"key": "prealbumin", "label": "前白蛋白 (mg/L)", "type": "number", "step": 1},
        ],
    },
    {
        "key": "vte",
        "name": "VTE",
        "icon": "🩸",
        "notes_key": "vte_notes",
        "today_fields": [
            {"key": "vte_prophylaxis", "label": "物理预防措施", "type": "text"},
        ],
        "yesterday_fields": [
            {"key": "d_dimer", "label": "D-二聚体 (ng/mL)", "type": "number", "step": 100},
            {"key": "leg_us", "label": "下肢彩超", "type": "text"},
        ],
    },
]

# 为未显式定义 today_groups 的维度自动生成默认分组
for _dim in DIMENSIONS:
    _build_groups(_dim)

# 危急值阈值
CRITICAL_THRESHOLDS = {
    "abg_lac": {"hi": 2, "label": "乳酸 >2 mmol/L"},
    "ionized_ca": {"lo": 1.15, "label": "离子钙 <1.15 mmol/L"},
    "abg_ph": {"lo": 7.25, "hi": 7.55, "label": "pH <7.25 或 >7.55"},
    "d_dimer": {"hi": 3000, "label": "D-二聚体 >3000 ng/mL"},
}

# 历史趋势可用指标
TREND_METRICS = [
    {"key": "abg_lac", "label": "乳酸 (mmol/L)", "color": "#e63946"},
    {"key": "pct", "label": "PCT (ng/mL)", "color": "#f4a261"},
    {"key": "renal_func_cr", "label": "肌酐 (μmol/L)", "color": "#2a9d8f"},
    {"key": "bnp", "label": "BNP (pg/mL)", "color": "#264653"},
    {"key": "abg_pao2", "label": "氧合指数", "color": "#0077b6"},
    {"key": "ionized_ca", "label": "离子钙 (mmol/L)", "color": "#8338ec"},
    {"key": "d_dimer", "label": "D-二聚体 (ng/mL)", "color": "#ff006e"},
]

# 教学深度模式
TEACHING_MODES = {
    "command": {"label": "指令模式", "description": "直接回答问题，简洁精炼"},
    "discussion": {"label": "讨论模式", "description": "展开分析，列出依据和考量"},
    "teaching": {"label": "教学模式", "description": "系统性讲解，包括基础知识和临床思维"},
}
