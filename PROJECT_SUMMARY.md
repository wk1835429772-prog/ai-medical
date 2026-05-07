# 临床助手 — 项目完整总结

> 2026-05-08

## 项目概述

**临床助手** 是一个 ICU 查房辅助系统，包含两个核心能力：

| 模块 | 技术 | 用途 |
|------|------|------|
| 数据管理 | Streamlit Web App | 患者管理、七维日卡、历史趋势、AI 汇报 |
| 数据存储 | Supabase PostgreSQL | 云端持久化，App 休眠不丢数据 |
| 移动查房 | RikkaHub + MCP | 手机上一句话查房："查3床""全查""异常值" |
| AI 推理 | DeepSeek API | 今日汇报生成、AI 对话 |

## 架构图

```
┌──────────────┐   HTTP API    ┌──────────────────────┐
│  Streamlit   │──────────────▶│   Supabase PostgreSQL  │
│  Web App     │               │   (数据永久存储)        │
└──────────────┘               └──────────────────────┘
                                       ▲
┌──────────────┐   MCP JSON-RPC       │
│  RikkaHub    │──────────────────────┘
│  手机 App    │  Edge Function
│              │  clinical-rounds
└──────────────┘  (4 个查房工具)
```

## 技术栈

| 层 | 技术 | 说明 |
|----|------|------|
| 前端 | Streamlit 1.42 | Python-only，移动端 CSS 适配 |
| 数据库 | Supabase PostgreSQL | pg8000 纯 Python 驱动，连接池 |
| API | Supabase Edge Function | Deno/TypeScript，MCP JSON-RPC |
| AI | DeepSeek API | deepseek-v4-flash / pro |
| 移动端 | RikkaHub Android | MCP Streamable HTTP 接入 |

## MCP 服务器（今日重点）

### 架构

Supabase Edge Function `clinical-rounds` 作为 MCP 服务器，遵循 MCP Streamable HTTP 传输 + 无状态 JSON 模式。

**端点**: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds`

### 4 个查房工具

| 工具名 | 用户输入 | 参数 | 功能 |
|--------|---------|------|------|
| `get_patient_list` | `患者列表` | 无 | 列出所有患者（床号、姓名、诊断、术后天数） |
| `get_rounds_by_bed` | `查3床` | bed: "3" | 返回某床完整查房汇报 |
| `get_rounds_all` | `全查` | 无 | 返回所有患者查房汇报 |
| `get_abnormal_flags` | `异常值` | 无 | 列出异常/危急指标 |

### MCP 协议踩坑

| 问题 | 根因 | 解决 |
|------|------|------|
| Streamable HTTP 无法同步 | 缺少 CORS 头 | 加 `Access-Control-Allow-*` |
| `id` field required | 通知返回了无 `id` 的 JSON | 通知用 204 No Content |
| `inputSchema` required | RikkaHub Kotlin SDK 要求所有工具有 schema | 无参工具加空 `inputSchema` |
| SSE vs Streamable HTTP | 最初混用了 SSE transport | 改为纯 stateless JSON-RPC POST |
| Auth 头被重写 | Supabase 中间件替换 Authorization | 改用 `x-api-key` 自定义头 |
| `Mcp-Session-Id` 缺失 | 忘记加 session 头 | 加上 `Mcp-Session-Id` 头 |

### RikkaHub 配置

```
传输: Streamable HTTP
URL: https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds
Header: x-api-key = sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW
```

## 数据库迁移踩坑

| 问题 | 根因 | 解决 |
|------|------|------|
| 数据丢失 | Streamlit Cloud 文件系统临时 | 迁移到 Supabase |
| psycopg2 不兼容 | Python 3.14 无二进制 wheel | 换 pg8000（纯 Python） |
| 连接超时 | 直连 IPv6 不通 | 用 Shared Pooler（IPv4） |
| Cursor closed | commit 后复用 cursor | 每次 execute 新 cursor |
| row[0] 失效 | dict 的 list() 返回键名 | _Row 类支持整数索引 |
| COUNT(*) 类型错误 | pg8000 返回 dict | `list(row)[0]` 取值 |

## 患者管理

### 七维框架

每日评估按以下顺序组织：
1. **原发病** — 引流量、引流性状、伤口/皮瓣
2. **循环** — BP/HR/SpO₂、出入量、MAP
3. **呼吸/酸碱** — 血气分析、呼吸机参数、OI
4. **感染** — 体温、WBC、PCT、IL-6
5. **脏器** — 尿量、肾功能、凝血、电解质
6. **营养** — 营养途径、入量、白蛋白
7. **VTE** — 预防措施、D-二聚体

### 彩色标注

| 颜色 | 含义 |
|------|------|
| 🔴 红色 | 高于正常值 |
| 🔵 蓝色 | 低于正常值 |
| 🚨 | 危急值 |

## 关键文件

| 文件 | 定位 |
|------|------|
| `core/database.py` | 双后端数据库（SQLite + PostgreSQL） |
| `supabase/functions/clinical-rounds/index.ts` | MCP 服务器（Edge Function） |
| `models/patient.py` | 患者 CRUD（含 bed_number） |
| `models/daily_card.py` | 日卡 CRUD（50+ 字段） |
| `pages/2_daily_assessment.py` | 核心：每日评估页 |
| `pages/4_ai_chat.py` | AI 纯文本对话 |
| `mcp_server.py` | MCP 本地服务器（备选） |
| `rikkahub-skill/clinical-rounds/` | RikkaHub Skill 文件 |

## 部署地址

| 服务 | 地址 |
|------|------|
| Streamlit App | Streamlit Cloud 自动部署 |
| Supabase 数据库 | `raqukmcgcohmlshhkfym.supabase.co` |
| MCP 查房 API | `/functions/v1/clinical-rounds` |
| GitHub 仓库 | `wk1835429772-prog/ai-medical` |
