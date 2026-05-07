// 临床查房 Edge Function — 支持 GET 和 MCP JSON-RPC
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const ANON_KEY = "sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW";

const REFS: Record<string, { label: string; lo: number; hi: number; unit: string }> = {
  bp_sys: { label: "收缩压", lo: 90, hi: 140, unit: "mmHg" },
  bp_dia: { label: "舒张压", lo: 60, hi: 90, unit: "mmHg" },
  hr: { label: "心率", lo: 60, hi: 100, unit: "bpm" },
  spo2: { label: "SpO₂", lo: 95, hi: 100, unit: "%" },
  rr: { label: "RR", lo: 12, hi: 20, unit: "bpm" },
  temp: { label: "体温", lo: 36.0, hi: 37.3, unit: "°C" },
  abg_ph: { label: "pH", lo: 7.35, hi: 7.45, unit: "" },
  abg_pao2: { label: "PaO₂", lo: 80, hi: 100, unit: "mmHg" },
  abg_lac: { label: "乳酸", lo: 0, hi: 2, unit: "mmol/L" },
  wbc: { label: "WBC", lo: 4, hi: 10, unit: "×10⁹/L" },
  pct: { label: "PCT", lo: 0, hi: 0.5, unit: "ng/mL" },
  ionized_ca: { label: "离子钙", lo: 1.15, hi: 1.30, unit: "mmol/L" },
  d_dimer: { label: "D-二聚体", lo: 0, hi: 500, unit: "ng/mL" },
};

function calcPostopDay(s: string | null): number | null {
  if (!s) return null;
  return Math.floor((Date.now() - new Date(s).getTime()) / 86400000);
}

async function getData(supabase: any) {
  const { data: patients } = await supabase.from("patients").select("*").order("created_at");
  const today = new Date().toISOString().slice(0, 10);
  const { data: cards } = await supabase.from("daily_cards").select("*").eq("data_date", today);
  const cardMap: Record<string, any> = {};
  if (cards) cards.forEach((c: any) => (cardMap[c.patient_id] = c));
  return { patients: patients || [], cardMap };
}

// ─── 工具函数 ───
function getPatientList(patients: any[]): string {
  const sorted = [...patients].sort((a, b) => {
    const an = parseInt(a.bed_number), bn = parseInt(b.bed_number);
    if (!isNaN(an) && !isNaN(bn)) return an - bn;
    return (a.bed_number || "").localeCompare(b.bed_number || "");
  });
  const lines = ["**管床患者列表**\n"];
  for (const p of sorted) {
    const pod = calcPostopDay(p.surgery_date);
    lines.push(`- **${p.bed_number || "?"}床**: ${p.name_abbr} | ${p.age}岁 | ${p.primary_diagnosis?.slice(0, 20) || ""} | ${pod != null ? "术后D" + pod : ""}`);
  }
  return lines.join("\n");
}

function getRoundByBed(patients: any[], cardMap: any, bed: string): string {
  const p = patients.find((x: any) => x.bed_number === bed);
  if (!p) return `未找到 ${bed} 床患者`;
  const card = cardMap[p.id] || {};
  const pod = calcPostopDay(p.surgery_date);
  const sys = card?.bp_sys, dia = card?.bp_dia;
  const vitals: string[] = [];
  if (sys && dia) vitals.push(`BP ${sys}/${dia} mmHg`);
  if (card?.hr != null) vitals.push(`HR ${card.hr} bpm`);
  if (card?.spo2 != null) vitals.push(`SpO₂ ${card.spo2}%`);
  if (card?.temp != null) vitals.push(`体温 ${card.temp}°C`);
  const lines = [
    `## ${bed}床 | ${p.name_abbr} | ${p.age}岁 | ${pod != null ? "术后D" + pod : ""}`,
    `诊断: ${p.primary_diagnosis || "未填写"}`,
    vitals.join(" | "),
  ];
  const flags: string[] = [];
  if (card) {
    for (const [key, ref] of Object.entries(REFS)) {
      const v = card[key];
      if (v == null || v === "" || v === "正常") continue;
      const n = Number(v);
      if (isNaN(n)) continue;
      if (n > ref.hi) flags.push(`${ref.label} ↑${n}`);
      else if (n < ref.lo) flags.push(`${ref.label} ↓${n}`);
    }
  }
  if (flags.length) { lines.push(""); lines.push("⚠️ " + flags.join(" | ")); }
  const tx = card?.treatment_plan;
  if (tx) { lines.push(""); lines.push(`💊 ${tx}`); }
  return lines.join("\n");
}

function getRoundsAll(patients: any[], cardMap: any): string {
  return patients.map(p => getRoundByBed(patients, cardMap, p.bed_number || "")).join("\n\n---\n\n");
}

function getAbnormalFlags(patients: any[], cardMap: any): string {
  const flags: string[] = [];
  for (const p of patients) {
    const card = cardMap[p.id];
    if (!card) continue;
    for (const [key, ref] of Object.entries(REFS)) {
      const v = card[key];
      if (v == null || v === "" || v === "正常") continue;
      const n = Number(v);
      if (isNaN(n)) continue;
      if (n > ref.hi) flags.push(`- **${p.bed_number || "?"}床 ${p.name_abbr}**: ${ref.label}=${n} ↑`);
      else if (n < ref.lo) flags.push(`- **${p.bed_number || "?"}床 ${p.name_abbr}**: ${ref.label}=${n} ↓`);
    }
  }
  return flags.length ? "**异常值汇总**\n\n" + flags.join("\n") : "✅ 所有指标正常";
}

// ─── MCP 工具定义 ───
const ANNOTATIONS = { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: false };
const TOOLS = [
  { ...ANNOTATIONS, name: "get_patient_list", description: "列出所有管床患者（床号、姓名、诊断、术后天数）",
    inputSchema: { type: "object", properties: {} } },
  { ...ANNOTATIONS, name: "get_rounds_by_bed", description: "返回指定床号患者的完整查房汇报",
    inputSchema: { type: "object", properties: { bed: { type: "string", description: "床号" } }, required: ["bed"] } },
  { ...ANNOTATIONS, name: "get_rounds_all", description: "返回所有患者的查房汇报",
    inputSchema: { type: "object", properties: {} } },
  { ...ANNOTATIONS, name: "get_abnormal_flags", description: "列出所有患者当前偏离正常范围的指标",
    inputSchema: { type: "object", properties: {} } },
];

// ─── 入口 ───
Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  const apiKey = req.headers.get("x-api-key") || "";
  const sessionId = "mcp-session";
  const jsonHeaders: Record<string, string> = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "content-type, x-api-key, mcp-session-id",
    "Access-Control-Expose-Headers": "mcp-session-id",
    "Mcp-Session-Id": sessionId,
  };

  // ─── CORS preflight ───
  if (req.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: jsonHeaders });
  }

  // ─── GET: MCP 服务器发现（不需要 auth） ───
  if (req.method === "GET") {
    const action = url.searchParams.get("action") || "";
    if (action) {
      if (apiKey !== ANON_KEY) return new Response("Unauthorized", { status: 401 });
      const supabase = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!);
      const { patients, cardMap } = await getData(supabase);
      let result = "";
      const bed = url.searchParams.get("bed") || "";
      if (action === "patient_list") result = getPatientList(patients);
      else if (action === "rounds_by_bed" && bed) result = getRoundByBed(patients, cardMap, bed);
      else if (action === "rounds_all") result = getRoundsAll(patients, cardMap);
      else if (action === "abnormal_flags") result = getAbnormalFlags(patients, cardMap);
      else result = "actions: patient_list | rounds_by_bed&bed=N | rounds_all | abnormal_flags";
      return new Response(result, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
    }
    return new Response(JSON.stringify({
      protocolVersion: "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "clinical-rounds", version: "1.0" },
    }), { headers: jsonHeaders });
  }

  // ─── POST: MCP JSON-RPC ───
  if (apiKey !== ANON_KEY) {
    return new Response(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32001, message: "Unauthorized: add x-api-key header" } }), { status: 401,
      headers: jsonHeaders });
  }

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
  );

  if (req.method === "POST") {
    const body = await req.json();
    const { method, id, params } = body;
    const { patients, cardMap } = await getData(supabase);

    if (method === "initialize") {
      return new Response(JSON.stringify({
        jsonrpc: "2.0", id,
        result: { protocolVersion: "2024-11-05", capabilities: { tools: {} }, serverInfo: { name: "clinical-rounds", version: "1.0" } },
      }), { headers: jsonHeaders });
    }

    if (method === "notifications/initialized") {
      return new Response(null, { status: 204, headers: jsonHeaders });
    }

    if (method?.startsWith("notifications/")) {
      return new Response(null, { status: 204, headers: jsonHeaders });
    }

    if (method === "ping") {
      return new Response(JSON.stringify({ jsonrpc: "2.0", id, result: {} }),
        { headers: jsonHeaders });
    }

    if (method === "resources/list") {
      return new Response(JSON.stringify({ jsonrpc: "2.0", id, result: { resources: [] } }),
        { headers: jsonHeaders });
    }

    if (method === "prompts/list") {
      return new Response(JSON.stringify({ jsonrpc: "2.0", id, result: { prompts: [] } }),
        { headers: jsonHeaders });
    }

    if (method === "tools/list") {
      return new Response(JSON.stringify({ jsonrpc: "2.0", id, result: { tools: TOOLS } }),
        { headers: jsonHeaders });
    }

    if (method === "tools/call") {
      const name = params?.name;
      const args = params?.arguments || {};
      let text = "";
      if (name === "get_patient_list") text = getPatientList(patients);
      else if (name === "get_rounds_by_bed") text = getRoundByBed(patients, cardMap, args.bed || "");
      else if (name === "get_rounds_all") text = getRoundsAll(patients, cardMap);
      else if (name === "get_abnormal_flags") text = getAbnormalFlags(patients, cardMap);
      else text = `Unknown tool: ${name}`;
      return new Response(JSON.stringify({
        jsonrpc: "2.0", id,
        result: { content: [{ type: "text", text }] },
      }), { headers: jsonHeaders });
    }

    return new Response(JSON.stringify({ jsonrpc: "2.0", id: id ?? null, error: { code: -32601, message: `Unknown: ${method}` } }),
      { headers: jsonHeaders });
  }

  return new Response(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code: -32000, message: "Use POST with JSON-RPC" } }), { headers: jsonHeaders });
});
