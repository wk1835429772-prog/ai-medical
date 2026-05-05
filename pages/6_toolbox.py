"""工具箱页面 — 55+ 医学计算器"""

import streamlit as st
import json
import os
import sys

st.set_page_config(page_title="工具箱 - 临床助手", page_icon="🧮", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()
st.title("🧮 医学工具箱")

# 加载注册表
registry_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "calc_registry.json")
with open(registry_path, "r", encoding="utf-8") as f:
    registry = json.load(f)

calculators = registry["calculators"]
categories = list(dict.fromkeys(c["cat"] for c in calculators))

# 收藏系统
if "calc_favorites" not in st.session_state:
    st.session_state.calc_favorites = set()

# 搜索
search = st.text_input("🔍 搜索计算器（名称/关键词）", placeholder="如：血气、eGFR、补钾、评分...")

filtered = calculators
if search:
    q = search.lower()
    filtered = [c for c in calculators if q in c["name"].lower() or q in c.get("keywords", "").lower()]


def _run_calc(calc_id, values):
    """执行计算"""
    import core.calc_engine as engine

    func_map = {
        "abg": ("abg", ["ph", "pco2", "hco3", "na", "cl", "k", "lac", "alb"]),
        "nadeficit": ("nadeficit", ["na", "wt", "sex"]),
        "pumprate": ("pumprate", ["drug", "dose_mg", "vol_ml", "wt", "target"]),
        "lactate": ("lactate_clearance", ["lac1", "lac2"]),
        "map": ("map_calc", ["sbp", "dbp"]),
        "hyperk": ("hyperk", ["k"]),
        "insulin_drip": ("insulin_drip", ["glucose"]),
        "correctedca": ("corrected_ca", ["ca", "alb"]),
        "nacorr": ("na_correction", ["na", "glu"]),
        "dka": ("dka_fluids", ["wt", "degree", "glucose", "k"]),
        "egfr": ("egfr", ["cr", "age", "sex"]),
        "cg": ("cockcroft_gault", ["age", "wt", "cr", "sex"]),
        "kdeficit": ("kdeficit", ["k", "wt"]),
        "ag": ("anion_gap", ["na", "cl", "hco3"]),
        "osmgap": ("osmgap", ["na", "glu", "bun", "osm"]),
        "schwartz": ("schwartz", ["ht", "cr"]),
        "sofa": ("sofa", ["pao2", "fio2", "plt", "bili", "map", "gcs", "cr", "vaso", "uo"]),
        "gcs": ("gcs", ["eye", "verbal", "motor"]),
        "curb65": ("curb65", ["conf", "bun", "rr", "bp", "age65"]),
        "wells": ("wells_pe", ["dvt", "pe", "hr", "imm", "dvthx", "hemo", "mal"]),
        "hasbled": ("hasbled", ["htn", "renal", "stroke", "bleed", "labile", "elderly", "drug"]),
        "cha2ds2": ("cha2ds2_vasc", ["chf", "htn", "age", "dm", "stroke", "vasc", "female"]),
        "childpugh": ("child_pugh", ["bili", "alb", "inr", "ascites", "enceph"]),
        "apgar": ("apgar", ["appearance", "pulse", "grimace", "activity", "respiration"]),
        "bmi": ("bmi", ["ht", "wt"]),
        "bsa": ("bsa", ["ht", "wt"]),
        "bmr": ("bmr_tdee", ["age", "wt", "ht", "sex", "act"]),
        "whr": ("whr", ["waist", "hip"]),
        "maint": ("maintenance_fluid", ["wt"]),
        "parkland": ("parkland", ["wt", "tbsa"]),
        "dehydration": ("dehydration_correction", ["wt", "na", "rate_mode"]),
        "insulintdd": ("insulin_tdd", ["dm_type", "wt"]),
        "isf": ("isf", ["tdd"]),
        "icr": ("icr", ["tdd"]),
        "ivinsulin": ("iv_insulin", ["wt", "glucose"]),
        "dopamine": ("dopamine_prep", ["wt"]),
        "norepi": ("norepi_prep", ["wt"]),
        "dex": ("dex_conversion", ["dose", "route"]),
        "pedsdose": ("peds_dose", ["wt", "mg_per_kg", "freq"]),
        "dilution": ("dilution", ["c1", "c2", "v2", "v1"]),
        "solution": ("solution_conc", ["mass", "vol"]),
        "kclconc": ("kcl_check", ["amount", "total_vol"]),
        "insulinPrep": ("insulin_prep", ["wt"]),
        "pnprotein": ("tpn_protein", ["wt", "g_per_kg"]),
        "pnenergy": ("tpn_energy", ["wt", "kcal_per_kg"]),
        "pnmacro": ("tpn_macro", ["total_kcal", "carb_pct", "fat_pct", "prot_pct"]),
        "glucoserate": ("tpn_glucose_rate", ["gluc_g", "wt"]),
        "tnratio": ("tn_ratio", ["np_cal", "aa_g"]),
        "pnosm": ("tpn_osm", ["g_vol", "f_vol", "a_vol", "o_vol"]),
        "edd": ("edd", ["lmp"]),
        "fetalweight": ("fetal_weight", ["bpd", "hc", "ac", "fl"]),
        "glucconv": ("glucose_convert", ["val", "dir"]),
        "crconv": ("creatinine_convert", ["val", "dir"]),
        "caconv": ("calcium_convert", ["val", "dir"]),
        "mgconv": ("magnesium_convert", ["val", "dir"]),
        "biliconv": ("bilirubin_convert", ["val", "dir"]),
        "cholconv": ("cholesterol_convert", ["val", "dir"]),
        "tgconv": ("triglyceride_convert", ["val", "dir"]),
        "presconv": ("pressure_convert", ["val", "dir"]),
        "tempconv": ("temperature_convert", ["val", "dir"]),
    }

    if calc_id not in func_map:
        return {"main": "计算器未实现", "detail": ""}

    func_name, arg_keys = func_map[calc_id]
    func = getattr(engine, func_name, None)
    if not func:
        return {"main": "函数未找到", "detail": ""}

    args = [values.get(k) for k in arg_keys]
    args = [None if a == "" or a is None else a for a in args]

    try:
        result = func(*args)
        return result
    except Exception as e:
        return {"main": "计算错误", "detail": str(e)}


def _render_calc_card(calc):
    """渲染单个计算器卡片"""
    calc_id = calc["id"]
    if not st.session_state.get(f"open_calc_{calc_id}", False):
        return

    with st.container(border=True):
        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"### {calc['icon']} {calc['name']}")
        with col2:
            is_fav = calc_id in st.session_state.calc_favorites
            if st.button("⭐" if is_fav else "☆", key=f"fav_toggle_{calc_id}", help="收藏/取消"):
                if is_fav:
                    st.session_state.calc_favorites.discard(calc_id)
                else:
                    st.session_state.calc_favorites.add(calc_id)
                st.rerun()

        # 输入区
        inputs = calc.get("inputs", [])
        values = {}
        cols = st.columns(min(4, max(1, len(inputs))))
        for i, inp in enumerate(inputs):
            with cols[i % 4]:
                k = inp["k"]
                label = inp["l"]
                if inp.get("type") == "check":
                    values[k] = st.checkbox(label, key=f"inp_{calc_id}_{k}")
                elif inp.get("type") == "select":
                    opts = inp.get("opts", [])
                    values[k] = st.selectbox(label, opts, key=f"inp_{calc_id}_{k}")
                else:
                    step = inp.get("s", 0.1)
                    values[k] = st.number_input(
                        label, step=step,
                        format=f"%.{len(str(step).split('.')[-1])}f" if '.' in str(step) else "%g",
                        key=f"inp_{calc_id}_{k}", value=None,
                    )

        # 计算按钮
        if st.button("🧮 计算", key=f"compute_{calc_id}", type="primary", use_container_width=True):
            result = _run_calc(calc_id, values)
            if result:
                st.session_state[f"result_{calc_id}"] = result
            else:
                st.warning("请填写必要参数", icon="⚠️")

        # 结果显示
        if f"result_{calc_id}" in st.session_state:
            result = st.session_state[f"result_{calc_id}"]
            warn = result.get("warn", "")
            if warn:
                st.error(f"⚠️ {warn}")
            st.success(f"**{result['main']}**")
            if result.get("detail"):
                st.markdown(result["detail"], unsafe_allow_html=True)


# 收藏区
if st.session_state.calc_favorites and not search:
    fav_calcs = [c for c in calculators if c["id"] in st.session_state.calc_favorites]
    if fav_calcs:
        st.subheader("⭐ 收藏")
        cols = st.columns(min(6, max(1, len(fav_calcs))))
        for i, calc in enumerate(fav_calcs):
            with cols[i % 6]:
                if st.button(f"{calc['icon']} {calc['name']}", key=f"fav_{calc['id']}",
                             use_container_width=True):
                    st.session_state[f"open_calc_{calc['id']}"] = not st.session_state.get(
                        f"open_calc_{calc['id']}", False)

# 计算器按钮区
if search:
    st.subheader(f"搜索结果（{len(filtered)} 个）")
    if not filtered:
        st.info("未找到匹配的计算器")
    cols = st.columns(4)
    for i, calc in enumerate(filtered):
        with cols[i % 4]:
            if st.button(f"{calc['icon']} {calc['name']}", key=f"calc_btn_{calc['id']}",
                         use_container_width=True):
                st.session_state[f"open_calc_{calc['id']}"] = not st.session_state.get(
                    f"open_calc_{calc['id']}", False)
else:
    cat_icons = {"急算": "🚨", "肾脏": "🫘", "评分": "📊", "营养": "🥗", "补液": "💧",
                 "胰岛素": "💉", "配药": "💊", "TPN": "🧬", "产科": "🤰", "换算": "🔄"}
    for cat in categories:
        cat_calcs = [c for c in filtered if c["cat"] == cat]
        if not cat_calcs:
            continue
        with st.expander(f"{cat_icons.get(cat, '🧮')} {cat}（{len(cat_calcs)}个）", expanded=False):
            cols = st.columns(4)
            for i, calc in enumerate(cat_calcs):
                with cols[i % 4]:
                    btn_label = f"{'⭐' if calc['id'] in st.session_state.calc_favorites else ''} {calc['icon']} {calc['name']}"
                    if st.button(btn_label, key=f"calc_btn_{calc['id']}", use_container_width=True):
                        st.session_state[f"open_calc_{calc['id']}"] = not st.session_state.get(
                            f"open_calc_{calc['id']}", False)

# 渲染所有已打开的计算器卡片（关键：必须在按钮之后调用）
for calc in calculators:
    _render_calc_card(calc)

st.divider()
st.caption("💡 提示：所有计算仅供参考，临床决策请结合患者具体情况。")
