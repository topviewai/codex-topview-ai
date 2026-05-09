# Instagram 上传配置项

AI 读取本文件后，根据"已实现"部分向用户收集信息。

## CLI 必填参数（必须收集）

| 参数 | 说明 | 收集方式 | 限制 |
|------|------|---------|------|
| `--video` | 视频文件路径 | 对话问 | mp4/mov/avi/mkv/webm/flv/wmv/3gp |
| `--caption` | 发布文案 | 对话问，用户没给则从文件名提取 | ≤2200 字符 |

注意：Instagram 没有单独的 `--title` 和 `--description`，只有 `--caption`。
如果用户提供了 title 和 description，AI 应拼接为 `title + "\n\n" + description` 作为 caption。

## 已实现的 profile 配置项（可以问用户）

### 同步到动态流 `instagram.share_to_feed`

- **收集方式**：AskQuestion（仅用户主动提及时）
- **默认值**：`true`（同步到动态流）
- **用户没提就用默认，不主动问**

AskQuestion 模板：
```json
{
  "id": "instagram_share_to_feed",
  "prompt": "是否同步到动态流？",
  "options": [
    { "id": "yes", "label": "是（默认）" },
    { "id": "no", "label": "否，仅作为 Reel 发布" }
  ]
}
```

映射：`yes` → `"share_to_feed": true`，`no` → `"share_to_feed": false`

## CLI 可选参数

| 参数 | 说明 |
|------|------|
| `--no-publish` | 仅填表单不发布 |
| `--resume-from` | 从断点恢复 |
| `--profile` | 配置文件路径 |

## 生成的 profile JSON 示例

用户说"上传到 Instagram，不同步到动态"时生成：
```json
{
  "instagram": {
    "share_to_feed": false
  }
}
```

用户什么都没说（全用默认）时：不传 `--profile`，代码自动用 default.json。

## 不支持的功能

- `schedule` — **定时发布：Instagram 网页版不支持定时发布功能。** 如果用户要求 Instagram 定时发布，应明确告知"Instagram 网页版不支持定时发布，视频将立即发布"。此为平台限制，非本工具问题。

## 规划中（代码暂未实现，不要问用户）

- `location` — 地理位置标记
