# 使用示例

## 单平台上传（默认配置）

### TikTok
```bash
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"
```

### TikTok（带封面图）
```bash
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅" --cover "/Users/xxx/cover.jpg"
```

### Instagram
```bash
.venv/bin/social-upload instagram --video "/Users/xxx/vlog.mp4" --caption "周末探店 🍜 #美食 #vlog"
```

### YouTube
```bash
.venv/bin/social-upload youtube --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"
```

## 定时发布和可见性（--schedule / --visibility）

### TikTok 定时发布
```bash
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅" --schedule "2026-04-10 15:00"
```

### TikTok 好友可见 + 定时发布
```bash
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅" --schedule "2026-04-10 15:00" --visibility friends
```

### YouTube 定时发布
```bash
.venv/bin/social-upload youtube --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅" --schedule "2026-04-10 15:00"
```

### YouTube 不公开列出
```bash
.venv/bin/social-upload youtube --video "/Users/xxx/draft.mp4" --title "草稿" --description "测试用" --visibility unlisted
```

### YouTube 私享模式
```bash
.venv/bin/social-upload youtube --video "/Users/xxx/draft.mp4" --title "草稿" --description "测试用" --visibility private
```

## 使用自定义配置（--profile，用于复杂配置）

### YouTube 面向儿童 + 加标签

先创建配置文件 `kids.json`：
```json
{
  "youtube": {
    "made_for_kids": true,
    "tags": "玩具,开箱,评测"
  }
}
```

然后上传（可同时使用 --visibility 和 --profile）：
```bash
.venv/bin/social-upload youtube --video "/Users/xxx/toy_review.mp4" --title "玩具开箱" --description "今天开箱的是..." --visibility unlisted --profile kids.json
```

### TikTok AI 生成标记 + 内容披露

```json
{
  "tiktok": {
    "ai_generated": true,
    "disclose_content": true
  }
}
```

```bash
.venv/bin/social-upload tiktok --video "/Users/xxx/ai_video.mp4" --title "AI 创作" --description "AI 生成的内容" --schedule "2026-04-10 10:00" --profile ai_config.json
```

## 仅填表单不发布

```bash
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "测试" --description "测试描述" --no-publish
```

## 从断点恢复（AI 自动修复时使用）

```bash
.venv/bin/social-upload youtube --video "/Users/xxx/vlog.mp4" --title "标题" --description "描述" --resume-from publish
```

## 切换账号后重启浏览器

```bash
# 终止旧的调试浏览器，然后用新账号重新启动
.venv/bin/social-upload restart-browser

# 重新启动调试浏览器（macOS）
bash scripts/start_chrome_debug.sh

# 重新启动调试浏览器（Windows）
scripts\start_chrome_debug.bat
```

## 全平台依次上传

依次执行三个命令，每个完成后汇报结果再执行下一个：

```bash
# 1. TikTok
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"

# 2. Instagram
.venv/bin/social-upload instagram --video "/Users/xxx/vlog.mp4" --caption "周末探店 🍜 记录周末的美食之旅"

# 3. YouTube
.venv/bin/social-upload youtube --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"
```
