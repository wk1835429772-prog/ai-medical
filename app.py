"""临床助手 - 入口程序"""

import streamlit as st
from core.database import init_database

# 页面配置（必须是第一个 Streamlit 命令）
st.set_page_config(
    page_title="临床助手",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 初始化数据库
init_database()

# --- 侧边栏 ---
with st.sidebar:
    st.title("🏥 临床助手")

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
                st.markdown("🔴 **危重患者**")
            elif crit == 1:
                st.markdown("🟡 **需关注**")
            else:
                st.markdown("🟢 稳定")
    else:
        st.session_state.pop("current_patient_id", None)

    st.divider()

    # 导航 - 使用 Streamlit 自动页面发现
    st.markdown("### 📋 功能导航")
    st.caption("使用左侧页面菜单切换功能")

    st.divider()
    st.caption(f"v1.0 | 临床助手")

# --- 首页仪表盘 ---
st.title("🏥 临床助手")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("在管患者", len(patients))
with col2:
    critical_count = sum(1 for p in patients if p.get("is_critical") == 2)
    st.metric("危重患者", critical_count, delta=f"{critical_count}人" if critical_count else None)
with col3:
    from datetime import date
    today_str = date.today().strftime("%Y年%m月%d日")
    st.metric("今日日期", today_str)
with col4:
    from core.deepseek_client import get_api_key
    api_status = "✅ 已配置" if get_api_key() else "⚠️ 未配置"
    st.metric("AI 状态", api_status)

st.divider()

# 快捷入口
st.subheader("快捷操作")
col1, col2, col3, col4 = st.columns(4)
with col1:
    if st.button("➕ 添加患者", use_container_width=True):
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

# 如果没有患者，提示添加
if not patients:
    st.info("👋 欢迎使用临床助手！请先添加患者开始工作。", icon=":material/info:")
