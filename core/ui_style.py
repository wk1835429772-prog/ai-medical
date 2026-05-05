"""全局 UI 样式注入 — 所有页面统一调用"""

import streamlit as st


def inject_global_css():
    """注入全局 CSS（每个页面调用一次）"""
    st.markdown("""
<style>
/* === 全局基础 === */
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

/* === 移动端适配 === */
@media (max-width: 768px) {
    .stColumns > div {
        min-width: 0 !important;
    }
    h1 { font-size: 1.5rem !important; }
}

/* === Plotly 图表 === */
.stPlotlyChart {
    border-radius: 12px;
    border: 1px solid #e5e7eb;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}
</style>
""", unsafe_allow_html=True)


def page_header(title: str, icon: str = ""):
    """渲染页面标题（带渐变）"""
    st.title(f"{icon} {title}" if icon else title)
