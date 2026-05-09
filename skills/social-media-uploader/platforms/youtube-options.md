# YouTube 上传配置项

AI 读取本文件后，根据"已实现"部分向用户收集信息、生成 profile JSON。

## CLI 必填参数（必须收集）

| 参数 | 说明 | 收集方式 | 限制 |
|------|------|---------|------|
| `--video` | 视频文件路径 | 对话问 | mp4/mov/avi/mkv/webm/flv/wmv/3gp |
| `--title` | 视频标题 | 对话问，用户没给则从文件名提取 | ≤95 字符 |
| `--description` | 视频描述 | 对话问，用户没给则复用 title | ≤4900 字符 |

## 已实现的 profile 配置项（可以问用户）

### 面向儿童 `youtube.made_for_kids`

- **收集方式**：AskQuestion
- **默认值**：`false`（不面向儿童）
- **用户没提就用默认，不主动问**

AskQuestion 模板：
```json
{
  "id": "youtube_kids",
  "prompt": "这个视频是面向儿童的内容吗？",
  "options": [
    { "id": "no", "label": "不是（默认）" },
    { "id": "yes", "label": "是，面向儿童" }
  ]
}
```

映射：`yes` → `"made_for_kids": true`，`no` → `"made_for_kids": false`

### 可见性 `youtube.visibility`

- **收集方式**：AskQuestion
- **默认值**：`"public"`
- **用户没提就用默认，不主动问**

AskQuestion 模板：
```json
{
  "id": "youtube_visibility",
  "prompt": "视频可见性设置？",
  "options": [
    { "id": "public", "label": "公开（所有人可见，默认）" },
    { "id": "unlisted", "label": "不公开列出（有链接才能看）" },
    { "id": "private", "label": "私享（仅自己可见）" }
  ]
}
```

映射：直接用 option id 作为 `"visibility"` 的值。

### 标签 `youtube.tags`

- **收集方式**：对话问
- **默认值**：`null`（不设置标签）
- **用户没提就用默认，不主动问**
- **格式**：逗号分隔的字符串，如 `"旅行,vlog,美食"`

### 分类 `youtube.category`

- **收集方式**：对话问
- **默认值**：`null`（不设置分类）
- **用户没提就用默认，不主动问**
- **可选值**：Entertainment, Education, Science & Technology, People & Blogs, Music, Gaming 等

## CLI 可选参数

| 参数 | 说明 |
|------|------|
| `--no-publish` | 仅填表单不发布，用户说"预览""不发布"时加上 |
| `--resume-from` | 从断点恢复，AI 自动修复时使用，不需要问用户 |
| `--profile` | 配置文件路径，AI 生成后自动传入 |

## 生成的 profile JSON 示例

用户说"上传到 YouTube，面向儿童，不公开，加标签旅行和美食"时生成：
```json
{
  "youtube": {
    "made_for_kids": true,
    "visibility": "unlisted",
    "tags": "旅行,美食"
  }
}
```

用户说"上传到 YouTube，明天上午10点定时发布"时生成：
```json
{
  "youtube": {
    "schedule": "2026-04-08 10:00"
  }
}
```

用户什么都没说（全用默认）时：不传 `--profile`，代码自动用 default.json。

### 定时发布 `youtube.schedule`

- **收集方式**：对话问
- **默认值**：`null`（立即发布）
- **用户没提就用默认，不主动问**
- **格式**：`"YYYY-MM-DD HH:MM"`，如 `"2026-04-08 10:00"`
- **前置条件**：定时发布会自动将可见性设为 PUBLIC（公开）
- **安全门控**：如果定时设置失败，脚本会中止发布，防止视频立即公开

AskQuestion 模板（仅用户主动提及定时发布时使用）：
```json
{
  "id": "youtube_schedule",
  "prompt": "YouTube 定时发布时间？",
  "options": [
    { "id": "now", "label": "立即发布（默认）" },
    { "id": "custom", "label": "指定时间（请在对话中补充 YYYY-MM-DD HH:MM）" }
  ]
}
```

映射：`now` → 不设 schedule，`custom` → `"schedule": "用户给出的时间"`

## 规划中（代码暂未实现，不要问用户）

以下功能在 default.json 中没有对应字段，代码也没有处理逻辑。
**AI 不得就这些选项向用户提问或生成配置。** 如果用户主动提到，应回复"此功能暂未实现"。

- `playlist` — 播放列表
- `license` — 授权类型
