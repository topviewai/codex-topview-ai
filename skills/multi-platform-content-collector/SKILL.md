---
name: multi-platform-content-collector
description: "根据用户需求，从公开网页和社交平台收集结构化数据；适用于选题调研、竞品内容、创作者名单、评论反馈、AI 作品与提示词、趋势线索、链接清单等采集任务。触发词：采集、收集、调研、找数据、整理来源、多平台采集、content collector。"
---

# Multi-platform Content Collector

按用户需求收集数据，而不是只采集某一种固定内容。用户可以要求收集作品、账号、评论、链接、指标、提示词、案例、竞品内容、趋势素材、产品反馈等。Agent 需要先把需求转成清晰的数据字段，再跨平台搜索、筛选、验证、整理交付。

**文件路径**：本 skill 作为 TopView AI 插件的一部分，位于 `skills/multi-platform-content-collector/`。运行辅助脚本前，将 `SKILL_DIR` 指向本 skill 目录。

---

## 核心原则

1. **需求决定字段**：先理解用户要解决什么问题，再决定采集字段；不要默认只有 `prompt`。
2. **公开来源优先**：只采集公开可访问内容；需要登录的平台必须沿用用户已有登录状态，不索要密码。
3. **可追溯**：每条数据都必须保留来源链接、平台、作者/来源、发布时间或抓取时间。
4. **少问快做**：用户需求足够明确时直接开采；缺字段时做合理默认，并用一句话告知。
5. **不无限重试**：候选不足时最多换关键词重跑 1 次；仍不足就交付现有数据并说明原因。

---

## Step 0：解析采集任务

收到用户请求后，先解析 6 个参数，不要把任务锁死为 AI 视频或 prompt：

| 参数 | 默认值 | 示例 |
|---|---|---|
| 采集目标 | 用户话里最核心的对象 | `Sora 教程评论` / `AI 视频创作者` / `小红书竞品笔记` |
| 数据字段 | 按目标自动生成 | 平台、作者、链接、标题、指标、摘要、关键发现 |
| 关键词 | 从用户话中提取 | `seedance 2.0` / `跨境电商口播` / `TopView AI` |
| 平台 | 默认 YouTube + Reddit + Bilibili | 用户可指定 X、TikTok、小红书、微博等 |
| 数量 | 默认 20 条 | `采集 50 条` / `找 10 个账号` |
| 输出形式 | 默认表格/清单 | Markdown、CSV、JSONL、飞书表格 |

确认句模板：

> 我按「`<目标>`」采集，字段是 `<字段列表>`，平台 `<平台列表>`，目标 `<N>` 条，开始收集。

---

## 常用采集场景

### 1. 通用内容/链接采集

适合：找案例、素材、新闻、帖子、视频、评论、资料源。

推荐字段：
`platform`, `title`, `author`, `date`, `metric`, `url`, `summary`, `why_relevant`

### 2. 竞品/选题调研

适合：竞品视频、爆款内容、用户反馈、标题脚本、卖点角度。

推荐字段：
`platform`, `competitor`, `content_type`, `hook`, `topic`, `engagement`, `url`, `insight`

### 3. 创作者/账号名单

适合：找达人、频道、潜在合作对象、垂类作者。

推荐字段：
`platform`, `creator`, `profile_url`, `niche`, `sample_content`, `metric`, `contact_hint`, `reason`

### 4. 评论/反馈采集

适合：产品痛点、用户评价、常见问题、负面反馈。

推荐字段：
`platform`, `source`, `comment_or_quote`, `sentiment`, `pain_point`, `url`, `date`

### 5. AI 作品 + 提示词采集（保留为预设）

适合：用户明确要 “prompt / 提示词 / seedance / kling / sora 作品提示词”。

推荐字段：
`platform`, `author`, `date`, `likes`, `url`, `prompt`

此场景使用 `search_all.py --mode prompt`，并遵守：提示词必须原文记录，不改写、不翻译、不补全；没有公开 prompt 的内容跳过。

---

## 工作流程

```powershell
# 如果当前目录是插件根目录：
$env:SKILL_DIR = "skills\multi-platform-content-collector"
```

### Step 1：环境检查

```bash
opencli doctor
```

- YouTube / Reddit / Bilibili 通常可直接用。
- X / TikTok / 小红书 / 微博属于浏览器驱动平台：只有用户明确要求、且登录状态可用时才启用。
- 如果 Browser Bridge 离线或平台触发反爬，切换到非浏览器平台，并告诉用户跳过原因。

### Step 2：搜索候选

通用采集默认用 `--mode general`：

```bash
python "$env:SKILL_DIR\scripts\search_all.py" "<关键词>" `
  --mode general --target 20 --platforms youtube,reddit,bilibili
```

提示词采集预设用 `--mode prompt`：

```bash
python "$env:SKILL_DIR\scripts\search_all.py" "<关键词>" `
  --mode prompt --target 20 --platforms youtube,reddit,bilibili
```

常用参数：

| 参数 | 用途 |
|---|---|
| `--mode general` | 通用采集，不额外绑定 prompt 搜索后缀 |
| `--mode prompt` | AI 作品提示词采集，加入 prompt/提示词搜索后缀 |
| `--target N` | 目标条数 |
| `--platforms a,b,c` | 限定平台 |
| `--skip-browser` | 跳过 X/TikTok 等浏览器驱动平台 |
| `--budget-only` | 只预览调用预算，不实际搜索 |
| `--output PATH` | 自定义候选 JSONL 路径 |

候选默认写入 `/tmp/candidates.jsonl`，按互动指标从高到低排序。

### Step 3：验证与抽取

每次读取 5 条候选，逐条判断是否符合用户目标：

```bash
head -n 5 /tmp/candidates.jsonl
```

验证规则：

- 符合采集目标：保留并抽取字段。
- 不符合目标：跳过，不为了凑数硬收。
- 信息不足但方向相关：保留，`summary` 或 `note` 里标注不确定点。
- 字段无法获取：填 `N/A`，不要编造。

详情获取参考：

- 平台搜索和详情命令：`docs/platforms.md`
- 筛选判断方法：`docs/filtering.md`

保存通过验证的数据：

```bash
python "$env:SKILL_DIR\scripts\save_verified.py" --from-file /tmp/entry.json
```

`/tmp/entry.json` 可以是任意字段结构，例如：

```json
{
  "platform": "YouTube",
  "title": "Example title",
  "author": "Example creator",
  "date": "2026-05-07",
  "metric": "120K views",
  "url": "https://example.com",
  "summary": "为什么这条和用户需求相关",
  "insight": "可复用的发现"
}
```

提示词预设也可继续用旧参数：

```bash
python "$env:SKILL_DIR\scripts\save_verified.py" "<platform>" "<author>" "<date>" "<likes>" "<url>" "<prompt>"
```

### Step 4：整理输出

根据用户要求选择：

- 直接回复 Markdown 表格/清单。
- 写入 CSV/JSONL。
- 写入飞书表格：参考 `docs/feishu-write.md`。

飞书写入前，把 JSONL 转成用户需要的列顺序：

```bash
python - <<'PY'
import json
rows = []
with open('/tmp/collector_verified.jsonl', encoding='utf-8') as f:
    for line in f:
        d = json.loads(line)
        rows.append([
            d.get('platform', 'N/A'),
            d.get('title') or d.get('author') or d.get('source', 'N/A'),
            d.get('metric') or d.get('likes') or d.get('views') or 'N/A',
            d.get('url', 'N/A'),
            d.get('summary') or d.get('insight') or d.get('prompt') or ''
        ])
with open('/tmp/rows.json', 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False)
PY
```

### Step 5：交付说明

交付时说明：

- 实际收集条数与平台分布。
- 数据字段和输出位置。
- 未达到目标数量时的原因。
- 下一步可做的筛选、分析或补采方向。

---

## 辅助脚本

| 脚本 | 用途 |
|---|---|
| `scripts/search_all.py` | 多平台候选搜索、去重、按互动排序 |
| `scripts/save_verified.py` | 保存已验证条目，支持任意 JSON 字段 |
| `scripts/write_rows.py` | 逐行写入飞书表格，支持长文本、重试、断点续写 |
| `scripts/fetch_reddit_post.py` | 获取 Reddit 帖子完整内容 |
| `scripts/fetch_bilibili_video.py` | 获取 Bilibili 视频完整描述 |
| `scripts/ocr_frames.py` | 可选：视频截帧 OCR |

---

## 上限与安全

- 最多读取 `max(8, target)` 个候选批次，每批 5 条。
- 候选不足时最多换关键词重跑 1 次。
- Browser 平台出现 `Tripped: [twitter]` 或 `Tripped: [tiktok]` 后，不要立刻重复跑同平台。
- 不采集私密、绕权限、需要付费墙或用户未授权的内容。
- 不为凑字段而猜测数据；未知就写 `N/A`。
