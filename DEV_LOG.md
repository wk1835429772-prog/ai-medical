# 临床助手 — 开发过程记录

> 供后续会话复习使用。记录核心架构、踩坑经历、关键决策。

---

## 1. 项目概述

**名称**：临床助手  
**版本**：v1.1.0  
**类型**：Streamlit 多页面 Web App（ICU 每日查房辅助）  
**部署**：Streamlit Cloud + Supabase PostgreSQL  
**使用场景**：手机浏览器为主（医生查房随身携带）

**功能模块**：
- 患者管理（增删改查）
- 每日评估（生命体征 + 七维临床数据 + 诊断/治疗方案）
- 历史趋势（颜色标注原始数据表，红=偏高，蓝=偏低）
- AI 对话（DeepSeek API，患者级对话持久化）
- 规则配置（黄金规则 + 参考范围 + API Key）

---

## 2. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Streamlit 1.42+ | Python-only，无前端代码 |
| 数据库（云端） | Supabase PostgreSQL | 通过 pg8000 连接 |
| 数据库（本地） | SQLite 3 | `data/app.db` |
| AI API | DeepSeek（OpenAI-compatible） | `deepseek-v4-flash` / `deepseek-v4-pro` |
| 部署平台 | Streamlit Cloud | 免费版，文件系统临时 |

---

## 3. 核心架构

### 3.1 双后端数据库

```
┌─────────────────────┐     ┌─────────────────┐
│  Streamlit Cloud    │────▶│  Supabase       │
│  （无状态，可重建）   │     │  PostgreSQL     │
└─────────────────────┘     │  （永久存储）    │
       ▲                    └─────────────────┘
       │ 自动检测 SUPABASE_URL
       │ 不存在时回退到 SQLite
       ▼
┌─────────────────────┐
│  本地开发            │
│  SQLite: data/app.db │
└─────────────────────┘
```

**关键代码**：`core/database.py`
- `USE_SUPABASE = bool(_get_supabase_url())` 自动检测后端
- `PgConnection` 包装类统一 pg8000 和 sqlite3 行为
- `_Row` 类同时支持 `row[0]`（整数索引）和 `row["col"]`（列名索引）
- `upsert_setting()` / `table_exists()` 兼容双后端

### 3.2 页面结构（按临床习惯排序）

```
1_patient_management.py   → 患者列表
2_daily_assessment.py     → 每日评估（核心页面）
3_history_trends.py       → 历史数据（颜色标注表）
4_ai_chat.py              → AI 对话（纯文本）
5_rules_config.py         → 设置（API/规则/参考范围）
6_toolbox.py              → 工具箱
```

**注意**：每个页面顶部必须调用 `init_database()`，因为 Streamlit Cloud 各页面独立运行。

### 3.3 每日评估页面布局

```
┌──────────────────────────────────────────┐
│ 患者选择 + 日期导航 + 保存按钮              │
├──────────────────────────────────────────┤
│ 📊 生命体征（可编辑 number_input）         │
│    收缩压 / 舒张压 → 内联 MAP              │
│    入量 / 出量 → 内联 平衡                │
├──────────────────────────────────────────┤
│ 🏥 当前诊断（textarea）                    │
├──────────────────────────────────────────┤
│ 📋 七维折叠卡片（原发病 → 循环 → 呼吸...） │
│    每个维度：结构化输入 + 自由文本备注      │
│    呼吸维度：PaO₂/FiO₂ → 内联 OI          │
├──────────────────────────────────────────┤
│ 💊 治疗方案（textarea）                    │
├──────────────────────────────────────────┤
│ 🤖 AI 汇报（右栏：生成今日汇报 / 交班报告）│
└──────────────────────────────────────────┘
```

### 3.4 数据自动保存机制

| 层级 | 机制 | 文件 |
|------|------|------|
| 云端 | Supabase PostgreSQL（主存储） | `core/database.py` |
| 本地备份 | 每次写操作后自动导出 JSON | `data/app.json` |
| 手动备份 | 设置页「导出数据」按钮 | `clinical_backup_*.json` |
| 导入恢复 | 设置页「导入数据」按钮 | `import_all_json()` |

---

## 4. 踩坑记录（核心经验）

### 4.1 Streamlit Cloud 文件系统临时

**现象**：App 休眠后 `data/app.db` 丢失  
**根因**：免费版容器销毁后文件系统重建  
**解决**：迁移到 Supabase PostgreSQL

### 4.2 连接字符串选择

**弯路**：
1. `db.xxx.supabase.co:5432` — 本地开发连不上（IPv6/网络限制）
2. `aws-0-*.pooler.supabase.com:6543` — 连接池，Streamlit Cloud 报 "Tenant not found"
3. **最终**：`aws-1-ap-northeast-1.pooler.supabase.com:6543` — Transaction Pooler，用户名格式 `postgres.project_id`

**教训**：Supabase 的 Connection String 有多个模式，必须选 **Transaction Pooler**（IPv4 兼容）。

### 4.3 PostgreSQL 驱动选择

| 驱动 | 结果 | 原因 |
|------|------|------|
| psycopg2-binary | ❌ | Python 3.14 二进制不兼容 |
| pg8000（legacy API） | ❌ | `tls` 参数不存在 |
| **pg8000.dbapi** | ✅ | 纯 Python，`ssl_context` 参数正确 |

### 4.4 连接复用导致的 Cursor Closed

**现象**：`_seed_default_rules()` 报 "Cursor closed"  
**根因**：`threading.local` 缓存连接后，一个函数 `commit`+`close` 会影响后续函数  
**弯路**：
1. 缓存连接 → cursor 复用报错
2. `_PgRef` 包装 → close 后重建 → 仍有竞态
3. **最终**：放弃连接缓存，每次 `get_connection()` 新建连接  
**代价**：每次操作慢 100-300ms（跨国网络），但稳定

### 4.5 行数据类型兼容

**现象**：`row[0]` 在 pg8000 返回 dict 时失效  
**根因**：sqlite3.Row 支持 `row[0]` 和 `row["col"]`，但 pg8000 返回 tuple，包装成 dict 后 `list(dict)[0]` 返回的是键名不是值  
**解决**：自定义 `_Row(dict)` 类，重写 `__getitem__` 支持整数索引

### 4.6 `?_placeholder` 替换陷阱

**现象**：SQL 中的 `LIKE 'ref_%'` 被误处理  
**原因**：`?` → `%s` 全局替换可能影响字符串字面量  
**结果**：此项目的 LIKE 模式恰好不含 `?`，未触发问题  
**风险**：未来如果有含 `?` 的字符串字面量，需要用正则做参数绑定替换

### 4.7 Streamlit 各页面状态隔离

**现象**：直接访问子页面时报 SQLite 错误  
**根因**：`init_database()` 只在 `app.py` 调用，Streamlit Cloud 各页面独立启动  
**解决**：每个 `pages/*.py` 顶部都加 `from core.database import init_database; init_database()`

### 4.8 AI Chat `st.chat_input` 重复消息

**现象**：SQLite IntegrityError 重复插入  
**根因**：`st.chat_input` 的返回值在 rerun 时不清空  
**解决**：session_state 维护已处理消息指纹集合 `_ai_processed_prompts`

---

## 5. 最终部署信息

| 项目 | 值 |
|------|-----|
| GitHub | `wk1835429772-prog/ai-medical` (master) |
| Streamlit Cloud | 自动跟随 master 部署 |
| Supabase | `raqukmcgcohmlshhkfym.supabase.co` (ap-northeast-1) |
| API | DeepSeek v4 (`deepseek-v4-flash` / `deepseek-v4-pro`) |
| Python | 3.12（`runtime.txt` 固定） |

**Streamlit Cloud Secrets**：
```toml
SUPABASE_URL = "postgresql://postgres.raqukmcgcohmlshhkfym:[PASSWORD]@aws-1-ap-northeast-1.pooler.supabase.com:6543/postgres"
```

---

## 6. 关键文件清单

| 文件 | 用途 | 改动频率 |
|------|------|---------|
| `core/database.py` | 双后端数据库连接 + 表初始化 | 高 |
| `models/patient.py` | 患者 CRUD | 低 |
| `models/daily_card.py` | 日卡 CRUD（50+ 字段） | 中 |
| `models/chat_message.py` | AI 对话 CRUD | 低 |
| `core/deepseek_client.py` | DeepSeek API 流式客户端 | 低 |
| `config.py` | 全局常量 + 七维框架 + 参考范围 | 中 |
| `pages/2_daily_assessment.py` | 核心每日评估页 | 高 |
| `pages/3_history_trends.py` | 历史数据 + 颜色标注 | 中 |
| `pages/4_ai_chat.py` | AI 纯文本对话 | 中 |
| `pages/5_rules_config.py` | 设置 + 数据管理 | 中 |
| `core/ui_style.py` | 全局 CSS + 移动端适配 | 低 |
| `requirements.txt` | Python 依赖 | 中 |

---

## 7. 常用操作

### 本地运行
```bash
cd "c:\Users\wk2001\Desktop\ai medical"
streamlit run app.py
```

### 部署
```bash
git add [files]
git commit -m "message"
git push origin master
# Streamlit Cloud 自动部署，1-2 分钟后生效
```

### 降级调试（不要用 Supabase）
删除 Streamlit Cloud Secrets 中的 `SUPABASE_URL`，App 自动回退本地 SQLite。

### 数据恢复
设置页 → 上传之前导出的 JSON 文件 → 自动导入到当前数据库。

---

## 8. 未来可扩展方向

- PWA 配置（manifest.json + service worker）— 手机添加桌面快捷方式
- 语音输入（曾有实现，因 bug 回退）— 可重新启用
- 局域网自托管（pyinstaller 打包 .exe）— 适合没网络的场景
- 多用户/登录系统 — 需要引入认证

---

> 最后更新：2026-05-07
> 核心教训：Supabase 连接用 Transaction Pooler + pg8000.dbapi；不要在跨 commit 复用 cursor；保持连接无状态比缓存更可靠。
