# 社交媒体数据分析与创作指导 — 完整工作流文档

通过 OpenCLI 适配器采集各社交平台创作者数据看板，生成数据简报并给出 AI 驱动的内容创作建议。支持 YouTube、TikTok、Instagram 三大平台。

---

## 一、核心概念

本 Skill 由 4 个子模块组成，按顺序串联执行：

```
BROWSER（浏览器管理）→ COLLECT（数据采集）→ ANALYZE（分析引擎）→ REPORT（报告导出）
```

整个流程以 3 轮对话完成：
1. **第 1 轮：** 打开浏览器，要求用户登录
2. **第 2 轮：** 验证登录 + 确认账号
3. **第 3 轮：** 采集数据 + 生成报告

---

## 二、执行环境

| 配置项 | macOS | Windows |
|--------|-------|---------|
| CLI 命令 | `.venv/bin/social-upload` | `.venv\Scripts\social-upload` |
| working_directory | 项目根目录（含 `pyproject.toml`） | 同左 |
| Chrome 用户数据 | `~/.social_uploader/chrome_profiles/<account>/` | 同左 |
| 调试端口 | 9222 | 同左 |

平台检测：`python -c "import sys; print(sys.platform)"` → `darwin` = macOS，`win32` = Windows。

> ⚠️ **下文所有 `<CLI>` 均代表上表中的 CLI 命令路径。** macOS 为 `.venv/bin/social-upload`，Windows 为 `.venv\Scripts\social-upload`。复制命令前请替换为实际路径。

---

## 三、硬性规则

1. 采集命令只用 `monitor collect`，**禁止** `monitor run`
2. **禁止输出技术细节**（执行计划、命令代码块等），只展示自然语言和最终报告
3. 每轮结束后必须停下等用户回复，不能连续执行多轮
4. 本 skill 与上传 skill 无关，禁止借用上传 skill 的输出格式

---

## 四、完整执行流程

### 第 1 轮：打开浏览器

#### 执行操作

```bash
<CLI> account login
```

#### 输出示例

```
🌐 调试浏览器已就绪（端口 9222）。

⚠️ 请在调试浏览器中登录你要查看数据的平台账号：

  1. YouTube Studio → studio.youtube.com
  2. TikTok Studio → tiktok.com/tiktokstudio
  3. Instagram → instagram.com

请逐个打开上面的链接，确认登录后回复"已登录"。
```

**然后停下，等用户回复。**

#### 浏览器状态检查（排障用）

```bash
lsof -i :9222 2>/dev/null | head -3
```
- 有输出 → Chrome 调试模式已运行
- 无输出 → 需要启动

#### Browser Bridge 检查（排障用）

```bash
opencli doctor 2>&1 | head -5
```
- `[OK] Extension: connected` → 连接正常
- 失败 → 需在 `chrome://extensions` 启用 OpenCLI Browser Bridge 扩展

---

### 第 2 轮：验证登录 + 确认账号

用户说"已登录"后，逐平台验证：

```bash
opencli tiktok creator-stats -f json 2>&1 | head -20
opencli instagram creator-stats -f json 2>&1 | head -20
```

#### 判断规则

| 输出 | 含义 | 处理 |
|------|------|------|
| 返回 JSON 数据（exit_code=0） | 已登录 | 标记 ✅ |
| `Not logged in` 或 `missing cookie` | 未登录 | 要求重新登录 |
| `No tab with id` / 连接错误 | 标签页问题 | 要求刷新页面 |
| 其他非 0 退出码 | 其他错误 | 展示错误信息 |

YouTube 不执行全量适配器验证（耗时太长），仅检查浏览器是否打开了 YouTube 标签页。

#### 输出示例

```
🔍 验证各平台登录状态：
  ✅ YouTube: 已登录
  ✅ TikTok: 已登录（用户: @example_tiktok）
  ❌ Instagram: 未登录 (missing ds_user_id cookie)

⚠️ Instagram 尚未登录成功。请在调试浏览器中打开 instagram.com 并登录后回复"好了"。
```

**全部通过后展示检测到的用户名，问"这是你的账号吗？"，然后停下等用户确认。**

---

### 第 3 轮：采集 + 出报告

用户确认后执行：

```bash
<CLI> monitor collect
```

以 `block_until_ms: 0` 后台执行，每 10-15 秒轮询。

#### 完成信号

| 终端输出 | 含义 | 下一步 |
|---------|------|--------|
| `✅ youtube: ... (用户: @xxx)` | 单平台采集成功 | 继续等待 |
| `❌ youtube: ...` | 单平台采集失败 | 记录错误 |
| `🎉 数据采集完成` | 全部完成 | 采集结束 |
| `exit_code: 0` | 正常退出 | 采集结束 |
| `exit_code: 1` | 异常退出 | 进入错误处理 |

#### 采集后身份确认

```
📊 采集完成，检测到以下已登录账号：

| 平台 | 检测到的账号 | 采集结果 |
|------|------------|---------|
| YouTube | 频道: Example Channel | ✅ 3 项指标, 20 条视频 (自动检测频道) |
| TikTok | 用户: @example_tiktok | ✅ 14 项指标, 7 条视频 (4-tab 全量) |
| Instagram | 用户: @example_instagram | ✅ 9 项指标, 20 条视频 |

这些是你想查看的账号吗？
```

确认后，将终端输出的完整报告（创作建议 + 数据简报）展示给用户。

---

## 五、快速路径

| 用户需求 | 做法 |
|---------|------|
| "看看我的视频数据" | 完整 3 轮对话 |
| "基于上次数据重新分析" | 直接 `monitor report` |
| "导出 HTML 报告" | 直接 `monitor report --format html` |
| "导出 Markdown 报告" | 直接 `monitor report --format md` |

只有"重新分析"和"导出"可以跳过第 1-2 轮。

---

## 六、子模块详解

### 6.1 SM-Browser — 调试浏览器管理

管理调试 Chrome 实例的生命周期。

| 功能 | 命令 | 说明 |
|------|------|------|
| 检查状态 | `lsof -i :9222` | 有输出=运行中 |
| 启动浏览器 | `<CLI> account login` | 指定账号：`<CLI> account login myaccount` |
| 备用启动 | `bash scripts/start_chrome_debug.sh` | 脚本方式 |
| 检查 Bridge | `opencli doctor 2>&1 \| head -5` | 需要 OpenCLI 扩展 |
| 重启浏览器 | `<CLI> restart-browser` | 重启后需重新登录 |

**关键文件：**
| 文件 | 角色 |
|------|------|
| `src/social_uploader/account_manager.py` | Chrome Profile 管理、实例启动 |
| `src/social_uploader/tools/browser_manager.py` | 端口检测、kill_browser |
| `scripts/start_chrome_debug.sh` | 备用启动脚本 |

---

### 6.2 SM-Collect — 数据采集

通过 `social-upload monitor collect` 调用 OpenCLI 适配器采集各平台数据。

#### 前置条件（全部满足才能执行）
1. 调试浏览器已运行（端口 9222）
2. 用户已在浏览器中手动登录各平台
3. 登录验证已通过
4. 平台配置已就绪

#### 支持平台

| 平台 | OpenCLI 命令 | 采集方式 | 耗时 |
|------|-------------|---------|------|
| YouTube | `opencli youtube creator-stats` | 自动检测频道 + DOM 解析 | ~40s |
| TikTok | `opencli tiktok creator-stats` | 4-tab 全量采集 + 内容管理页 | ~30s |
| Instagram | `opencli instagram creator-stats` | REST API 直调 | ~9s |
| 抖音 | `opencli douyin stats <aweme_id>` | REST API 直调 | ~5s |

#### 采集流程技术详情

**YouTube（自动检测频道 + DOM 解析）：**

适配器不需要预先提供频道 ID，全流程自动完成：

| 步骤 | 页面 | 采集内容 | 方式 |
|------|------|---------|------|
| 1 | `studio.youtube.com` | 频道 ID + 频道名 | 等待 Studio 自动重定向到 `/channel/UCxxx/`，从 URL 提取 |
| 2 | Analytics 概览页 | 观看次数、观看时长、订阅人数 | 直接导航 → DOM 文本解析 |
| 3 | Content 管理页 | 每条视频的标题、时长、可见性、日期、观看次数、评论数 | 直接导航 → DOM 文本解析 |

注意事项：
- 频道 ID 也可手动传入：`opencli youtube creator-stats UCxxx -f json`
- 如果账号有多个频道且 Studio 显示频道选择器，自动检测可能失败
- 草稿和处理中断的视频不包含观看/评论数据

**Instagram：**
1. 从 cookie 提取 `ds_user_id` 和 `csrftoken`
2. 调用 `/api/v1/users/{userId}/info/` → 粉丝数等
3. 调用 `/api/v1/feed/user/{userId}/?count=20` → 视频数据
4. 自动计算互动率、视频/图片分布

**TikTok（4-tab 全量采集）：**

适配器会依次访问 TikTok Studio 的 4 个分析 tab + 内容管理页，共采集 5 个维度的数据：

```
Analytics → Overview → Content → Viewers → Followers → Content 管理页
```

| 步骤 | 页面/Tab | 采集内容 | 方式 |
|------|---------|---------|------|
| 1 | 进入 analytics | 用户资料（粉丝、关注、获赞、视频数） | `/tiktokstudio/api/web/user` JSON API |
| 2 | **Overview tab** | Video views, Profile views, Likes, Comments, Shares, Est. rewards + 趋势变化 | SSR DOM 文本解析 |
| 3 | **Content tab** | 热门帖子排行（按 Most views / Most likes 等） | 点击 tab → DOM 文本解析 |
| 4 | **Viewers tab** | Total viewers, New viewers + 性别/年龄/地区画像 | 点击 tab → DOM 文本解析 |
| 5 | **Followers tab** | Total followers, Net followers + 粉丝性别/年龄/地区画像 | 点击 tab → DOM 文本解析 |
| 6 | Content 管理页 | 每条视频的 views/likes/comments、发布日期、时长、隐私状态 | 导航到 `/tiktokstudio/content` → DOM 解析 |

注意事项：
- Viewers 画像（性别/年龄/地区）需达到 100 观看者才显示
- Followers 画像需达到 100 粉丝才显示
- Content tab 的热门帖子需要有播放数据才会出现
- 视频列表包含定时发布（scheduled）和私密（Only me）的视频

#### 初始化配置

```bash
<CLI> monitor config --youtube true --tiktok true --instagram true   # 设置
<CLI> monitor config                                                  # 查看
```

#### 数据存储

```
~/.social_uploader/analytics/<account>/snapshots/<timestamp>_<platform>.json
```

**关键文件：**
| 文件 | 角色 |
|------|------|
| `src/social_uploader/analytics/collector.py` | 采集编排 |
| `src/social_uploader/analytics/store.py` | 快照存取 |

---

### 6.3 SM-Analyze — 数据分析 + AI 创作建议

#### 规则分析引擎 (`analyzer.py`)

内置分析规则，不依赖 LLM：

| 分析维度 | 计算方式 |
|---------|---------|
| 互动率 | (点赞 + 评论 + 分享) / 播放量 |
| 趋势变化 | 当前快照 vs 上一次快照的百分比变化 |
| 爆款检测 | 某视频指标 > 全部视频均值 × 2.0 |
| 低迷检测 | 某视频指标 < 全部视频均值 × 0.3 |
| 发布节奏 | 按发布时间统计每日/每周频率 |

#### AI 创作建议 (`advisor.py`)

Moonshot LLM 接收**脱敏数据**（视频标题替换为"视频1""视频2"），生成：

1. **内容方向建议** — 基于爆款视频分析热门方向
2. **格式与长度建议** — 最佳视频时长、封面风格
3. **发布策略** — 最佳发布时间、频率
4. **标签建议** — 热门标签推荐

#### AI 降级策略

| 情况 | 行为 |
|------|------|
| `MOONSHOT_API_KEY` 未配置 | 降级为规则建议，报告标注 `source: rules` |
| LLM 调用失败 | 降级为规则建议，日志记录错误 |
| LLM 返回非标准 JSON | 自动修复（中文引号→标准引号），失败则降级 |

#### 配置 API Key

```bash
export MOONSHOT_API_KEY=sk-xxx
```

不设置也可以使用，AI 建议会降级为基于规则的建议。

#### 数据隔离
- 发送给 LLM 的数据**不包含**频道 ID、用户名、视频 URL
- 视频标题替换为匿名编号
- API Key 仅从环境变量加载

**关键文件：**
| 文件 | 角色 |
|------|------|
| `src/social_uploader/analytics/analyzer.py` | 规则分析引擎 |
| `src/social_uploader/analytics/advisor.py` | AI 建议生成 |

---

### 6.4 SM-Report — 报告渲染与导出

#### 支持格式

| 格式 | 命令 | 输出 | 适用场景 |
|------|------|------|---------|
| 终端 | `<CLI> monitor report --format terminal` | 直接终端输出 | 快速查看 |
| Markdown | `<CLI> monitor report --format md` | 终端 + `.md` 文件 | 文档归档、飞书/Notion |
| HTML | `<CLI> monitor report --format html` | 终端 + `.html` 文件 | 浏览器查看、分享 |

#### 高级用法

```bash
# 自定义保存路径
<CLI> monitor report --format md --output ~/Desktop/my_report.md

# 指定时间范围
<CLI> monitor report --period 7                 # 最近 7 天
<CLI> monitor report --period 30 --format md    # 最近 30 天

# 指定账号
<CLI> monitor report --format md --account myaccount
```

#### 报告内容结构

```
📊 社交媒体数据简报
├── 📅 报告日期 + 涵盖平台
├── 🔑 关键发现
│   ├── 亮点（🔥 爆款视频、涨粉等）
│   └── 预警（⚠️ 下降趋势等）
├── 📈 账号级指标总览
│   ├── 各平台核心指标 + 趋势变化
│   └── 跨平台对比表（多平台时）
├── 🎬 视频详情
│   ├── 逐视频指标表（含所有可用字段）
│   └── 爆款/低迷标记（🔥 / ⚠️）
├── 💡 AI 创作建议
│   ├── 内容方向
│   ├── 格式与长度
│   ├── 发布策略
│   └── 标签推荐
└── 📝 元信息（生成时间、数据来源）
```

#### 模板系统

| 模板文件 | 用途 |
|---------|------|
| `src/social_uploader/analytics/templates/report.md` | Markdown 模板 |
| `src/social_uploader/analytics/templates/report.html` | HTML 模板（含样式） |

终端格式由 `reporter.py` 的 `render_terminal()` 直接生成，不使用模板。

#### 报告存储

```
~/.social_uploader/analytics/
├── <account>/
│   ├── reports/
│   │   ├── 2026-04-14_report.md
│   │   ├── 2026-04-14_report.html
│   │   └── ...
│   ├── snapshots/       ← 原始采集数据
│   └── history.jsonl    ← 采集历史
└── accounts_map.json    ← 平台开关配置
```

**关键文件：**
| 文件 | 角色 |
|------|------|
| `src/social_uploader/analytics/reporter.py` | 报告渲染核心 |
| `src/social_uploader/analytics/templates/report.md` | Markdown 模板 |
| `src/social_uploader/analytics/templates/report.html` | HTML 模板 |
| `src/social_uploader/analytics/store.py` | 报告保存 |

---

## 七、错误处理汇总

| 错误 | 终端表现 | 处理 |
|------|---------|------|
| Chrome 启动失败 | — | 手动：`bash scripts/start_chrome_debug.sh` |
| 端口被占用 | — | `<CLI> restart-browser` |
| Browser Bridge 断开 | `exit code 69` | `chrome://extensions` 启用扩展 |
| OpenCLI 未安装 | `未找到 opencli 命令` | `npm install -g @jackwener/opencli` |
| 未登录 | `Not logged in (missing cookie)` | 用户需在浏览器中登录 |
| YouTube 频道 ID 缺失 | `channel ID not detected` | 在浏览器打开 studio.youtube.com 并登录 |
| Tab ID 失效 | `No tab with id: xxx` | `<CLI> restart-browser` |
| 超时 | >3 分钟无输出 | 检查网络 |

---

## 八、调试技巧

### 直接调用 OpenCLI（跳过 social-upload）

```bash
opencli youtube creator-stats -f json              # 自动检测频道，约 40 秒
opencli youtube creator-stats UCxxxx -f json       # 手动指定频道 ID
opencli tiktok creator-stats -f json               # 4-tab 全量采集，约 25 秒
opencli instagram creator-stats -f json
opencli instagram creator-stats --count 50 -f json
```

### 用 opencli browser 手动查看 TikTok Studio 数据

当需要排查 TikTok 数据采集问题时，可以用浏览器控制命令逐步操作：

```bash
# 1. 打开 TikTok Studio
opencli browser open "https://www.tiktok.com/tiktokstudio"

# 2. 查看页面状态（找到 Analytics 按钮的索引号 N）
opencli browser state 2>&1 | grep -E "Analytics|Content|Viewers|Followers"

# 3. 点击 Analytics 按钮
opencli browser click N

# 4. 等待加载后截图
sleep 5 && opencli browser screenshot ~/Desktop/tiktok_overview.png

# 5. 提取页面文本看实际数据
opencli browser eval "document.querySelector('#root').innerText.substring(0, 2000)"

# 6. 逐个点击 Content / Viewers / Followers tab（先找索引号）
opencli browser state 2>&1 | grep -E "\[.*\].*Content|Viewers|Followers"
opencli browser click <Content索引>
opencli browser click <Viewers索引>
opencli browser click <Followers索引>

# 7. 查看 Posts 管理页
opencli browser open "https://www.tiktok.com/tiktokstudio/content"
sleep 5 && opencli browser eval "document.querySelector('#root').innerText.substring(0, 3000)"
```

### 查看快照和报告

```bash
ls -la ~/.social_uploader/analytics/default/snapshots/ | tail -5
ls -la ~/.social_uploader/analytics/default/reports/
```

### 用浏览器打开 HTML 报告

```bash
open ~/.social_uploader/analytics/default/reports/2026-04-14_report.html   # macOS
```

### 单独测试分析模块

```python
from social_uploader.analytics.store import load_latest_snapshot
from social_uploader.analytics.analyzer import analyze
snapshot = load_latest_snapshot(account="default")
result = analyze(snapshot)
```

### 测试 AI 建议

```python
from social_uploader.analytics.advisor import generate_advice
advice = generate_advice(analysis_result)
```

---

## 九、OpenCLI 适配器输出结构

各平台 `creator-stats` 适配器返回统一的 `[{metric, value, trend}, ...]` 格式，通过 `---` 分隔符划分数据区。

### YouTube 适配器输出（自动检测频道 + DOM 解析）

```
┌─ 用户资料 ────────────────────────────────────
│  用户名 (username)        bill s（或频道 ID）
├─ Overview (过去 28 天) ───────────────────────
│  观看次数 (views)         145
│  观看时长（小时） (watch_time_hours)  0.1
│  订阅人数 (subscribers)   +1
├─ Top Videos (N 条视频) ──────────────────────
│  🎬 公开视频标题          views=X comments=Y   日期
│  ⏰ 定时发布视频          views=0 comments=0   日期
│  📝 草稿视频              views=0 comments=0
│  🔒 私享视频              views=X comments=Y   日期
│  🔗 不公开列出视频        views=X comments=Y   日期
└──────────────────────────────────────────────
```

### TikTok 适配器输出（4-tab 全量）

```
┌─ 用户资料 ────────────────────────────────────
│  用户名 (username)        spicychicke2
│  粉丝数 (followers)       0
│  关注数 (following)       0
│  获赞总数 (hearts)        0
│  视频数 (videos)          0
├─ 概览 Overview (过去 7 天) ───────────────────
│  Video views (views)      0          (--)
│  Profile views            0          (--)
│  Likes (likes)            0          (--)
│  Comments (comments)      0          (--)
│  Shares (shares)          0          (--)
│  Est. rewards             $0         (0.0%)
├─ 内容 Content ───────────────────────────────
│  热门帖子                 暂无 / 视频排行列表
├─ 观众 Viewers (过去 7 天) ───────────────────
│  Total viewers            0          (--)
│  New viewers              0          (--)
│  性别分布 / 年龄分布 / 地区分布（需 100 观看者）
├─ 粉丝 Followers ─────────────────────────────
│  Total followers          0          All time
│  Net followers            0          (--)
│  粉丝性别 / 年龄 / 地区（需 100 粉丝）
├─ Top Videos (N 条视频) ──────────────────────
│  🎬 视频标题              views=X likes=Y comments=Z   日期
│  🔒 私密视频标题          views=X likes=Y comments=Z   日期
└──────────────────────────────────────────────
```

### Instagram 适配器输出

```
┌─ 用户资料 ────────────────────────────────────
│  粉丝数 / 关注数 / 帖子数 / 用户名 / 账号类型
├─ 近期内容汇总 (N posts) ─────────────────────
│  总点赞 / 总评论 / 总播放 / 视频数 / 图片数 / 互动率
├─ 单帖数据 (top 10) ─────────────────────────
│  🎬 视频标题    likes=X comments=Y plays=Z   日期
└──────────────────────────────────────────────
```

### collector.py 如何消化适配器输出

`collector.py` 的 `_normalize_flat_output()` 通过分隔符路由数据：

| 分隔符 value 关键词 | 映射到 section | 数据去向 |
|---|---|---|
| `Top Video` / `单帖` / `Top Content` | `videos` | `video_metrics[]` |
| `近期内容` / `content` | `summary` | `account_metrics{}` |
| `分析数据` / `analytics` | `analytics` | `account_metrics{}` |
| `概览` / `Overview` | `analytics` | `account_metrics{}` |
| `观众` / `Viewers` | `analytics` | `account_metrics{}` |
| `粉丝` / `Followers` | `analytics` | `account_metrics{}` |
| `内容` / `Content` | `summary` | `account_metrics{}` |

视频行的 `value` 格式（`views=X likes=Y comments=Z`）通过正则 `(\w+)=(\d+)` 提取。

---

## 十、扩展新平台

在 `~/.opencli/clis/<新平台>/` 下创建 `creator-stats.js` 适配器，返回 `[{metric, value, trend}, ...]` 格式，然后执行：

```bash
<CLI> monitor config --新平台 true
```

---

## 十一、关键文件索引

| 文件 | 角色 |
|------|------|
| `src/social_uploader/analytics/__init__.py` | 模块入口 |
| `src/social_uploader/analytics/collector.py` | 采集编排（调用 opencli） |
| `src/social_uploader/analytics/analyzer.py` | 规则分析引擎 |
| `src/social_uploader/analytics/advisor.py` | AI 建议生成 |
| `src/social_uploader/analytics/reporter.py` | 报告渲染 |
| `src/social_uploader/analytics/store.py` | 数据存取 |
| `src/social_uploader/analytics/templates/report.md` | Markdown 模板 |
| `src/social_uploader/analytics/templates/report.html` | HTML 模板 |
| `src/social_uploader/account_manager.py` | Chrome Profile 管理 |
| `src/social_uploader/tools/browser_manager.py` | 浏览器管理 |
| `src/social_uploader/command_entry.py` | CLI 入口 |
| `~/.social_uploader/analytics/accounts_map.json` | 平台开关配置 |
| `~/.opencli/clis/tiktok/creator-stats.js` | TikTok 4-tab 全量采集适配器 |
| `~/.opencli/clis/instagram/creator-stats.js` | Instagram REST API 采集适配器 |
| `~/.opencli/clis/youtube/creator-stats.js` | YouTube 自动检测频道 + DOM 解析采集适配器 |
