"""全局 UI 样式注入 — 所有页面统一调用"""

import streamlit as st


def inject_global_css():
    """注入全局 CSS（每个页面调用一次）"""
    st.markdown("""
<style>
/* === 全局基础 === */
.block-container {
    padding-top: 2.5rem !important;
}
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #f0f7ff 0%, #f8f9fa 100%);
    border-right: 1px solid #e0e6ed;
}
section[data-testid="stSidebar"] .stMarkdown h1,
section[data-testid="stSidebar"] .stMarkdown h3 {
    color: #1a365d;
}

/* === 标题风格 === */
h1 {
    background: linear-gradient(135deg, #1a5276 0%, #2e86c1 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 800 !important;
    padding-bottom: 0.3rem;
    border-bottom: 3px solid #2e86c1;
    margin-bottom: 1rem;
}
h2, h3 {
    color: #1a365d !important;
    font-weight: 700 !important;
}

/* === 分组标签 === */
.group-label {
    font-size: 0.85rem;
    font-weight: 600;
    color: #4a5568;
    padding: 4px 0 2px 0;
    border-bottom: 1px dashed #e2e8f0;
    margin-bottom: 8px;
    margin-top: 4px;
}

/* === 按钮 === */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.15s ease;
    border: 1px solid #d1d5db;
}
.stButton > button:hover {
    border-color: #2e86c1;
    box-shadow: 0 2px 8px rgba(46,134,193,0.15);
    transform: translateY(-1px);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2e86c1 0%, #1a5276 100%) !important;
    border: none !important;
    color: white !important;
    box-shadow: 0 2px 8px rgba(46,134,193,0.25);
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 12px rgba(46,134,193,0.35);
}

/* === 输入框 === */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 8px !important;
    border: 1.5px solid #d1d5db !important;
    transition: border-color 0.15s ease;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #2e86c1 !important;
    box-shadow: 0 0 0 2px rgba(46,134,193,0.15) !important;
}

/* === 分隔线 === */
hr {
    border: none;
    height: 1px;
    background: linear-gradient(90deg, transparent, #cbd5e1, transparent);
    margin: 1.5rem 0;
}

/* === Tab 样式 === */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #f8fafc;
    border-radius: 10px;
    padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

/* === Expander === */
details {
    border-radius: 10px !important;
    border: 1px solid #e5e7eb !important;
    margin-bottom: 8px;
}
details summary {
    font-weight: 600;
}

/* === Metric 卡片 === */
[data-testid="stMetric"] {
    background: white;
    border-radius: 12px;
    padding: 16px;
    border: 1px solid #e5e7eb;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
[data-testid="stMetric"] label {
    color: #6b7280 !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
[data-testid="stMetric"] [data-testid="stMetricValue"] {
    color: #1a365d !important;
    font-weight: 700 !important;
}

/* === Alert 样式 === */
.stAlert {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* === Selectbox / Radio === */
.stSelectbox > div > div,
.stRadio > div {
    border-radius: 8px;
}

/* === 表格 === */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e5e7eb;
}

/* === Container border === */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border: 1px solid #e5e7eb !important;
    padding: 4px;
}

/* === Plotly 图表 === */
.stPlotlyChart {
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}

/* =============================================
   移动端适配（≤768px）
   ============================================= */
@media (max-width: 768px) {
    /* 全局：收紧边距 */
    .block-container {
        padding-left: 0.75rem !important;
        padding-right: 0.75rem !important;
        padding-top: 0.5rem !important;
    }

    /* 标题缩放 */
    h1 { font-size: 1.3rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 1rem !important; }

    /* 所有列布局自动堆叠为全宽 */
    [data-testid="stHorizontalBlock"] > div {
        flex: 1 1 100% !important;
        max-width: 100% !important;
        min-width: 0 !important;
    }

    /* 输入框：防 iOS 自动缩放 + 触控目标 ≥44px */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div,
    .stDateInput > div > div > input {
        min-height: 44px !important;
        font-size: 16px !important;
    }

    /* 按钮：触控目标 */
    .stButton > button {
        min-height: 44px !important;
        font-size: 0.95rem !important;
        padding: 8px 16px !important;
        width: 100% !important;
    }

    /* Metric 卡片：紧凑 */
    [data-testid="stMetric"] {
        padding: 10px 12px !important;
        margin-bottom: 4px !important;
    }
    [data-testid="stMetric"] label {
        font-size: 0.75rem !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.1rem !important;
    }

    /* Expander：紧凑 */
    details {
        margin-bottom: 4px !important;
    }

    /* Radio：自动换行 */
    .stRadio > div {
        flex-wrap: wrap !important;
    }

    /* 侧边栏收窄 */
    section[data-testid="stSidebar"] {
        width: 260px !important;
    }

    /* 分组标签 */
    .group-label {
        font-size: 0.8rem !important;
    }

    /* 表格横向滚动 */
    [data-testid="stDataFrame"] {
        overflow-x: auto !important;
    }

    /* 图表高度自适应 */
    .stPlotlyChart {
        min-height: 300px;
    }
}

/* === 平板适配（769-1024px）=== */
@media (min-width: 769px) and (max-width: 1024px) {
    .stButton > button {
        min-height: 40px !important;
    }
    [data-testid="stMetric"] {
        padding: 12px !important;
    }
}
</style>
""", unsafe_allow_html=True)


def page_header(title: str, icon: str = ""):
    """渲染页面标题（带渐变）"""
    st.title(f"{icon} {title}" if icon else title)
