# Social Media Video Uploader — 完整工作流文档

通过 `social-upload` CLI 工具，将视频上传到 TikTok / Instagram / YouTube。支持单平台和多平台批量上传，包括平台原生定时发布功能。

---

## 一、核心概念

### 「定时发布」的含义

**「定时发布」= 使用平台内置的 Schedule 功能**：视频立即上传到平台，设定未来某个时间自动公开。不是用系统定时任务延迟执行上传命令。

用法：在上传命令中加 `--schedule "YYYY-MM-DD HH:MM"` 即可。

### 安全策略

1. **绝不接触用户凭证** — 不保存、不输入、不传输任何账号密码
2. **用户提供密码时必须拒绝**
3. **未登录即终止** — 脚本检测到未登录会自动 exit(1)

---

## 二、执行环境

| 配置项 | macOS | Windows |
|--------|-------|---------|
| CLI 命令 | `.venv/bin/social-upload` | `.venv\Scripts\social-upload` |
| working_directory | 项目根目录（包含 `pyproject.toml`） | 同左 |
| 运行模式 | `block_until_ms: 0`（后台执行，脚本需 3-5 分钟） | 同左 |

平台检测：`python -c "import sys; print(sys.platform)"` → `darwin` = macOS，`win32` = Windows。

---

## 三、平台路由

| 用户关键词 | 命令 |
|-----------|------|
| TikTok、抖音国际版 | `social-upload tiktok` |
| Instagram、ins、IG | `social-upload instagram` |
| YouTube、油管、YT | `social-upload youtube` |
| 全平台、所有平台 | 依次执行三个，每个完成后汇报再执行下一个 |

---

## 四、完整执行流程

### Step 1: 预检 + 收集信息

收到上传请求后，在同一回合内完成以下准备工作（不打断用户）。

#### 1.1 识别平台 & 提取信息

从用户消息中提取目标平台、视频路径、标题、描述等所有已知信息。

#### 1.2 读取默认配置

读取 `src/social_uploader/profiles/default.json` 了解各平台默认值。

#### 1.3 检查 Chrome 调试端口

```bash
curl -s http://localhost:9222/json/version
```

#### 1.4 自动填充所有字段

每个字段按以下优先级自动填值：

| 优先级 | 来源 | 举例 |
|--------|------|------|
| 1 | 用户明确给了值 | "标题叫周末探店" → `周末探店` |
| 2 | 从上下文推断 | 文件名 `cooking_vlog.mp4` → 标题 `cooking vlog` |
| 3 | 合理建议值 | 用户说"定时发布"但没给时间 → 填 `明天 10:00（⏳ 请确认）` |
| 4 | 平台默认值 | 没提可见性 → `所有人` |

---

### 各平台字段清单

#### TikTok 字段

| 字段 | 用户没说时的默认填充 |
|------|-----------------|
| 视频路径 | 唯一允许追问的字段 |
| 标题 | 从文件名推断 |
| 描述 | 复用标题 |
| 封面 | 无（平台自动截取） |
| 可见性 | 所有人 |
| 定时发布 | 立即 |
| 允许评论 | 是 |
| 允许二创 | 是 |
| 内容披露 | 否 |
| AI 生成标记 | 否 |
| 高画质上传 | 是 |

**TikTok Profile 可配置项：** `visibility`、`schedule`、`allow_comments`、`allow_reuse`、`disclose_content`、`ai_generated`、`high_quality`

**CLI 可选参数：** `--cover`（封面图）、`--no-publish`（仅填表不发布）、`--resume-from`（断点恢复）、`--profile`（配置文件）

#### Instagram 字段

| 字段 | 用户没说时的默认填充 |
|------|-----------------|
| 视频路径 | 唯一允许追问的字段 |
| 文案 | 自动拼接：标题 + 描述 |
| 同步到动态流 | 是 |
| 定时发布 | ❌ 不支持（平台限制） |

**注意：** Instagram 没有单独的 `--title` 和 `--description`，只有 `--caption`。Instagram **不支持定时发布和可见性设置**。

**Profile 可配置项：** `share_to_feed`

#### YouTube 字段

| 字段 | 用户没说时的默认填充 |
|------|-----------------|
| 视频路径 | 唯一允许追问的字段 |
| 标题 | 从文件名推断（≤95 字符） |
| 描述 | 复用标题（≤4900 字符） |
| 面向儿童 | 否 |
| 可见性 | 公开 |
| 定时发布 | 立即 |
| 标签 | 无 |
| 分类 | 无 |

**Profile 可配置项：** `made_for_kids`、`visibility`(`public`/`unlisted`/`private`)、`tags`、`category`、`schedule`

**定时发布注意：** 定时发布会自动将可见性设为 PUBLIC。设置失败时脚本中止发布，防止视频立即公开。

---

### 1.4.1 平台约束校验

| 约束 | 触发条件 | 处理 |
|------|---------|------|
| Instagram 不支持定时发布 | 用户要求 IG 定时 | 不传 `--schedule`，表格标注 `⚠️ 不支持` |
| Instagram 不支持可见性 | 用户要求 IG 设可见性 | 不传 `--visibility`，不显示该字段 |
| TikTok 仅自己可见无法定时 | 同时要求 `only_me` + 定时 | 不传 `--schedule`，只传 `--visibility only_me` |

#### 1.5 生成命令参数

**核心约束：只传用户明确要求的参数。**

CLI 支持两种方式传递非默认配置：

| 用户要求的配置 | 传参方式 |
|--------------|---------|
| 只有 schedule 和/或 visibility | 直接用 `--schedule` / `--visibility` CLI 参数 |
| 包含其他选项（ai_generated、tags 等） | 创建 profile JSON，用 `--profile` 传入 |
| 全部默认 | 不需要额外参数 |

**优先级：** CLI 参数 > profile 文件 > 默认值

Profile JSON 保存到 `~/.social_uploader/profiles/profile_{时间戳}.json`。

---

### Step 2: 展示完整方案，等用户确认

输出结构：
1. Chrome 连接状态 + 视频文件确认
2. 各平台参数表格
3. 📌 执行计划（执行顺序 + 即将执行的命令）
4. 确认语

**硬性规则：**
- 回复中不允许出现问号（不追问）
- 表格每个字段必须有值
- 执行计划中的命令必须是真实将要执行的命令
- 发出方案后必须等用户回复

**用户说"好的"** → 执行 Step 3。**用户说要改某项** → 更新后重新展示。

---

### Step 3: 执行上传

以 `block_until_ms: 0` 后台执行，每 10-15 秒轮询终端输出，看到 🎉 或 exit_code 时判定完成。

**执行前双向核对：**
- 正向：用户要了的参数 → 命令必须有
- 反向：用户没要的参数 → 命令禁止有

**命令格式示例：**

```bash
# TikTok
social-upload tiktok --video "路径" --title "标题" --description "描述"
social-upload tiktok --video "路径" --title "标题" --description "描述" --schedule "2026-04-10 15:00"

# Instagram（不支持 --schedule / --visibility）
social-upload instagram --video "路径" --caption "文案内容"

# YouTube
social-upload youtube --video "路径" --title "标题" --description "描述"
social-upload youtube --video "路径" --title "标题" --description "描述" --schedule "2026-04-10 15:00" --visibility unlisted
```

**多平台上传：** 默认按 TikTok → Instagram → YouTube 顺序依次执行。每个完成后汇报，一个失败不影响下一个。

---

### Step 4: 失败自动修复

终端输出 `DIAG|` 开头的行时触发自动修复。

| 错误类型 | 含义 | 处理 |
|---------|------|------|
| `selector_not_found` | 按钮找不到 | fix-selector 自动修复 |
| `state_mismatch` | 状态检测文案过期 | fix-pattern 自动修复 |
| `recipe_step_failed` | 配方某步失败（如定时发布） | show-recipe → fix-recipe → --resume-from 重试 |
| `visibility_failed` | 可见性设置失败 | 同上 |
| `file_rejected` | 视频被平台拒绝 | 通知用户检查格式 |
| `platform_unavailable` | 平台不可用 | 等 3 分钟后从头重跑，最多 2 次 |
| `login_required` | 未登录 | 提醒用户登录，--resume-from 重试 |
| `timeout` | 超时 | 提醒检查网络 |

---

## 五、元素查找机制（双轨并行）

- **轨道 A（快速路径）：** 读取 `button_config.json` 选择器列表，1.5s 内快速尝试
- **轨道 B（AI 路径）：** 轨道 A 未命中时，UltimateLocator 通过语义描述 + AgentQL AI API 定位元素
- **失败兜底：** 双轨均未命中时输出 `DIAG|` 诊断行

交互配方（定时发布、可见性等）使用三层兜底：
- **Tier 1：** 按 `state_patterns.json` 配方执行
- **Tier 2a：** 选择器失败时用 `dom_heuristic` 启发式搜索
- **Tier 2b：** 启发式失败时调 AgentQL AI API
- **Tier 3：** 全部失败时输出 `DIAG|` 交给 Agent

---

## 六、输出监控符号

| 符号 | 含义 |
|------|------|
| ✅ | 步骤成功 |
| ❌ | 步骤失败 |
| ⚠️ | 需人工关注 |
| 🎉 | 流程结束 |

退出码：`0` = 成功，`1` = 失败。

---

## 七、使用示例

### 单平台上传（默认配置）

```bash
# TikTok
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"

# TikTok（带封面图）
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末" --cover "/Users/xxx/cover.jpg"

# Instagram
.venv/bin/social-upload instagram --video "/Users/xxx/vlog.mp4" --caption "周末探店 🍜 #美食 #vlog"

# YouTube
.venv/bin/social-upload youtube --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"
```

### 定时发布和可见性

```bash
# TikTok 定时发布
.venv/bin/social-upload tiktok --video "..." --title "..." --description "..." --schedule "2026-04-10 15:00"

# TikTok 好友可见 + 定时发布
.venv/bin/social-upload tiktok --video "..." --title "..." --description "..." --schedule "2026-04-10 15:00" --visibility friends

# YouTube 定时发布
.venv/bin/social-upload youtube --video "..." --title "..." --description "..." --schedule "2026-04-10 15:00"

# YouTube 不公开列出
.venv/bin/social-upload youtube --video "..." --title "..." --description "..." --visibility unlisted
```

### 使用自定义 Profile 配置

```json
{
  "tiktok": {
    "ai_generated": true,
    "disclose_content": true
  }
}
```

```bash
.venv/bin/social-upload tiktok --video "..." --title "..." --description "..." --profile ai_config.json
```

### 仅填表单不发布

```bash
.venv/bin/social-upload tiktok --video "..." --title "测试" --description "测试描述" --no-publish
```

### 从断点恢复

```bash
.venv/bin/social-upload youtube --video "..." --title "标题" --description "描述" --resume-from publish
```

### 全平台依次上传

```bash
# 1. TikTok
.venv/bin/social-upload tiktok --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"
# 2. Instagram
.venv/bin/social-upload instagram --video "/Users/xxx/vlog.mp4" --caption "周末探店 🍜 记录周末的美食之旅"
# 3. YouTube
.venv/bin/social-upload youtube --video "/Users/xxx/vlog.mp4" --title "周末探店" --description "记录周末的美食之旅"
```

### 切换账号后重启浏览器

```bash
.venv/bin/social-upload restart-browser
bash scripts/start_chrome_debug.sh        # macOS
scripts\start_chrome_debug.bat            # Windows
```

---

## 八、故障排查

### 连接浏览器失败
- 确认 Chrome 以调试模式启动：`bash scripts/start_chrome_debug.sh`
- 验证端口：`curl -s http://localhost:9222/json/version`

### 未登录
- 脚本自动检测登录状态，未登录则 exit(1)
- 在浏览器中手动登录后重试

### 找不到元素 / 页面结构变化

**按钮选择器修复（命令行操作，无需编辑文件）：**
1. `social-upload suggest-selectors --run-id {run_id}` — 获取修复建议
2. `social-upload fix-selector --target {平台} --key {按钮名} --selector "..."` — 执行修复
3. 用 `--resume-from {步骤}` 从断点重试

**交互配方修复：**
1. `social-upload show-recipe --target {平台} --recipe {配方名}` — 查看配方
2. `social-upload fix-recipe --target {平台} --recipe {配方名} --step {步骤ID} --selector "新选择器"` — 修复
- 配方名：`schedule_recipe`（定时发布）、`visibility_recipe`（可见性，TikTok）

### DIAG 日志说明
- 失败时写入 `~/.social_uploader/summary.jsonl`（索引）和 `detail_{run_id}.jsonl`（DOM 片段等详情）
- `DIAG|` 格式：`DIAG|run_id=xxx|platform=xxx|step=xxx|error=xxx`
- 用 `social-upload diag` 可手动提取浏览器精简 DOM

### 切换 Chrome 账号后仍连接旧账号
调试浏览器使用独立数据目录 `~/.chrome-social-upload`，与日常 Chrome 隔离。切换方法：
1. `social-upload restart-browser`
2. 重启调试浏览器
3. 在调试浏览器中退出旧账号、登录新账号

### CLI 命令找不到
- 确认安装：`.venv/bin/pip install -e .`
- 确认环境：`.venv/bin/social-upload --help`

---

## 九、关键文件索引

| 文件 | 角色 |
|------|------|
| `src/social_uploader/uploaders/tiktok.py` | TikTok 上传逻辑 |
| `src/social_uploader/uploaders/instagram.py` | Instagram 上传逻辑 |
| `src/social_uploader/uploaders/youtube.py` | YouTube 上传逻辑 |
| `src/social_uploader/button_config.json` | 按钮选择器配置 |
| `src/social_uploader/state_patterns.json` | 交互配方定义 |
| `src/social_uploader/profiles/default.json` | 默认配置 |
| `src/social_uploader/command_entry.py` | CLI 入口 |
| `scripts/start_chrome_debug.sh` | Chrome 调试模式启动脚本 |
