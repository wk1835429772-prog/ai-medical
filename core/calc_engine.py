"""医学计算器引擎 — 从 PWA 完整迁移 55+ 计算器"""

import math


def _round(n, d=1):
    """四舍五入到指定小数位"""
    if n is None or (isinstance(n, float) and math.isnan(n)):
        return None
    return round(n * 10**d) / 10**d


# ============================================================
# 急算
# ============================================================

def abg(ph, pco2, hco3, na, cl, k, lac, alb):
    """血气分析"""
    if ph is None or pco2 is None or hco3 is None:
        return None
    ph, pco2, hco3 = float(ph), float(pco2), float(hco3)
    na = float(na) if na is not None else None
    cl = float(cl) if cl is not None else None
    lac = float(lac) if lac is not None else None
    alb = float(alb) if alb is not None else None

    if ph < 7.35:
        state = "酸血症"
    elif ph > 7.45:
        state = "碱血症"
    else:
        state = "pH正常"

    primary, primary_detail = "", ""
    if ph < 7.35:
        if pco2 > 45:
            primary = "呼吸性酸中毒"
            primary_detail = f"PaCO₂ {pco2}>45"
        if hco3 < 22:
            primary += (" + " if primary else "") + "代谢性酸中毒"
            primary_detail += ("；" if primary_detail else "") + f"HCO₃⁻ {hco3}<22"
    elif ph > 7.45:
        if pco2 < 35:
            primary = "呼吸性碱中毒"
            primary_detail = f"PaCO₂ {pco2}<35"
        if hco3 > 26:
            primary += (" + " if primary else "") + "代谢性碱中毒"
            primary_detail += ("；" if primary_detail else "") + f"HCO₃⁻ {hco3}>26"
    else:
        if pco2 > 45 and hco3 > 26:
            primary = "混合性紊乱（待定）"
        elif pco2 < 35 and hco3 < 22:
            primary = "混合性紊乱（待定）"
        else:
            primary = "无明显原发紊乱"

    lines = [f"① {state}（pH {ph}）", f"② 原发紊乱: {primary}"]

    has_met_acid = "代谢性酸中毒" in primary
    has_met_alk = "代谢性碱中毒" in primary
    has_resp_acid = "呼吸性酸中毒" in primary
    has_resp_alk = "呼吸性碱中毒" in primary

    if has_met_acid and not has_resp_acid and not has_resp_alk:
        exp_pco2 = 1.5 * hco3 + 8
        lo, hi = _round(exp_pco2 - 2), _round(exp_pco2 + 2)
        msg = "合并呼碱" if pco2 < lo else "合并呼酸" if pco2 > hi else "代偿适当"
        lines.append(f"③ 代偿: 预计PaCO₂ {_round(exp_pco2)}（{lo}-{hi}）→ {msg}")
    elif has_met_alk and not has_resp_acid and not has_resp_alk:
        exp_pco2 = 0.7 * hco3 + 21
        lo, hi = _round(exp_pco2 - 2), _round(exp_pco2 + 2)
        msg = "合并呼碱" if pco2 < lo else "合并呼酸" if pco2 > hi else "代偿适当"
        lines.append(f"③ 代偿: 预计PaCO₂ {_round(exp_pco2)}（{lo}-{hi}）→ {msg}")
    elif has_resp_acid and not has_met_acid and not has_met_alk:
        dc = pco2 - 40
        acute = _round(24 + dc * 0.1)
        chronic = _round(24 + dc * 0.35)
        is_chronic = abs(hco3 - chronic) <= abs(hco3 - acute)
        lines.append(f"③ 急/慢: 急性HCO₃⁻ {acute}，慢性 {chronic}，实测 {hco3} → {'慢性' if is_chronic else '急性'}呼酸")
    elif has_resp_alk and not has_met_acid and not has_met_alk:
        dc = 40 - pco2
        acute = _round(24 - dc * 0.2)
        chronic = _round(24 - dc * 0.5)
        is_chronic = abs(hco3 - chronic) <= abs(hco3 - acute)
        lines.append(f"③ 急/慢: 急性HCO₃⁻ {acute}，慢性 {chronic}，实测 {hco3} → {'慢性' if is_chronic else '急性'}呼碱")
    else:
        lines.append("③ 代偿: 混合紊乱，公式不适用")

    warn = ""
    if na is not None and cl is not None:
        ag = _round(na - cl - hco3)
        eff_ag = ag
        ag_str = f"AG = {ag}"
        if alb is not None:
            eff_ag = _round(ag + 2.5 * (4 - alb / 10))
            ag_str += f" → 校正AG = {eff_ag}"
        ag_str += " ⬆️" if eff_ag > 16 else " ⬇️" if eff_ag < 8 else " ✓"
        lines.append(f"④ 阴离子间隙: {ag_str}")
        if eff_ag > 16 and hco3 < 24:
            dd = _round((eff_ag - 12) / (24 - hco3), 2)
            if dd and dd > 0:
                dd_msg = "合并正常AG代酸" if dd < 1 else "单纯高AG代酸" if dd <= 2 else "合并代碱"
                lines.append(f"⑤ Δ-Δ = {dd} → {dd_msg}")

    if lac is not None and lac > 2:
        lines.append(f"⑥ 乳酸: {lac} ⬆️")
        if lac > 4:
            warn = "乳酸>4, 严重乳酸酸中毒"
    if k is not None and k < 3.5:
        lines.append(f"⑦ K⁺: {k} 低钾")
    if k is not None and k > 5.0:
        lines.append(f"⑦ K⁺: {k} 高钾")

    return {"main": f"{state} · {primary}", "detail": "<br>".join(lines), "warn": warn}


def nadeficit(na, wt, sex):
    """低钠补钠"""
    if not na or not wt:
        return None
    na, wt = float(na), float(wt)
    factor = 0.5 if sex == "女" else 0.6
    deficit = round((140 - na) * wt * factor)
    rate = round(deficit / 72)
    return {"main": f"缺钠量 ≈ {deficit} mmol", "detail": f"TBW系数 {factor}（{sex or '男'}）<br>按72h纠正: 约{rate} mmol/h<br>纠正速度 ≤ 0.5 mmol/L/h"}


def pumprate(drug, dose_mg, vol_ml, wt, target):
    """泵速计算"""
    if not dose_mg or not vol_ml or not wt:
        return None
    dose_mg, vol_ml, wt = float(dose_mg), float(vol_ml), float(wt)
    conc = dose_mg / vol_ml
    if not target:
        return {"main": f"浓度 = {_round(conc, 2)} mg/mL",
                "detail": f"配法: {dose_mg}mg + NS 至 {vol_ml}mL"}
    target = float(target)
    # default: mcg/kg/min → mL/h
    mlh = target * wt * 60 / (conc * 1000)
    return {"main": f"泵速 = {_round(mlh, 1)} mL/h",
            "detail": f"目标 {target} mcg/kg/min<br>浓度 {_round(conc, 2)} mg/mL"}


def lactate_clearance(lac1, lac2):
    """乳酸清除率"""
    if not lac1 or not lac2:
        return None
    lac1, lac2 = float(lac1), float(lac2)
    clearance = _round((lac1 - lac2) / lac1 * 100)
    ok = clearance >= 20
    return {"main": f"乳酸清除率 = {clearance}%",
            "detail": f"{'✅' if ok else '⚠️'} {'清除率≥20%，复苏有效' if ok else '清除率<20%，需继续积极复苏'}"}


def map_calc(sbp, dbp):
    """平均动脉压"""
    if not sbp or not dbp:
        return None
    sbp, dbp = float(sbp), float(dbp)
    map_val = round((sbp + 2 * dbp) / 3)
    status = "✅ 灌注压达标" if map_val >= 65 else "⚠️ 灌注压不足"
    return {"main": f"MAP = {map_val} mmHg", "detail": status}


def hyperk(k):
    """高钾处理"""
    if not k:
        return None
    k = float(k)
    lines = []
    if k >= 7.0:
        level = "危急"
        lines.append("⚠️ 立即心电监护！准备紧急处理")
    elif k >= 6.0:
        level = "严重"
        lines.append("⚠️ 需紧急处理")
    elif k >= 5.5:
        level = "中度"
        lines.append("需积极处理")
    else:
        level = "轻度"

    lines.append("1. 10%葡萄糖酸钙 10mL iv (稳定心肌)")
    if k >= 6.0:
        lines.append("2. RI 10U + 50%GS 50mL iv (促K⁺内移)")
    lines.append(f"{'3' if k >= 6.0 else '2'}. 聚苯乙烯磺酸钠 15-30g po (排K⁺)")
    lines.append(f"{'4' if k >= 6.0 else '3'}. 呋塞米 20-40mg iv (利尿排K⁺)")
    if k >= 7.0:
        lines.append("5. 碳酸氢钠 150mL iv (纠酸促K⁺内移)")
    lines.append(f"{'6' if k >= 7.0 else '5'}. 排查原因（药物、肾功能、溶血等）")
    return {"main": f"K⁺ {k} mmol/L — {level}高钾血症",
            "detail": "<br>".join(lines),
            "warn": f"K⁺ {k} — {level}高钾血症，需紧急处理" if level in ("危急", "严重") else ""}


def insulin_drip(glucose):
    """胰岛素泵速"""
    if not glucose:
        return None
    glucose = float(glucose)
    if glucose > 20:
        rate = "4-6 U/h"
    elif glucose > 15:
        rate = "2-4 U/h"
    elif glucose > 11:
        rate = "1-2 U/h"
    else:
        rate = "0.5-1 U/h"
    return {"main": f"起始泵速 {rate}",
            "detail": f"血糖 {glucose} mmol/L<br>配法: RI 50U + NS 49.5mL (1U/mL)<br>每1-2h监测血糖"}


def corrected_ca(ca, alb):
    """校正钙"""
    if not ca or not alb:
        return None
    ca, alb = float(ca), float(alb)
    corrected = _round(ca + 0.02 * (40 - alb), 2)
    return {"main": f"校正钙 = {corrected} mmol/L", "detail": f"{ca} + 0.02×(40-{alb})"}


def na_correction(na, glu):
    """校正钠(血糖)"""
    if not na or not glu:
        return None
    na, glu = float(na), float(glu)
    corrected = _round(na + 0.024 * (glu - 5.5), 1)
    return {"main": f"校正Na⁺ = {corrected} mmol/L", "detail": f"{na} + 0.024×({glu}-5.5)"}


def dka_fluids(wt, degree, glucose, k):
    """DKA/HHS补液"""
    if not wt or not degree:
        return None
    wt, degree = float(wt), float(degree)
    total = round(wt * degree * 1000)
    p1 = round(wt * 20)
    p2 = round((total - p1) * 0.5)
    p3 = total - p1 - p2
    ins_r = _round(wt * 0.1, 2)
    if k is not None:
        k = float(k)
        k_guide = "暂不补钾" if k > 5 else "KCl 15mL/袋" if k > 3.5 else "KCl 30mL/袋,心电监护"
    else:
        k_guide = "查血钾后决定"
    return {"main": f"DKA/HHS 补液 {total}mL",
            "detail": f"①NS {p1}mL@{p1}mL/h(1h) ②NS {p2}mL@{round(p2/7)}mL/h(2-8h) ③5%GNS {p3}mL@{round(p3/16)}mL/h(8-24h)<br>RI {ins_r}U/h(0.1U/kg/h)<br>补钾：{k_guide}<br>血糖13.9后换5%GS+RI减量"}


# ============================================================
# 肾脏
# ============================================================

def egfr(cr, age, sex):
    """eGFR CKD-EPI"""
    if not cr or not age:
        return None
    cr, age = float(cr), float(age)
    scr = cr / 88.4
    k = 0.7 if sex == "女" else 0.9
    alpha = -0.241 if sex == "女" else -0.302
    sex_fac = 1.012 if sex == "女" else 1
    if scr <= k:
        gfr = 142 * (scr / k) ** alpha * (0.9938 ** age) * sex_fac
    else:
        gfr = 142 * (scr / k) ** (-1.2) * (0.9938 ** age) * sex_fac
    gfr = round(gfr)
    stage = "G1" if gfr >= 90 else "G2" if gfr >= 60 else "G3a" if gfr >= 45 else "G3b" if gfr >= 30 else "G4" if gfr >= 15 else "G5"
    return {"main": f"eGFR = {gfr} mL/min/1.73m²", "detail": f"CKD-EPI · {stage}期"}


def cockcroft_gault(age, wt, cr, sex):
    """Cockcroft-Gault 肌酐清除率"""
    if not age or not wt or not cr:
        return None
    age, wt, cr = float(age), float(wt), float(cr)
    cr_mg = cr / 88.4
    crcl = ((140 - age) * wt) / (72 * cr_mg)
    if sex == "女":
        crcl *= 0.85
    crcl = _round(crcl, 1)
    return {"main": f"CrCl = {crcl} mL/min", "detail": "Cockcroft-Gault"}


def kdeficit(k, wt):
    """补钾"""
    if not k or not wt:
        return None
    k, wt = float(k), float(wt)
    deficit = round((3.5 - k) / 0.3 * 100)
    max_rate = min(round(wt * 0.5), 20)
    warn = ""
    if k < 2.5:
        warn = "严重低钾！需心电监护，中心静脉高浓度补钾"
    elif k < 3.0:
        warn = "中重度低钾，建议静脉补钾"
    return {"main": f"缺钾 ≈ {deficit} mmol",
            "detail": f"安全补钾上限: {max_rate} mmol/h(外周){'<br>⚠️ ' + warn if warn else ''}",
            "warn": warn}


def anion_gap(na, cl, hco3):
    """阴离子间隙"""
    if not na or not cl or not hco3:
        return None
    ag = _round(float(na) - (float(cl) + float(hco3)))
    interp = "升高 ⬆️ 高AG代酸" if ag > 12 else "正常（12±4）" if ag >= 8 else "偏低"
    return {"main": f"AG = {ag} mmol/L", "detail": interp}


def osmgap(na, glu, bun, osm):
    """渗透压间隙"""
    if not na or not glu or not bun or not osm:
        return None
    calc_osm = 2 * float(na) + float(glu) / 18 + float(bun) / 2.8
    gap = _round(float(osm) - calc_osm)
    interp = "正常(<10)" if gap < 10 else "升高 ⚠️ 考虑中毒（甲醇/乙二醇等）"
    return {"main": f"渗透压间隙 = {gap} mOsm/L", "detail": f"计算渗透压 = {_round(calc_osm)}<br>{interp}"}


def schwartz(ht, cr):
    """Schwartz公式(儿童eGFR)"""
    if not ht or not cr:
        return None
    egfr_val = _round(36.5 * float(ht) / float(cr), 1)
    return {"main": f"eGFR = {egfr_val} mL/min/1.73m²", "detail": "Schwartz公式(经典系数36.5)"}


# ============================================================
# 评分
# ============================================================

def sofa(pao2, fio2, plt, bili, map_val, gcs, cr, vaso, uo):
    """SOFA评分"""
    total = 0
    details = []
    if pao2 is not None and fio2 is not None:
        pf = float(pao2) / (float(fio2) / 100)
        r = 4 if pf < 100 else 3 if pf < 200 else 2 if pf < 300 else 1 if pf < 400 else 0
        total += r
        details.append(f"呼吸 P/F={round(pf)} → {r}分")
    if plt is not None:
        plt = float(plt)
        r = 4 if plt < 20 else 3 if plt < 50 else 2 if plt < 100 else 1 if plt < 150 else 0
        total += r
        details.append(f"凝血 PLT={plt} → {r}分")
    if bili is not None:
        bili = float(bili)
        mg = bili / 17.1
        r = 4 if mg >= 12 else 3 if mg >= 6 else 2 if mg >= 2 else 1 if mg >= 1.2 else 0
        total += r
        details.append(f"肝脏 TB={bili} → {r}分")
    if vaso is not None and float(vaso) > 0:
        v = int(float(vaso))
        total += v
        labels = ["", "多巴胺≤5", "多巴胺>5 或 NE≤0.1", "多巴胺>15 或 NE>0.1"]
        details.append(f"心血管 {labels[v]} → {v}分")
    elif map_val is not None:
        r = 1 if float(map_val) < 70 else 0
        total += r
        details.append(f"心血管 MAP={map_val} → {r}分")
    if gcs is not None:
        gcs = float(gcs)
        r = 4 if gcs < 6 else 3 if gcs < 10 else 2 if gcs < 13 else 1 if gcs < 15 else 0
        total += r
        details.append(f"CNS GCS={gcs} → {r}分")
    if cr is not None:
        cr = float(cr)
        mg = cr / 88.4
        r = 4 if mg >= 5.0 else 3 if mg >= 3.5 else 2 if mg >= 2.0 else 1 if mg >= 1.2 else 0
        total += r
        details.append(f"肾脏 Cr={cr} → {r}分")
    elif uo is not None:
        uo = float(uo)
        r = 4 if uo < 200 else 3 if uo < 500 else 0
        total += r
        details.append(f"肾脏 尿量={uo}mL/d → {r}分")
    mort = ">95%" if total >= 15 else "~80%" if total >= 13 else "~50%" if total >= 10 else "~20%" if total >= 7 else "~10%" if total >= 4 else "<5%"
    return {"main": f"SOFA = {total} 分", "detail": "<br>".join(details) + f"<br>死亡率约 {mort}"}


def gcs(eye, verbal, motor):
    """GCS评分"""
    if eye is None or verbal is None or motor is None:
        return None
    total = int(float(eye)) + int(float(verbal)) + int(float(motor))
    level = "严重昏迷" if total <= 8 else "中度昏迷" if total <= 12 else "轻度"
    return {"main": f"GCS = {total} 分", "detail": f"{level}<br>睁眼{eye} + 语言{verbal} + 运动{motor}"}


def curb65(conf, bun, rr, bp, age65):
    """CURB-65"""
    score = sum([1 for v in [conf, bun and float(bun) > 7, rr, bp, age65] if v])
    level = "低危" if score <= 1 else "中危" if score <= 2 else "高危"
    mort = "<1%" if score <= 1 else "3-9%" if score <= 2 else "9-40%"
    return {"main": f"{score} 分 — {level}", "detail": f"30天死亡率约 {mort}<br>{'住院，≥4评估ICU' if score >= 3 else '留观/短期住院' if score >= 2 else '可门诊'}"}


def wells_pe(dvt, pe, hr, imm, dvthx, hemo, mal):
    """Wells PE评分"""
    score = 0
    if dvt: score += 3
    if pe: score += 3
    if hr: score += 1.5
    if imm: score += 1.5
    if dvthx: score += 1.5
    if hemo: score += 1
    if mal: score += 1
    risk = "高危" if score > 6 else "中危" if score > 4 else "低-中危"
    detail = "建议CTPA" if score > 4 else "考虑D-二聚体排除"
    return {"main": f"{score} 分 — {risk}", "detail": detail}


def hasbled(htn, renal, stroke, bleed, labile, elderly, drug):
    """HAS-BLED评分"""
    score = sum([1 for v in [htn, stroke, bleed, labile, elderly, drug] if v])
    if renal: score += 2
    return {"main": f"{score} 分 — {'出血高风险' if score >= 3 else '低-中风险'}",
            "detail": f"年大出血率: 0分=1%, 3分=3.7%, ≥5分=12.5%"}


def cha2ds2_vasc(chf, htn, age, dm, stroke, vasc, female):
    """CHA₂DS₂-VASc"""
    if age is None:
        return None
    score = 0
    if chf: score += 1
    if htn: score += 1
    if age >= 75: score += 2
    elif age >= 65: score += 1
    if dm: score += 1
    if stroke: score += 2
    if vasc: score += 1
    if female: score += 1
    rates = {0: "0%", 1: "1.3%", 2: "2.2%", 3: "3.2%", 4: "4.0%", 5: "6.7%", 6: "9.8%", 7: "9.6%", 8: "6.7%", 9: "15.2%"}
    rate = rates.get(score, "≥15%")
    need_ac = (score - (1 if female else 0)) >= 1
    return {"main": f"{score} 分 · 年卒中率 {rate}",
            "detail": f"抗凝建议: {'推荐口服抗凝（NOAC优先）' if need_ac else '不推荐抗凝'}",
            "warn": "高危，强烈推荐抗凝" if score >= 4 else ""}


def child_pugh(bili, alb, inr, ascites, enceph):
    """Child-Pugh"""
    if not bili or not alb or not inr:
        return None
    bili, alb, inr = float(bili), float(alb), float(inr)
    score = 0
    score += 1 if bili < 34 else 2 if bili < 50 else 3
    score += 1 if alb > 35 else 2 if alb > 28 else 3
    score += 1 if inr < 1.7 else 2 if inr < 2.3 else 3
    score += int(ascites or 0)
    score += int(enceph or 0)
    grade = "A(轻度)" if score <= 6 else "B(中度)" if score <= 9 else "C(重度)"
    return {"main": f"{score} 分 — {grade}", "detail": "1年生存率: A~100%, B~80%, C~45%"}


def apgar(appearance, pulse, grimace, activity, respiration):
    """Apgar评分"""
    vals = [appearance, pulse, grimace, activity, respiration]
    if any(v is None for v in vals):
        return None
    total = sum(int(v) for v in vals)
    interp = "正常" if total >= 7 else "轻度窒息" if total >= 4 else "重度窒息"
    return {"main": f"Apgar = {total} 分", "detail": f"{interp}"}


# ============================================================
# 营养
# ============================================================

def bmi(ht, wt):
    """BMI"""
    if not ht or not wt:
        return None
    ht, wt = float(ht), float(wt)
    bmi_val = _round(wt / (ht / 100) ** 2)
    grade = "偏瘦" if bmi_val < 18.5 else "正常" if bmi_val < 24 else "超重" if bmi_val < 28 else "肥胖"
    ideal_lo = _round(18.5 * (ht / 100) ** 2)
    ideal_hi = _round(23.9 * (ht / 100) ** 2)
    return {"main": f"BMI = {bmi_val} kg/m²", "detail": f"{grade} · 理想体重 {ideal_lo}-{ideal_hi} kg"}


def bsa(ht, wt):
    """体表面积"""
    if not ht or not wt:
        return None
    ht, wt = float(ht), float(wt)
    dubois = _round(0.007184 * ht ** 0.725 * wt ** 0.725, 2)
    mosteller = _round(math.sqrt(ht * wt / 3600), 2)
    return {"main": f"BSA = {dubois} m²", "detail": f"Du Bois: {dubois} m²<br>Mosteller: {mosteller} m²"}


def bmr_tdee(age, wt, ht, sex, act):
    """BMR/TDEE"""
    if not age or not wt or not ht:
        return None
    age, wt, ht = float(age), float(wt), float(ht)
    act = float(act) if act else 1.2
    if sex == "女":
        msj = 10 * wt + 6.25 * ht - 5 * age - 161
    else:
        msj = 10 * wt + 6.25 * ht - 5 * age + 5
    tdee = round(msj * act)
    return {"main": f"TDEE ≈ {tdee} kcal/d", "detail": f"Mifflin-St Jeor: {round(msj)} kcal<br>活动系数: ×{act}"}


def whr(waist, hip):
    """腰臀比"""
    if not waist or not hip:
        return None
    ratio = _round(float(waist) / float(hip), 2)
    return {"main": f"WHR = {ratio}"}


# ============================================================
# 补液
# ============================================================

def maintenance_fluid(wt):
    """维持液量 4-2-1"""
    if not wt:
        return None
    wt = float(wt)
    if wt <= 10:
        mlh = wt * 4
    elif wt <= 20:
        mlh = 40 + (wt - 10) * 2
    else:
        mlh = 60 + (wt - 20) * 1
    mld = round(mlh * 24)
    return {"main": f"{round(mlh)} mL/h (总量 {mld} mL/d)", "detail": "4-2-1法则"}


def parkland(wt, tbsa):
    """Parkland烧伤补液"""
    if not wt or not tbsa:
        return None
    wt, tbsa = float(wt), float(tbsa)
    total = 4 * wt * tbsa
    rate8 = round(total / 2 / 8)
    rate16 = round(total / 2 / 16)
    return {"main": f"24h总量 {total} mL",
            "detail": f"前8h: {round(total/2)}mL @{rate8}mL/h<br>后16h: {round(total/2)}mL @{rate16}mL/h"}


def dehydration_correction(wt, na, rate_mode):
    """脱水补液"""
    if not wt or not na:
        return None
    wt, na = float(wt), float(na)
    deficit = _round(wt * 0.6 * (na / 140 - 1), 2)
    rates = {"safe": (72, 0.5), "slow": (48, 0.5), "fast": (24, 1.0)}
    rm = rates.get(rate_mode, rates["safe"])
    hr = round(abs(deficit) * 1000 / rm[0])
    fluid = "5%GS" if na > 150 else "3%高渗盐水" if na < 120 else "5%GNS"
    return {"main": f"缺水≈{abs(deficit)}L",
            "detail": f"{rm[0]}h纠正，{hr}mL/h<br>液体：{fluid}<br>目标下降速度≤{rm[1]}mmol/L/h",
            "warn": "严重低钠！渗透性脱髓鞘风险" if na < 120 else ""}


# ============================================================
# 胰岛素
# ============================================================

def insulin_tdd(dm_type, wt):
    """胰岛素TDD"""
    if not wt:
        return None
    wt = float(wt)
    lo = 0.3 if dm_type == 1 else 0.2
    hi = 0.6 if dm_type == 1 else 0.4
    return {"main": f"TDD: {round(wt * lo)}-{round(wt * hi)} U/d",
            "detail": f"基础: {round(wt*lo/2)}-{round(wt*hi/2)}U<br>餐时: {round(wt*lo/2)}-{round(wt*hi/2)}U"}


def isf(tdd):
    """胰岛素敏感系数"""
    if not tdd:
        return None
    tdd = float(tdd)
    return {"main": f"ISF = {_round(100/tdd, 1)} mmol/L/U", "detail": f"100法则"}


def icr(tdd):
    """胰岛素碳水比"""
    if not tdd:
        return None
    tdd = float(tdd)
    return {"main": f"ICR = {_round(28/tdd, 1)} g碳水/U", "detail": "500/28法则"}


def iv_insulin(wt, glucose):
    """静脉胰岛素泵速"""
    if not wt:
        return None
    wt = float(wt)
    rate = _round(wt * 0.1, 1) if glucose is None else _round(wt * 0.1, 1)
    return {"main": f"起始 {rate} U/h", "detail": f"RI 50U + NS 49.5mL (1U/mL)<br>0.1U/kg/h = {rate}mL/h"}


# ============================================================
# 配药
# ============================================================

def dopamine_prep(wt):
    """多巴胺配法"""
    if not wt:
        return None
    dose = round(float(wt) * 3)
    return {"main": f"{dose}mg + NS 至 50mL", "detail": f"1mL/h = 1μg/kg/min<br>体重{wt}kg × 3"}


def norepi_prep(wt):
    """去甲肾配法"""
    if not wt:
        return None
    wt = float(wt)
    return {"main": f"{_round(wt*0.3,1)}mg + NS 至 50mL",
            "detail": f"1mL/h = 0.1μg/kg/min<br>起始 0.05-0.1μg/kg/min"}


def dex_conversion(dose, route):
    """地塞米松换算"""
    if not dose:
        return None
    dose = float(dose)
    eq = dose * 5 if route == "iv" else dose * 0.75
    return {"main": f"≈ {_round(eq, 1)} mg 泼尼松当量",
            "detail": f"地塞米松 {dose}mg{' iv' if route == 'iv' else ' po'}"}


def peds_dose(wt, mg_per_kg, freq):
    """儿科药物剂量"""
    if not wt or not mg_per_kg:
        return None
    wt, mg_per_kg = float(wt), float(mg_per_kg)
    dose = _round(wt * mg_per_kg, 1)
    if freq:
        daily = _round(dose * float(freq), 1)
        return {"main": f"{dose} mg/次", "detail": f"{mg_per_kg}mg/kg × {wt}kg<br>{freq}次/日 = {daily}mg/d"}
    return {"main": f"{dose} mg", "detail": f"{mg_per_kg}mg/kg × {wt}kg"}


def dilution(c1, c2, v2, v1):
    """稀释计算器 C1V1=C2V2"""
    if not c1 or not c2:
        return None
    c1, c2 = float(c1), float(c2)
    if v2:
        r = _round(c2 * float(v2) / c1, 2)
        return {"main": f"V₁ = {r} mL", "detail": f"取{r}mL原液定容至{v2}mL"}
    if v1:
        r = _round(c1 * float(v1) / c2, 2)
        return {"main": f"V₂ = {r} mL", "detail": f"移取{v1}mL原液定容至{r}mL"}
    return None


def solution_conc(mass, vol):
    """溶液浓度"""
    if not mass or not vol:
        return None
    return {"main": f"{_round(float(mass)/float(vol), 2)} mg/mL", "detail": f"{mass}mg / {vol}mL"}


def kcl_check(amount, total_vol):
    """KCl浓度检查"""
    if not amount or not total_vol:
        return None
    amount, total_vol = float(amount), float(total_vol)
    pct = _round(amount / total_vol * 100, 2)
    mmol = _round(amount / 74.55 / total_vol * 1000, 1)
    return {"main": f"{pct}%（{mmol} mmol/L）",
            "detail": f"{amount}mg KCl / {total_vol}mL",
            "warn": "外周静脉禁用！必须CVC" if pct > 0.3 else "建议CVC" if pct > 0.2 else ""}


def insulin_prep(wt):
    """胰岛素配制"""
    if not wt:
        return None
    wt = float(wt)
    return {"main": "RI 50U + NS 49.5mL (1U/mL)", "detail": f"起始 0.1U/kg/h = {_round(wt*0.1,2)} mL/h"}


# ============================================================
# TPN
# ============================================================

def tpn_protein(wt, g_per_kg):
    """TPN蛋白量"""
    if not wt:
        return None
    wt = float(wt)
    g_per_kg = float(g_per_kg) if g_per_kg else 1.2
    prot = _round(wt * g_per_kg)
    n2 = _round(prot * 0.16)
    return {"main": f"{prot} g/d", "detail": f"{g_per_kg} g/kg × {wt}kg<br>氮量 ≈ {n2}g | 供能 ≈ {round(prot*4)}kcal"}


def tpn_energy(wt, kcal_per_kg):
    """TPN能量"""
    if not wt:
        return None
    total = round(float(wt) * float(kcal_per_kg or 25))
    return {"main": f"{total} kcal/d", "detail": f"{kcal_per_kg or 25} kcal/kg × {wt}kg"}


def tpn_macro(total_kcal, carb_pct, fat_pct, prot_pct):
    """TPN宏量营养素"""
    if not total_kcal:
        return None
    total_kcal = float(total_kcal)
    carb_pct = float(carb_pct or 60)
    fat_pct = float(fat_pct or 25)
    prot_pct = float(prot_pct or 15)
    c_g = _round(total_kcal * carb_pct / 100 / 3.4)
    f_g = _round(total_kcal * fat_pct / 100 / 10)
    p_g = _round(total_kcal * prot_pct / 100 / 4)
    pct_sum = carb_pct + fat_pct + prot_pct
    return {"main": f"糖{c_g}g 脂{f_g}g 蛋白{p_g}g",
            "detail": f"50%GS:{round(c_g/0.5)}mL 20%脂肪乳:{round(f_g/0.2)}mL 8.5%AA:{round(p_g/0.085)}mL",
            "warn": f"供能比之和={pct_sum}%≠100%" if pct_sum != 100 else ""}


def tpn_glucose_rate(gluc_g, wt):
    """TPN糖速"""
    if not gluc_g or not wt:
        return None
    gluc_g, wt = float(gluc_g), float(wt)
    rate = _round(gluc_g * 1000 / (wt * 1440), 2)
    return {"main": f"{rate} mg/kg/min",
            "detail": f"{gluc_g}g/d ÷ {wt}kg ÷ 1440min",
            "warn": "速率>5,建议CVC" if rate > 5 else "速率接近上限,注意血糖" if rate > 4 else ""}


def tn_ratio(np_cal, aa_g):
    """热氮比"""
    if not np_cal or not aa_g:
        return None
    np_cal, aa_g = float(np_cal), float(aa_g)
    n2 = aa_g * 0.16
    ratio = round(np_cal / n2)
    interp = "理想范围" if 100 <= ratio <= 150 else "偏低,增加非蛋白热量" if ratio < 100 else "偏高,增加氨基酸"
    return {"main": f"热氮比 = {ratio}:1",
            "detail": f"氮量={_round(n2,1)}g<br>{interp}",
            "warn": interp if ratio < 100 or ratio > 150 else ""}


def tpn_osm(g_vol, f_vol, a_vol, o_vol):
    """TPN渗透压"""
    g_vol = float(g_vol or 0)
    f_vol = float(f_vol or 0)
    a_vol = float(a_vol or 0)
    o_vol = float(o_vol or 0)
    total = g_vol + f_vol + a_vol + o_vol
    if not total:
        return None
    osm = round((g_vol * 2500 + f_vol * 350 + a_vol * 800 + o_vol * 300) / total)
    return {"main": f"总量{total}mL 渗透压≈{osm}mOsm/L",
            "warn": "必须CVC!" if osm > 900 else "建议CVC" if osm > 600 else ""}


# ============================================================
# 产科
# ============================================================

def edd(lmp_str):
    """预产期"""
    if not lmp_str:
        return None
    from datetime import date, timedelta
    try:
        lmp = date.fromisoformat(lmp_str)
        edd_date = lmp + timedelta(days=280)
        ga_days = (date.today() - lmp).days
        ga_weeks = ga_days // 7
        ga_rem = ga_days % 7
        return {"main": f"预产期: {edd_date.isoformat()}", "detail": f"目前孕{ga_weeks}周{ga_rem}天（LMP: {lmp_str}）"}
    except (ValueError, TypeError):
        return None


def fetal_weight(bpd, hc, ac, fl):
    """胎儿体重(Hadlock)"""
    if not bpd or not hc or not ac or not fl:
        return None
    bpd, hc, ac, fl = float(bpd), float(hc), float(ac), float(fl)
    efw = round(10 ** (1.3596 + 0.0064 * hc + 0.0424 * ac + 0.174 * fl + 0.00061 * bpd * ac - 0.00386 * ac * fl) / 1000, 2)
    return {"main": f"EFW ≈ {efw} kg", "detail": "Hadlock公式(4参数)"}


# ============================================================
# 单位换算
# ============================================================

def glucose_convert(val, direction):
    """血糖换算 mmol/L ↔ mg/dL"""
    if not val:
        return None
    val = float(val)
    if direction == "to_mg":
        return {"main": f"{_round(val * 18.02, 1)} mg/dL"}
    return {"main": f"{_round(val / 18.02, 2)} mmol/L"}


def creatinine_convert(val, direction):
    """肌酐换算 μmol/L ↔ mg/dL"""
    if not val:
        return None
    val = float(val)
    if direction == "to_mg":
        return {"main": f"{_round(val / 88.4, 2)} mg/dL"}
    return {"main": f"{_round(val * 88.4)} μmol/L"}


def calcium_convert(val, direction):
    """钙换算 mmol/L ↔ mg/dL"""
    if not val:
        return None
    val = float(val)
    if direction == "to_mg":
        return {"main": f"{_round(val * 4, 1)} mg/dL"}
    return {"main": f"{_round(val / 4, 2)} mmol/L"}


def magnesium_convert(val, direction):
    """镁换算 mmol/L ↔ mg/dL"""
    if not val:
        return None
    val = float(val)
    if direction == "to_mg":
        return {"main": f"{_round(val * 2.43, 1)} mg/dL"}
    return {"main": f"{_round(val / 2.43, 2)} mmol/L"}


def bilirubin_convert(val, direction):
    """胆红素换算 μmol/L ↔ mg/dL"""
    if not val:
        return None
    val = float(val)
    if direction == "to_mg":
        return {"main": f"{_round(val / 17.1, 2)} mg/dL"}
    return {"main": f"{_round(val * 17.1, 1)} μmol/L"}


def cholesterol_convert(val, direction):
    """胆固醇换算 mmol/L ↔ mg/dL"""
    if not val:
        return None
    val = float(val)
    if direction == "to_mg":
        return {"main": f"{_round(val * 38.67, 1)} mg/dL"}
    return {"main": f"{_round(val / 38.67, 2)} mmol/L"}


def triglyceride_convert(val, direction):
    """甘油三酯换算 mmol/L ↔ mg/dL"""
    if not val:
        return None
    val = float(val)
    if direction == "to_mg":
        return {"main": f"{_round(val * 88.57, 1)} mg/dL"}
    return {"main": f"{_round(val / 88.57, 2)} mmol/L"}


def pressure_convert(val, direction):
    """血压换算 mmHg ↔ kPa"""
    if not val:
        return None
    val = float(val)
    if direction == "to_kpa":
        return {"main": f"{_round(val * 0.1333, 1)} kPa"}
    return {"main": f"{_round(val / 0.1333, 1)} mmHg"}


def temperature_convert(val, direction):
    """体温换算 °C ↔ °F"""
    if not val:
        return None
    val = float(val)
    if direction == "to_f":
        return {"main": f"{_round(val * 9/5 + 32, 1)} °F"}
    return {"main": f"{_round((val - 32) * 5/9, 1)} °C"}
