# 临床查房

ICU 查房助手，直接调用 Supabase Edge Function 获取患者数据，按七维框架生成结构化汇报。

## 配置

在 RikkaHub 中配置 4 个自定义 HTTP 工具：

### 工具 1: 患者列表
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=patient_list`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

### 工具 2: 查某床
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=rounds_by_bed&bed={bed}`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`
- 参数: bed (床号数字)

### 工具 3: 全查
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=rounds_all`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

### 工具 4: 异常值
- URL: `https://raqukmcgcohmlshhkfym.supabase.co/functions/v1/clinical-rounds?action=abnormal_flags`
- 方法: GET
- Header: `Authorization: Bearer sb_publishable_g1XfDU9GH9z5zWiq3f4OBA_lUKaG0LW`

## 触发条件

| 输入 | 动作 | 调用工具 |
|------|------|---------|
| `患者列表` | 列出管床患者 | 工具1 |
| `查{数字}床` | 查指定床号 | 工具2 (bed={数字}) |
| `全查` | 查所有患者 | 工具3 |
| `异常值` | 异常指标汇总 | 工具4 |

## 工作流

1. 匹配用户输入，提取床号
2. 调用对应 HTTP 工具获取数据
3. 返回的文本直接展示

## 注意

- 请求必须带 Authorization 头
- 数据为只读，不会修改
- 七维框架：原发病→循环→呼吸→感染→脏器→营养→VTE
- 🔴偏高 🔵偏低 🚨危急值
