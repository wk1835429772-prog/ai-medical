# 临床查房

ICU 查房助手，通过 Supabase Edge Function 获取患者数据，按七维框架生成结构化汇报。

## API 端点

`https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds`

请求头：`Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

## 触发条件

| 输入 | 动作 | API 调用 |
|------|------|---------|
| `患者列表` | 列出管床患者 | `?action=patient_list` |
| `查{数字}床` | 查指定床号 | `?action=rounds_by_bed&bed={数字}` |
| `全查` | 查所有患者 | `?action=rounds_all` |
| `异常值` | 异常指标汇总 | `?action=abnormal_flags` |

## 工作流

1. 匹配用户输入，提取床号
2. 调用对应 API 端点（HTTP GET）
3. 返回的文本直接展示给用户

## 七维框架参考

1. **原发病** — 引流量、引流性状、伤口评估
2. **循环** — BP/HR/SpO₂、出入量平衡、MAP
3. **呼吸/酸碱** — 血气分析、呼吸机参数、OI
4. **感染** — 体温、WBC、PCT、IL-6
5. **脏器** — 尿量、肾功能、凝血、电解质
6. **营养** — 营养途径、入量、白蛋白
7. **VTE** — 预防措施、D-二聚体

## 颜色标注

- 🔴↑ 偏高
- 🔵↓ 偏低
- 🚨 危急值
