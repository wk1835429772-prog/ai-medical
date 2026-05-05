"""临床助手 - 入口程序"""

import streamlit as st
from core.database import init_database
from datetime import date

# 页面配置（必须是第一个 Streamlit 命令）
st.set_page_config(
    page_title="临床助手",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化数据库
init_database()

# 全局样式
from core.ui_style import inject_global_css
inject_global_css()

from config import APP_VERSION

# --- 侧边栏 ---
with st.sidebar:
    st.markdown("## 🏥 临床助手")
    st.caption(f"v{APP_VERSION}")

    # 患者选择下拉框
    from models.patient import get_all
    patients = get_all()
    patient_options = {p["name_abbr"]: p["id"] for p in patients}
    selected_name = st.selectbox(
        "当前患者",
        options=["（未选择）"] + list(patient_options.keys()),
        key="sidebar_patient",
    )
    if selected_name != "（未选择）":
        st.session_state["current_patient_id"] = patient_options[selected_name]
        patient = next((p for p in patients if p["id"] == patient_options[selected_name]), None)
        if patient:
            crit = patient.get("is_critical", 0)
            if crit == 2:
                st.error("🔴 危重患者", icon="🚨")
            elif crit == 1:
                st.warning("🟡 需关注", icon="⚠️")
            else:
                st.success("🟢 稳定", icon="✅")
    else:
        st.session_state.pop("current_patient_id", None)

    st.divider()
    st.caption(f"使用上方 ↗ 页面菜单切换功能")
    st.caption(f"v{APP_VERSION} · 临床助手 · ICU 日查房工具")

# --- 首页仪表盘 ---
st.title("🏥 临床助手")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("在管患者", f"{len(patients)} 人")
with col2:
    critical_count = sum(1 for p in patients if p.get("is_critical") == 2)
    st.metric("危重患者", f"{critical_count} 人",
              delta=f"{'需紧急关注' if critical_count else '全部稳定'}",
              delta_color="inverse" if critical_count else "normal")
with col3:
    today_str = date.today().strftime("%Y年%m月%d日")
    st.metric("今日日期", today_str)
with col4:
    from core.deepseek_client import get_api_key
    api_ok = get_api_key()
    st.metric("AI 状态", "已就绪" if api_ok else "未配置",
              delta="DeepSeek API" if api_ok else "请先配置 API Key",
              delta_color="normal" if api_ok else "off")

st.divider()

# 快捷入口
st.subheader("快捷操作")
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("👥 患者管理", use_container_width=True):
        st.switch_page("pages/1_patient_management.py")
with col2:
    if st.button("📝 今日评估", use_container_width=True):
        st.switch_page("pages/2_daily_assessment.py")
with col3:
    if st.button("🧮 医学工具箱", use_container_width=True):
        st.switch_page("pages/6_toolbox.py")
with col4:
    if st.button("🤖 AI 对话", use_container_width=True):
        st.switch_page("pages/4_ai_chat.py")

st.divider()

# 如果没有患者，提示添加
if not patients:
    st.info("👋 欢迎使用临床助手！请点击「患者管理」添加您的第一位患者。", icon="ℹ️")
else:
    # 显示简要患者列表
    st.subheader("患者概览")
    for p in patients:
        crit = p.get("is_critical", 0)
        dot = "🔴" if crit == 2 else "🟡" if crit == 1 else "🟢"
        diag = p.get("primary_diagnosis") or "未填诊断"
        st.markdown(f"{dot} **{p['name_abbr']}** — {diag}")
