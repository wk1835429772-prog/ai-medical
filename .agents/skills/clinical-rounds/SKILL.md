---
name: clinical-rounds
description: ICU clinical rounds assistant. Get patient data by bed number and generate structured reports.
---

# 临床查房

ICU 查房助手，调用 Supabase Edge Function 获取患者数据，按七维框架生成结构化汇报。

## 配置

在 RikkaHub 中添加 4 个自定义 HTTP 工具：

### 工具: 患者列表
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=patient_list`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

### 工具: 查某床
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=rounds_by_bed&bed={bed}`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

### 工具: 全查
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=rounds_all`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

### 工具: 异常值
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=abnormal_flags`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

## 触发条件

| 输入 | 动作 | 调用工具 |
|------|------|---------|
| `患者列表` | 列出管床患者 | 患者列表 |
| `查{数字}床` | 查指定床号 | 查某床 (bed={数字}) |
| `全查` | 查所有患者 | 全查 |
| `异常值` | 异常指标汇总 | 异常值 |

## 工作流

1. 匹配用户输入，提取床号
2. 调用对应 HTTP 工具获取数据
3. 返回的文本直接展示

## 汇报模板

汇报按七维框架组织：原发病→循环→呼吸→感染→脏器→营养→VTE
异常值标注：🔴偏高 🔵偏低 🚨危急值
