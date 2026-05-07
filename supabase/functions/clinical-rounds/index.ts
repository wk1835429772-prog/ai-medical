// 临床查房 Edge Function — 部署到 Supabase，替代本地 MCP 服务器
// 调用方式: https://<project>.supabase.co/functions/v1/clinical-rounds?action=xxx

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

// 参考范围（与 Python config.py 同步）
const REFERENCE_RANGES: Record<string, { label: string; lo: number; hi: number; unit: string }> = {
  bp_sys:    { label: "收缩压",     lo: 90,   hi: 140,  unit: "mmHg" },
  bp_dia:    { label: "舒张压",     lo: 60,   hi: 90,   unit: "mmHg" },
  hr:        { label: "心率",       lo: 60,   hi: 100,  unit: "bpm" },
  spo2:      { label: "SpO₂",      lo: 95,   hi: 100,  unit: "%" },
  rr:        { label: "RR",        lo: 12,   hi: 20,   unit: "bpm" },
  temp:      { label: "体温",       lo: 36.0, hi: 37.3, unit: "°C" },
  abg_ph:    { label: "pH",        lo: 7.35, hi: 7.45, unit: "" },
  abg_pao2:  { label: "PaO₂",     lo: 80,   hi: 100,  unit: "mmHg" },
  abg_paco2: { label: "PaCO₂",    lo: 35,   hi: 45,   unit: "mmHg" },
  abg_hco3:  { label: "HCO₃⁻",   lo: 22,   hi: 26,   unit: "mmol/L" },
  abg_lac:   { label: "乳酸",       lo: 0,    hi: 2,    unit: "mmol/L" },
  wbc:       { label: "WBC",       lo: 4,    hi: 10,   unit: "×10⁹/L" },
  neut_pct:  { label: "中性粒%",    lo: 50,   hi: 70,   unit: "%" },
  pct:       { label: "PCT",       lo: 0,    hi: 0.5,  unit: "ng/mL" },
  il6:       { label: "IL-6",      lo: 0,    hi: 7,    unit: "pg/mL" },
  bnp:       { label: "BNP",       lo: 0,    hi: 100,  unit: "pg/mL" },
  ionized_ca:{ label: "离子钙",     lo: 1.15, hi: 1.30, unit: "mmol/L" },
  albumin:   { label: "白蛋白",     lo: 35,   hi: 55,   unit: "g/L" },
  prealbumin:{ label: "前白蛋白",   lo: 200,  hi: 400,  unit: "mg/L" },
  d_dimer:   { label: "D-二聚体",   lo: 0,    hi: 500,  unit: "ng/mL" },
  vent_fio2: { label: "FiO₂",     lo: 21,   hi: 60,   unit: "%" },
  vent_peep: { label: "PEEP",      lo: 5,    hi: 10,   unit: "cmH₂O" },
};

const CRITICAL: Record<string, { hi?: number; lo?: number; label: string }> = {
  abg_lac:    { hi: 2,    label: "乳酸 >2 mmol/L" },
  ionized_ca: { lo: 1.15, label: "离子钙 <1.15 mmol/L" },
  abg_ph:     { lo: 7.25, hi: 7.55, label: "pH <7.25 或 >7.55" },
  d_dimer:    { hi: 3000, label: "D-二聚体 >3000 ng/mL" },
};

// ─── 工具函数 ───
function calcMAP(sys: number | null, dia: number | null): number | null {
  if (sys == null || dia == null) return null;
  return Math.round((sys + dia * 2) / 3);
}

function calcOI(pao2: number | null, fio2: number | null): number | null {
  if (pao2 == null || fio2 == null || fio2 <= 0) return null;
  const fio2dec = fio2 > 1 ? fio2 / 100 : fio2;
  return Math.round(pao2 / fio2dec);
}

function calcBalance(intake: number | null, output: number | null): number | null {
  if (intake == null || output == null) return null;
  return intake - output;
}

function calcPostopDay(surgeryDate: string | null): number | null {
  if (!surgeryDate) return null;
  const s = new Date(surgeryDate);
  const t = new Date();
  return Math.floor((t.getTime() - s.getTime()) / (1000 * 60 * 60 * 24));
}

function checkAbnormal(val: number | null, key: string): string {
  const ref = REFERENCE_RANGES[key];
  if (!ref || val == null) return "";
  if (val > ref.hi) return "🔴↑";
  if (val < ref.lo) return "🔵↓";
  return "";
}

function formatVal(val: any, key: string): string {
  if (val == null || val === "") return "";
  const ref = REFERENCE_RANGES[key];
  const label = ref?.label ?? key;
  const unit = ref?.unit ?? "";
  if (typeof val === "number") {
    const flag = checkAbnormal(val, key);
    return `${label}: ${val}${unit ? " " + unit : ""} ${flag}`.trim();
  }
  return `${label}: ${val}`;
}

// ─── 数据获取 ───
async function getData(supabase: any) {
  const { data: patients } = await supabase.from("patients").select("*").order("created_at");
  const today = new Date().toISOString().slice(0, 10);
  const { data: cards } = await supabase.from("daily_cards").select("*").eq("data_date", today);
  const cardMap: Record<string, any> = {};
  if (cards) cards.forEach((c: any) => (cardMap[c.patient_id] = c));
  return { patients: patients || [], cardMap };
}

// ─── 汇报生成 ───
function formatRounds(patient: any, card: any, bed: number): string {
  const pod = calcPostopDay(patient.surgery_date);
  let lines = [
    `## ${bed}床 | ${patient.name_abbr} | ${patient.age}岁`,
    `诊断: ${patient.primary_diagnosis || "未填写"}`,
    `术后: ${pod != null ? "D" + pod : "未填手术日期"}`,
    "",
    "### 生命体征",
  ];

  const sys = card?.bp_sys, dia = card?.bp_dia;
  const vitals = [];
  if (sys && dia) vitals.push(`BP ${sys}/${dia} mmHg`);
  if (card?.hr != null) vitals.push(`HR ${card.hr} bpm`);
  if (card?.spo2 != null) vitals.push(`SpO₂ ${card.spo2}%`);
  if (card?.temp != null) vitals.push(`体温 ${card.temp}°C`);
  if (card?.rr != null) vitals.push(`RR ${card.rr} bpm`);
  lines.push(vitals.join(" | ") || "未填写");

  const map = calcMAP(sys, dia);
  const bal = calcBalance(card?.intake_vol, card?.output_vol);
  const calcs = [];
  if (map != null) calcs.push(`MAP ${map} mmHg`);
  if (bal != null) calcs.push(`平衡 ${bal > 0 ? "+" : ""}${bal} mL`);
  if (calcs.length) lines.push(calcs.join(" | "));

  // 异常值
  const flags: string[] = [];
  if (card) {
    for (const [key, ref] of Object.entries(REFERENCE_RANGES)) {
      const v = card[key];
      if (v == null || v === "" || v === "正常") continue;
      const n = Number(v);
      if (isNaN(n)) continue;
      if (n > ref.hi) flags.push(`${ref.label} ↑${n}`);
      else if (n < ref.lo) flags.push(`${ref.label} ↓${n}`);
    }
    for (const [key, crit] of Object.entries(CRITICAL)) {
      const v = Number(card[key]);
      if (isNaN(v)) continue;
      if ((crit.hi && v > crit.hi) || (crit.lo && v < crit.lo)) {
        flags.push(`🚨 ${crit.label} | 当前: ${v}`);
      }
    }
  }

  if (flags.length) {
    lines.push("");
    lines.push("### ⚠️ 异常值");
    lines.push(...flags);
  }

  const treatment = card?.treatment_plan;
  if (treatment) {
    lines.push("");
    lines.push(`### 💊 治疗方案\n${treatment}`);
  }

  return lines.join("\n");
}

// ─── 入口 ───
Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  const action = url.searchParams.get("action") || "";
  const bed = url.searchParams.get("bed") || "";

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  const { patients, cardMap } = await getData(supabase);

  // 按床号查找
  function findByBed(bedNum: string) {
    return patients.find((p: any) => p.bed_number === bedNum) || null;
  }

  if (action === "patient_list") {
    const lines = ["**管床患者列表**\n"];
    const sorted = [...patients].sort((a: any, b: any) => {
      const an = parseInt(a.bed_number), bn = parseInt(b.bed_number);
      if (!isNaN(an) && !isNaN(bn)) return an - bn;
      return (a.bed_number || "").localeCompare(b.bed_number || "");
    });
    for (const p of sorted) {
      const bnum = p.bed_number || "?";
      const pod = calcPostopDay(p.surgery_date);
      lines.push(`- **${bnum}床**: ${p.name_abbr} | ${p.age}岁 | ${p.primary_diagnosis?.slice(0, 20) || ""} | ${pod != null ? "术后D" + pod : ""}`);
    }
    return new Response(lines.join("\n"), {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  if (action === "rounds_by_bed" && bed) {
    const patient = findByBed(bed);
    if (!patient) return new Response(`未找到 ${bed} 床患者`, { status: 404 });
    const card = cardMap[patient.id] || {};
    return new Response(formatRounds(patient, card, parseInt(bed) || 0), {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  if (action === "rounds_all") {
    const sections: string[] = [];
    const sorted = [...patients].sort((a: any, b: any) => {
      const an = parseInt(a.bed_number), bn = parseInt(b.bed_number);
      if (!isNaN(an) && !isNaN(bn)) return an - bn;
      return 0;
    });
    for (const p of sorted) {
      const card = cardMap[p.id] || {};
      const bnum = parseInt(p.bed_number) || 0;
      sections.push(formatRounds(p, card, bnum));
      sections.push("\n---\n");
    }
    return new Response(sections.join("\n"), {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  if (action === "abnormal_flags") {
    const flags: string[] = [];
    for (const p of patients) {
      const card = cardMap[p.id];
      if (!card) continue;
      const bnum = p.bed_number || "?";
      for (const [key, ref] of Object.entries(REFERENCE_RANGES)) {
        const v = card[key];
        if (v == null || v === "" || v === "正常") continue;
        const n = Number(v);
        if (isNaN(n)) continue;
        if (n > ref.hi) flags.push(`- **${bnum}床 ${p.name_abbr}**: ${ref.label} = ${n} 🔴↑`);
        else if (n < ref.lo) flags.push(`- **${bnum}床 ${p.name_abbr}**: ${ref.label} = ${n} 🔵↓`);
      }
    }
    return new Response(flags.length ? "**异常值汇总**\n\n" + flags.join("\n") : "✅ 所有指标正常", {
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }

  return new Response(
    "临床查房 API\n\n操作: patient_list / rounds_by_bed&bed=N / rounds_all / abnormal_flags",
    { headers: { "Content-Type": "text/plain; charset=utf-8" } }
  );
});
