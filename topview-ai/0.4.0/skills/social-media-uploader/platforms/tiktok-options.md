# TikTok 上传配置项

AI 读取本文件后，根据"已实现"部分向用户收集信息。

## CLI 必填参数（必须收集）

| 参数 | 说明 | 收集方式 | 限制 |
|------|------|---------|------|
| `--video` | 视频文件路径 | 对话问 | mp4/mov/avi/mkv/webm/flv/wmv/3gp |
| `--title` | 视频标题 | 对话问，用户没给则从文件名提取 | 无硬限制 |
| `--description` | 视频描述 | 对话问，用户没给则复用 title | ≤3900 字符 |

## 已实现的 profile 配置项（可以问用户）

### 可见性 `tiktok.visibility`

- **收集方式**：AskQuestion（仅用户主动提及时）
- **默认值**：`"everyone"`
- **用户没提就用默认，不主动问**

AskQuestion 模板：
```json
{
  "id": "tiktok_visibility",
  "prompt": "谁可以观看这个视频？",
  "options": [
    { "id": "everyone", "label": "所有人（默认）" },
    { "id": "friends", "label": "好友" },
    { "id": "only_me", "label": "仅自己" }
  ]
}
```

映射：直接用 option id 作为 `"visibility"` 的值。

### 定时发布 `tiktok.schedule`

- **收集方式**：对话问
- **默认值**：`null`（立即发布）
- **用户没提就用默认，不主动问**
- **格式**：`"YYYY-MM-DD HH:MM"`，如 `"2026-04-08 10:00"`

### 允许评论 `tiktok.allow_comments`

- **收集方式**：AskQuestion（仅用户主动提及时）
- **默认值**：`true`
- **用户没提就用默认，不主动问**

### 允许二创 `tiktok.allow_reuse`

- **收集方式**：AskQuestion（仅用户主动提及时）
- **默认值**：`true`
- **用户没提就用默认，不主动问**

### 内容披露 `tiktok.disclose_content`

- **收集方式**：AskQuestion（仅用户主动提及时）
- **默认值**：`false`
- **用户没提就用默认，不主动问**
- **说明**：开启后告知观众此帖推广品牌/产品/服务

### AI 生成标记 `tiktok.ai_generated`

- **收集方式**：AskQuestion（仅用户主动提及时）
- **默认值**：`false`
- **用户没提就用默认，不主动问**
- **重要**：如果视频是 AI 生成的，建议开启此标记以符合平台规范

AskQuestion 模板：
```json
{
  "id": "tiktok_ai_generated",
  "prompt": "是否标记为 AI 生成内容？",
  "options": [
    { "id": "no", "label": "否（默认）" },
    { "id": "yes", "label": "是，标记为 AI 生成" }
  ]
}
```

### 高画质上传 `tiktok.high_quality`

- **收集方式**：AskQuestion（仅用户主动提及时）
- **默认值**：`true`
- **用户没提就用默认，不主动问**

## CLI 可选参数

| 参数 | 说明 |
|------|------|
| `--cover` | 自定义封面图路径（jpg/png），不传则由平台自动截取 |
| `--no-publish` | 仅填表单不发布 |
| `--resume-from` | 从断点恢复 |
| `--profile` | 配置文件路径 |

## 封面图（通过 --cover 参数，不走 profile）

- **默认**：不传 `--cover`，由平台自动从视频中截取一帧作为封面
- **用户主动提供了封面图路径** → 加 `--cover "路径"`（支持 jpg/png）
- **不主动问用户**，遵循 SKILL.md Step 1.4 的"默认优先、绝不追问"原则

## 生成的 profile JSON 示例

用户说"上传到 TikTok，标记为 AI 生成，定时明天 10 点发"时生成：
```json
{
  "tiktok": {
    "ai_generated": true,
    "schedule": "2026-04-08 10:00"
  }
}
```

用户什么都没说（全用默认）时：不传 `--profile`，代码自动用 default.json。
