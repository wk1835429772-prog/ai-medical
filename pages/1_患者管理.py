"""患者管理页面"""

import streamlit as st
from datetime import date
import models.patient as patient_db
from core.calculator import calc_postop_days

st.set_page_config(page_title="患者管理 - 临床助手", page_icon="🏥", layout="wide")
st.title("👥 患者管理")

# --- 搜索栏 ---
search = st.text_input("🔍 搜索（姓名缩写 / 诊断）", placeholder="输入关键词筛选...")

# --- 添加患者按钮 ---
if "show_add_form" not in st.session_state:
    st.session_state.show_add_form = False

col1, col2 = st.columns([1, 4])
with col1:
    if st.button("➕ 添加新患者", type="primary" if not st.session_state.show_add_form else "secondary"):
        st.session_state.show_add_form = not st.session_state.show_add_form

# --- 添加/编辑表单 ---
if st.session_state.show_add_form:
    with st.expander("📝 添加新患者", expanded=True):
        with st.form("add_patient_form"):
            col1, col2, col3 = st.columns(3)
            with col1:
                name_abbr = st.text_input("姓名缩写 *", placeholder="如：张三 → ZS")
                age = st.number_input("年龄", min_value=0, max_value=120, step=1)
                gender = st.selectbox("性别", ["", "男", "女", "其他"])
            with col2:
                admission_date = st.date_input("入院日期", value=date.today())
                primary_diagnosis = st.text_input("主要诊断", placeholder="入院诊断")
                surgery_type = st.text_input("手术方式", placeholder="如：CABG")
            with col3:
                surgery_date = st.date_input("手术日期", value=None)
                is_critical = st.selectbox("危重级别", [
                    (0, "稳定 (绿)"),
                    (1, "关注 (黄)"),
                    (2, "危重 (红)"),
                ], format_func=lambda x: x[1])
                notes = st.text_area("备注", placeholder="其他注意事项...")

            submitted = st.form_submit_button("✅ 保存患者", type="primary")
            if submitted:
                if not name_abbr.strip():
                    st.error("姓名缩写不能为空")
                else:
                    data = {
                        "name_abbr": name_abbr.strip().upper(),
                        "age": age if age > 0 else None,
                        "gender": gender,
                        "admission_date": admission_date.isoformat() if admission_date else "",
                        "primary_diagnosis": primary_diagnosis.strip(),
                        "surgery_type": surgery_type.strip(),
                        "surgery_date": surgery_date.isoformat() if surgery_date else None,
                        "is_critical": is_critical[0],
                        "notes": notes.strip(),
                    }
                    patient_db.create(data)
                    st.session_state.show_add_form = False
                    st.success(f"✅ 患者 {name_abbr.strip().upper()} 已添加")
                    st.rerun()

# --- 编辑模式 ---
if "editing_patient_id" not in st.session_state:
    st.session_state.editing_patient_id = None

if st.session_state.editing_patient_id:
    patient = patient_db.get_by_id(st.session_state.editing_patient_id)
    if patient:
        with st.expander(f"✏️ 编辑患者：{patient['name_abbr']}", expanded=True):
            with st.form("edit_patient_form"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    name_abbr = st.text_input("姓名缩写 *", value=patient.get("name_abbr", ""))
                    age = st.number_input("年龄", min_value=0, max_value=120, step=1,
                                          value=patient.get("age") or 0)
                    gender = st.selectbox("性别", ["", "男", "女", "其他"],
                                          index=["", "男", "女", "其他"].index(patient.get("gender", "")))
                with col2:
                    admission_date = st.date_input("入院日期",
                                                   value=date.fromisoformat(patient["admission_date"])
                                                   if patient.get("admission_date") else date.today())
                    primary_diagnosis = st.text_input("主要诊断", value=patient.get("primary_diagnosis", ""))
                    surgery_type = st.text_input("手术方式", value=patient.get("surgery_type", ""))
                with col3:
                    surgery_date = st.date_input("手术日期",
                                                 value=date.fromisoformat(patient["surgery_date"])
                                                 if patient.get("surgery_date") else None)
                    is_critical = st.selectbox("危重级别", [
                        (0, "稳定 (绿)"),
                        (1, "关注 (黄)"),
                        (2, "危重 (红)"),
                    ], format_func=lambda x: x[1],
                    index=patient.get("is_critical", 0))
                    notes = st.text_area("备注", value=patient.get("notes", ""))

                col1, col2 = st.columns(2)
                with col1:
                    submitted = st.form_submit_button("💾 保存修改", type="primary")
                with col2:
                    cancel = st.form_submit_button("❌ 取消")

                if submitted:
                    data = {
                        "name_abbr": name_abbr.strip().upper(),
                        "age": age if age > 0 else None,
                        "gender": gender,
                        "admission_date": admission_date.isoformat() if admission_date else "",
                        "primary_diagnosis": primary_diagnosis.strip(),
                        "surgery_type": surgery_type.strip(),
                        "surgery_date": surgery_date.isoformat() if surgery_date else None,
                        "is_critical": is_critical[0],
                        "notes": notes.strip(),
                    }
                    patient_db.update(st.session_state.editing_patient_id, data)
                    st.session_state.editing_patient_id = None
                    st.success("✅ 患者信息已更新")
                    st.rerun()
                if cancel:
                    st.session_state.editing_patient_id = None
                    st.rerun()

# --- 患者列表 ---
st.divider()
st.subheader(f"📋 患者列表（共 {len(patient_db.get_all(search))} 人）")

patients = patient_db.get_all(search)
if not patients:
    if search:
        st.info("未找到匹配的患者")
    else:
        st.info("暂无患者，点击上方按钮添加")

for p in patients:
    crit = p.get("is_critical", 0)
    border_color = "#e63946" if crit == 2 else "#f4a261" if crit == 1 else "#2a9d8f"
    dot_emoji = "🔴" if crit == 2 else "🟡" if crit == 1 else "🟢"
    postop = calc_postop_days(p.get("surgery_date"))

    with st.container():
        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:12px 16px;margin-bottom:8px;
                    border-left:4px solid {border_color};box-shadow:0 1px 4px rgba(0,0,0,0.06);">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
                <span style="font-weight:700;font-size:1.05rem;">{dot_emoji} {p['name_abbr']}</span>
                <span style="font-size:0.8rem;color:#666;">{p.get('gender','')} · {p.get('age','')}岁</span>
                {f'<span style="font-size:0.8rem;background:#e8f5f3;color:#2a9d8f;padding:2px 8px;border-radius:4px;">术后D{postop}</span>' if postop is not None else ''}
                <span style="font-size:0.8rem;color:#999;margin-left:auto;">入院：{p.get('admission_date','')}</span>
            </div>
            <div style="font-size:0.85rem;color:#555;margin-bottom:2px;">
                🏷️ {p.get('primary_diagnosis','未填诊断')}
                {f' | 🔪 {p.get(\"surgery_type\",\"\")}' if p.get('surgery_type') else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns([1, 1, 1, 1])
        with col1:
            if st.button("✏️ 编辑", key=f"edit_{p['id']}"):
                st.session_state.editing_patient_id = p['id']
                st.rerun()
        with col2:
            if st.button("📝 今日评估", key=f"assess_{p['id']}"):
                st.session_state.current_patient_id = p['id']
                st.switch_page("pages/2_今日评估.py")
        with col3:
            if st.button("📊 趋势", key=f"trend_{p['id']}"):
                st.session_state.current_patient_id = p['id']
                st.switch_page("pages/3_历史趋势.py")
        with col4:
            if st.button("🗑️ 删除", key=f"del_{p['id']}", type="secondary"):
                if st.session_state.get(f"confirm_del_{p['id']}"):
                    patient_db.delete(p['id'])
                    st.success(f"已删除患者 {p['name_abbr']}")
                    st.rerun()
                else:
                    st.session_state[f"confirm_del_{p['id']}"] = True
                    st.warning(f"确认删除 {p['name_abbr']}？再次点击删除按钮确认。")
