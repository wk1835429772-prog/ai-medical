"""规则配置页面 — API Key 配置 + 黄金规则管理 + 参考范围 + 系统提示词预览"""

import streamlit as st
import uuid

from core.database import init_database
init_database()

from config import REFERENCE_RANGES

st.set_page_config(page_title="规则配置 - 临床助手", page_icon="⚙️", layout="wide")
from core.ui_style import inject_global_css
inject_global_css()
st.title("⚙️ 设置")

tab1, tab2, tab3, tab4 = st.tabs(["🔑 API 配置", "📋 黄金规则", "📐 参考范围", "📜 系统提示词"])

# --- Tab 1: API 配置 ---
with tab1:
    st.subheader("DeepSeek API 配置")

    from core.database import get_connection
    from core.security import encrypt, decrypt

    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = 'api_key'").fetchone()
    conn.close()

    current_key = ""
    if row:
        try:
            current_key = decrypt(row["value"])
        except Exception:
            current_key = ""

    api_key = st.text_input(
        "API Key",
        type="password",
        value=current_key if current_key else "",
        placeholder="输入 DeepSeek API Key（sk-...）",
        help="API Key 将加密存储在本地数据库，不会上传到任何服务器。",
    )

    model_fast = st.selectbox(
        "快速模型（病历生成、常规问答）",
        ["deepseek-v4-flash", "deepseek-v4-pro"],
        index=0,
    )
    model_pro = st.selectbox(
        "推理模型（复杂鉴别诊断、矛盾分析）",
        ["deepseek-v4-pro", "deepseek-v4-flash"],
        index=0,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("💾 保存 API 配置", type="primary"):
            if api_key.strip():
                conn = get_connection()
                encrypted = encrypt(api_key.strip())
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('api_key', ?, datetime('now','localtime'))",
                    (encrypted,),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('model_fast', ?, datetime('now','localtime'))",
                    (model_fast,),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES ('model_pro', ?, datetime('now','localtime'))",
                    (model_pro,),
                )
                conn.commit()
                conn.close()
                st.success("✅ API 配置已保存")
            else:
                st.error("API Key 不能为空")
    with col2:
        if st.button("🧪 测试连接"):
            if not api_key.strip():
                st.error("请先输入 API Key")
            else:
                from openai import OpenAI
                try:
                    client = OpenAI(api_key=api_key.strip(), base_url="https://api.deepseek.com")
                    resp = client.chat.completions.create(
                        model=model_fast,
                        messages=[{"role": "user", "content": "你好，请回复'连接成功'"}],
                        max_tokens=20,
                    )
                    st.success(f"✅ 连接成功！模型响应：{resp.choices[0].message.content}")
                except Exception as e:
                    st.error(f"❌ 连接失败：{str(e)}")

    st.divider()
    st.caption("💡 提示：API Key 获取地址：https://platform.deepseek.com")

# --- Tab 2: 黄金规则 ---
with tab2:
    st.subheader("黄金规则管理")
    st.caption("规则将自动注入所有 AI 对话的 System Prompt")

    # 加载现有规则
    from core.database import get_connection
    conn = get_connection()
    rules = conn.execute("SELECT * FROM rules ORDER BY category, title").fetchall()
    conn.close()
    rules = [dict(r) for r in rules]

    # 添加规则
    with st.expander("➕ 添加新规则"):
        with st.form("add_rule_form"):
            rule_title = st.text_input("规则标题")
            rule_content = st.text_area("规则内容", height=100,
                                        placeholder="填写规则的具体内容，将注入到 AI 对话中...")
            rule_category = st.selectbox("分类", ["general", "diagnosis", "treatment", "report", "safety"])
            submitted = st.form_submit_button("保存规则")
            if submitted and rule_title.strip() and rule_content.strip():
                conn = get_connection()
                rule_id = uuid.uuid4().hex[:12]
                conn.execute(
                    "INSERT INTO rules (id, title, content, category) VALUES (?, ?, ?, ?)",
                    (rule_id, rule_title.strip(), rule_content.strip(), rule_category),
                )
                conn.commit()
                conn.close()
                st.success("✅ 规则已添加")
                st.rerun()

    # 显示现有规则
    if not rules:
        st.info("暂无自定义规则，点击上方添加")

    for rule in rules:
        with st.expander(f"{'🟢' if rule['is_active'] else '🔴'} [{rule['category']}] {rule['title']}"):
            st.text(rule['content'])
            col1, col2 = st.columns(2)
            with col1:
                new_state = not bool(rule['is_active'])
                if st.button(
                    "停用" if rule['is_active'] else "启用",
                    key=f"toggle_{rule['id']}",
                ):
                    conn = get_connection()
                    conn.execute("UPDATE rules SET is_active = ? WHERE id = ?",
                                 (1 if new_state else 0, rule['id']))
                    conn.commit()
                    conn.close()
                    st.rerun()
            with col2:
                if st.button("🗑️ 删除", key=f"del_rule_{rule['id']}"):
                    conn = get_connection()
                    conn.execute("DELETE FROM rules WHERE id = ?", (rule['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()

# --- Tab 3: 参考范围 ---
with tab3:
    st.subheader("临床参考范围设置")
    st.caption("调整各指标的正常值范围，将影响历史趋势页面的颜色标注。修改后自动保存到本地数据库。")

    from core.database import get_connection

    # 从数据库加载自定义范围，回退到 config 默认值
    def _load_ranges() -> dict:
        ranges = {}
        conn = get_connection()
        try:
            rows = conn.execute("SELECT key, value FROM settings WHERE key LIKE 'ref_%'").fetchall()
            import json
            for r in rows:
                metric_key = r["key"][4:]  # strip "ref_" prefix
                try:
                    ranges[metric_key] = dict(json.loads(r["value"]))
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            conn.close()
        return ranges

    custom_ranges = _load_ranges()

    def _get_ref(key):
        if key in custom_ranges:
            return custom_ranges[key]
        return REFERENCE_RANGES.get(key)

    st.markdown("##### 生命体征")
    vital_metrics = ["bp_sys", "bp_dia", "hr", "spo2", "rr", "temp"]
    for key in vital_metrics:
        ref = _get_ref(key)
        if not ref:
            continue
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.markdown(f"**{ref['label']}** ({ref['unit']})")
        with c2:
            lo = st.number_input(
                "下限", value=float(ref["lo"]), step=1.0,
                key=f"ref_lo_{key}", format="%g",
            )
        with c3:
            hi = st.number_input(
                "上限", value=float(ref["hi"]), step=1.0,
                key=f"ref_hi_{key}", format="%g",
            )
        with c4:
            if st.button("保存", key=f"ref_save_{key}"):
                import json
                conn = get_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
                    (f"ref_{key}", json.dumps({"label": ref["label"], "lo": lo, "hi": hi, "unit": ref["unit"]})),
                )
                conn.commit()
                conn.close()
                st.success(f"{ref['label']} 已更新")
                st.rerun()

    st.markdown("##### 血气分析")
    abg_metrics = ["abg_ph", "abg_pao2", "abg_paco2", "abg_hco3", "abg_lac"]
    for key in abg_metrics:
        ref = _get_ref(key)
        if not ref:
            continue
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.markdown(f"**{ref['label']}** ({ref['unit']})")
        with c2:
            lo = st.number_input(
                "下限", value=float(ref["lo"]), step=0.1,
                key=f"ref_lo_{key}", format="%.2f",
            )
        with c3:
            hi = st.number_input(
                "上限", value=float(ref["hi"]), step=0.1,
                key=f"ref_hi_{key}", format="%.2f",
            )
        with c4:
            if st.button("保存", key=f"ref_save_{key}"):
                import json
                conn = get_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
                    (f"ref_{key}", json.dumps({"label": ref["label"], "lo": lo, "hi": hi, "unit": ref["unit"]})),
                )
                conn.commit()
                conn.close()
                st.success(f"{ref['label']} 已更新")
                st.rerun()

    st.markdown("##### 感染指标")
    inf_metrics = ["wbc", "neut_pct", "pct", "il6"]
    for key in inf_metrics:
        ref = _get_ref(key)
        if not ref:
            continue
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.markdown(f"**{ref['label']}** ({ref['unit']})")
        with c2:
            lo = st.number_input(
                "下限", value=float(ref["lo"]), step=0.1,
                key=f"ref_lo_{key}", format="%.2f",
            )
        with c3:
            hi = st.number_input(
                "上限", value=float(ref["hi"]), step=0.1,
                key=f"ref_hi_{key}", format="%.2f",
            )
        with c4:
            if st.button("保存", key=f"ref_save_{key}"):
                import json
                conn = get_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
                    (f"ref_{key}", json.dumps({"label": ref["label"], "lo": lo, "hi": hi, "unit": ref["unit"]})),
                )
                conn.commit()
                conn.close()
                st.success(f"{ref['label']} 已更新")
                st.rerun()

    st.markdown("##### 其他指标")
    other_metrics = ["bnp", "ionized_ca", "albumin", "prealbumin", "d_dimer", "vent_fio2", "vent_peep"]
    for key in other_metrics:
        ref = _get_ref(key)
        if not ref:
            continue
        step = 0.01 if key in ("ionized_ca",) else (100 if key == "d_dimer" else 1)
        fmt = "%.2f" if key in ("ionized_ca",) else ("%g")
        c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
        with c1:
            st.markdown(f"**{ref['label']}** ({ref['unit']})")
        with c2:
            lo = st.number_input(
                "下限", value=float(ref["lo"]), step=float(step),
                key=f"ref_lo_{key}", format=fmt,
            )
        with c3:
            hi = st.number_input(
                "上限", value=float(ref["hi"]), step=float(step),
                key=f"ref_hi_{key}", format=fmt,
            )
        with c4:
            if st.button("保存", key=f"ref_save_{key}"):
                import json
                conn = get_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))",
                    (f"ref_{key}", json.dumps({"label": ref["label"], "lo": lo, "hi": hi, "unit": ref["unit"]})),
                )
                conn.commit()
                conn.close()
                st.success(f"{ref['label']} 已更新")
                st.rerun()

    st.divider()
    if st.button("🔄 恢复默认值", help="将所有参考范围恢复为系统默认值"):
        conn = get_connection()
        conn.execute("DELETE FROM settings WHERE key LIKE 'ref_%'")
        conn.commit()
        conn.close()
        st.success("已恢复默认值")
        st.rerun()


# --- Tab 4: 系统提示词预览 ---
with tab4:
    st.subheader("系统提示词预览")
    from prompts.prompt_builder import build_system_prompt
    full_prompt = build_system_prompt(include_rules=True)
    st.text_area("当前有效 System Prompt（含动态规则）", full_prompt, height=500, disabled=True)
    st.caption(f"提示：在「黄金规则」标签页添加/编辑规则后，此处会实时更新。")
