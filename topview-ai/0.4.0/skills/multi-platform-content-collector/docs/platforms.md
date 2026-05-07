# 平台搜索配置

本文件是 `search_all.py` 的平台搜索参考。脚本负责候选搜索、去重和排序；Agent 在验证阶段按需读取详情。

---

## 搜索模式

| 模式 | 用途 |
|---|---|
| `--mode general` | 通用采集：按用户关键词搜索，不绑定 prompt 后缀 |
| `--mode prompt` | AI 作品提示词采集：额外搜索 `prompt` / `提示词` 等后缀 |

`search_all.py` 会把用户关键词展开成常见变体，例如 `seedance 2.0` 会扩展为 `seedance 2.0 / seedance2 / seedance2.0 / seedance 2 / Seedance / seedance`。

---

## 候选排序

搜索完成后按互动指标从高到低排序：

| 平台 | 排序字段 |
|---|---|
| X/Twitter | `likes` |
| TikTok | `likes` |
| YouTube | `views` |
| Reddit | `score` |
| Bilibili | `score` |

这些指标只是优先级，不等于是否合格；最终是否录入仍按用户目标验证。

---

## X / Twitter

需要 Browser Bridge + 登录 x.com。用户明确要求 X/Twitter 时才启用。

返回字段：`id`, `author`, `text`, `created_at`, `likes`, `views`, `url`

详情获取：

```bash
opencli twitter thread "<tweet-id>" -f json
```

适合：热点讨论、创作者观点、作品发布、短文本反馈、链接线索。

---

## TikTok

需要 Browser Bridge + 登录 tiktok.com。用户明确要求 TikTok 时才启用。

返回字段：`desc`, `author`, `url`, `plays`, `likes`

注意：TikTok 每次搜索会刷新浏览器页面，速度较慢；目标少量时建议单独跑。

适合：爆款短视频、口播脚本、创作者样本、评论/趋势线索。

---

## YouTube

返回字段：`title`, `channel`, `views`, `duration`, `published`, `url`

详情获取：

```bash
opencli youtube video "<url>" -f json
opencli youtube transcript "<url>" -f json
```

适合：长视频案例、频道/创作者、教程内容、评论反馈、字幕信息。

---

## Reddit

返回字段：`title`, `subreddit`, `author`, `score`, `comments`, `url`

详情获取：

```bash
SKILL_DIR="$HOME/.codex/skills/multi-platform-content-collector"
python3 "$SKILL_DIR/scripts/fetch_reddit_post.py" <subreddit> <post_id>
```

适合：用户反馈、痛点、产品讨论、prompt 分享、社区真实评价。

---

## Bilibili

返回字段：`title`, `author`, `score`, `url`

详情获取：

```bash
SKILL_DIR="$HOME/.codex/skills/multi-platform-content-collector"
python3 "$SKILL_DIR/scripts/fetch_bilibili_video.py" <BV号>
```

适合：中文视频案例、教程、创作者、评论区线索、AI 作品素材。

---

## 其他平台

用户明确要求时，可用 OpenCLI 适配器扩展：

| 平台 | 命令 | 备注 |
|---|---|---|
| 小红书 | `opencli xiaohongshu search` | 需登录 |
| 微博 | `opencli weibo search` | 需登录 |
| 抖音 | `opencli douyin hashtag search` | 需登录 creator.douyin.com |

---

## 命令速查

```bash
opencli twitter thread "<tweet-id>" -f json
opencli youtube video "<url>" -f json
opencli youtube transcript "<url>" -f json
python3 "$SKILL_DIR/scripts/fetch_reddit_post.py" <subreddit> <post_id>
python3 "$SKILL_DIR/scripts/fetch_bilibili_video.py" <BV号>
opencli doctor
```
