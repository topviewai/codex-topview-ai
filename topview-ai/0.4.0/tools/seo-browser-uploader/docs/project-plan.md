# 社交媒体视频自动上传 — 项目规划文档

> 最后更新：2026-04-05
> 当前版本：v0.2.0

---

## 一、项目是什么

一个命令行工具，连接你本地已打开的 Chrome 浏览器，自动完成向 TikTok / Instagram / YouTube 上传视频的全部操作（填标题、填描述、点发布）。

核心特点：
- **不碰密码**：用你自己已登录的浏览器，工具不接触任何账号信息
- **AI 自修复**：平台改版导致按钮找不到时，AI 能自动分析页面、修复配置、重试上传
- **新窗口隔离**：每次上传在独立的新窗口中进行，不影响你正在用的浏览器标签页

---

## 二、项目文件结构

```
项目根目录/
├── pyproject.toml                       # Python 包配置（依赖、入口命令）
├── README.md                            # 项目说明
├── .venv/                               # Python 虚拟环境
│
├── src/social_uploader/                 # 【核心代码】
│   ├── command_entry.py                 # ① 命令入口：接收用户指令，分发给对应平台
│   ├── button_config.json               # ② 按钮配置表：记录每个平台的按钮怎么找
│   ├── error_classifier.py              # ③ 错误分类器：判断错误类型和处理方式
│   ├── repair_engine.py                # ④ 日志与修复引擎：记录日志 + 拍快照 + 推荐修复
│   │
│   ├── uploaders/                       # 【上传脚本】
│   │   ├── video_check.py               # ⑤ 视频校验：检查文件是否合法
│   │   ├── tiktok.py                    # ⑥ TikTok 上传全流程
│   │   ├── instagram.py                 # ⑦ Instagram 上传全流程
│   │   └── youtube.py                   # ⑧ YouTube 上传全流程
│   │
│   └── tools/                           # 【工具箱】
│       ├── browser_manager.py           # ⑨ 浏览器管理：连接 Chrome、开新窗口、清弹窗
│       ├── element_finder.py            # ⑩ 双轨元素查找：轨道 A 快速选择器 → 轨道 B AI 语义定位
│       ├── ai_locator.py             # ⑪ AI 导航器：UltimateLocator（页面预热 + 语义查询 + 视觉校验）
│       ├── platform_semantics.py       # ⑫ 平台语义配置：每个按钮的 container + target 描述
│       ├── agentql_client.py            # ⑬ AgentQL API 调用：REST API 语义定位 + 属性精提
│       ├── pattern_checker.py          # ⑭ 状态模式检查：页面状态检测 + 弹窗清理
│       ├── recipe_runner.py            # ⑮ 交互配方执行：定时发布、可见性等复杂流程
│       └── dom_heuristic.py           # ⑯ DOM 启发式发现：语义关键词搜索替代元素
│
├── scripts/                             # 辅助脚本
│   ├── install.sh / install.bat         # 一键安装
│   └── start_chrome_debug.sh / .bat     # 启动 Chrome 调试模式
│
├── docs/                                # 文档
│   ├── 项目规划文档.md                    # 本文件
│   └── 自动修复机制说明.md                # 修复机制的通俗解释
│
├── tests/                               # 测试素材
│   ├── sample_video.mp4
│   └── sample_cover.jpg
│
├── vendor_wheels/                       # 离线安装包（无网络时用）
│
└── .cursor/skills/social-media-uploader/ # AI Agent 的操作手册
    ├── SKILL.md                          # Agent 看的完整操作指南
    ├── examples.md                       # 使用示例
    └── troubleshooting.md                # 故障排查
```

---

## 三、每个文件负责什么（详解）

### ① `command_entry.py` — 命令入口

**做什么**：接收用户在终端输入的命令，根据平台名分发给对应的上传脚本。

**包含的子命令**：
| 子命令 | 作用 |
|--------|------|
| `social-upload tiktok --video ... --title ... --description ...` | 上传到 TikTok |
| `social-upload instagram --video ... --caption ...` | 上传到 Instagram |
| `social-upload youtube --video ... --title ... --description ...` | 上传到 YouTube |
| `social-upload diag` | 提取当前页面的精简 DOM（调试用） |
| `social-upload suggest-selectors --run-id xxx` | 从失败快照中推荐修复命令 |
| `social-upload fix-selector --target xxx --key xxx --selector "..."` | 往按钮配置表中添加新按钮 |

**调用关系**：用户 → `command_entry.py` → `uploaders/tiktok.py` 或 `instagram.py` 或 `youtube.py`

---

### ② `button_config.json` — 按钮配置表

**做什么**：记录每个平台上每个关键按钮"怎么找"。这是 **AI 修复时唯一会被修改的文件**。

**结构示例**：
```json
{
  "tiktok": {
    "post_button": ["@data-e2e=upload-btn", "text:发布", "text:Post"],
    "file_input": ["tag:input@type=file"]
  },
  "youtube": {
    "upload_icon": ["@id=upload-icon", "@aria-label=上传视频"],
    "post_button": ["#done-button", "text:发布"]
  }
}
```

每个按钮对应一个列表，列表里是多个"找法"，脚本会从前往后依次尝试，第一个找到的就用。

**谁读它**：`element_finder.py` 读取 → 交给上传脚本使用
**谁改它**：`element_finder.py` 的 `add_selector()` 函数（被 `fix-selector` 命令调用）

---

### ③ `error_classifier.py` — 错误分类器

**做什么**：定义每种错误该怎么处理。

```
selector_not_found  →  AI 自己修（agent_fix）
login_required      →  通知用户去登录（notify_user）
timeout             →  等一会再试（wait_retry）
unknown             →  告诉用户（escalate_user）
```

**谁用它**：Agent 通过 SKILL.md 中的流程判断，目前 Agent 只自主处理 `selector_not_found`，其他类型通知用户。

---

### ④ `repair_engine.py` — 日志与修复引擎 ⭐ AI 修复的核心

这是整个自动修复机制最重要的文件，它负责三件事：

**（A）记录每一步的执行日志**

上传脚本每完成一步就调用 `log_step()`：
```
成功 → {"step":"login","status":"ok"}           输出到 stderr
失败 → {"step":"publish","status":"fail","error":"selector_not_found"}
```
同时输出 emoji 日志到终端给人看：`✅ [login] 完成` 或 `❌ [publish] 失败`

**（B）失败时"拍快照" + 写日志文件**

当按钮找不到时，`report_failure()` 函数做三件事：
1. 运行 JS 脚本提取页面上所有可交互元素的信息（"拍快照"）
2. 写两个日志文件到 `~/.social_uploader/`：
   - `summary.jsonl`：一行摘要（< 500 字），记录哪个平台、哪步失败、什么错误
   - `detail_{run_id}.jsonl`：详细信息（≤ 1500 字），包含 DOM 快照
3. 终端输出 `DIAG|run_id=xxx|platform=xxx|step=xxx|error=xxx`（给 AI 的报警信号）

**（C）分析快照，推荐修复命令**

`suggest_selectors()` 函数被 `suggest-selectors` 子命令调用：
1. 读取 detail 文件中保存的 DOM 快照
2. 用 `STEP_KEYWORDS` 字典做语义匹配（比如"发布按钮"→ 找包含 "post"、"publish"、"发布" 的元素）
3. 把匹配到的元素转换成可直接运行的 `fix-selector` 命令，输出给 AI

**信息字数限制机制（防止 AI 上下文溢出）**：
| 限制层 | 做了什么 | 限到多少 |
|--------|---------|---------|
| JS 只提取按钮 | 忽略所有装饰标签，只取 button/input/a 等 | 整页几百KB → 几KB |
| 只保留关键属性 | 每个元素只留 id、class(前3个)、aria-label 等 11 个属性，文字只取前 15 字 | 再砍一半 |
| 硬限总字符 | `MAX_SNIPPET_CHARS = 1500`，超了直接截断 | **≤ 1.5KB** |
| 分层文件 | summary（< 500 字） + detail（≤ 1500 字），AI 先看摘要再按需看详情 | 每轮 **~2.5KB** |
| 每轮独立 | 每次修复只看最新日志，不累积历史 | 不会无限增长 |

---

### ⑤ `uploaders/video_check.py` — 视频校验

**做什么**：上传前检查视频文件是否合法（文件是否存在、格式是否支持、大小是否正常）。还提供统一的"未登录"错误提示。

**被谁调用**：被 tiktok.py / instagram.py / youtube.py 在最开头调用。

---

### ⑥⑦⑧ `uploaders/tiktok.py` / `instagram.py` / `youtube.py` — 上传脚本

**做什么**：各平台的完整上传自动化流程。它们是实际操作浏览器的代码。

**内部流程（以 TikTok 为例）**：
```
校验视频 → 连接浏览器 → 打开上传页 → 检测登录状态
→ 清理弹窗 → 注入视频文件 → 等待上传完成
→ 填写标题和描述 → 等待版权检查
→ 点击发布 → 等待发布成功确认
```

**每一步执行后都会**：
- 成功 → 调用 `log_step("步骤名", "ok")`
- 失败 → 调用 `log_step("步骤名", "fail", error="错误类型")`
- 按钮找不到 → 额外调用 `report_failure()` 拍快照写日志

**找按钮的方式**：不直接写死，而是调用 `element_finder.py` 的 `find_element(page, "tiktok", "post_button")`，后者去 `button_config.json` 里查按钮名单。

---

### ⑨ `tools/browser_manager.py` — 浏览器管理

**做什么**：
- `connect_browser()`：连接本地 Chrome 调试端口（9222），**新开一个独立窗口**执行任务
- `dismiss_interfering_overlays()`：清理页面上的干扰弹窗（浏览器扩展、通知等）
- `cleanup_tabs()`：任务结束后关闭任务窗口，保留用户原有标签
- `find_first()`：给定多个选择器，依次尝试，返回第一个找到的元素

**返回值**：`(ctrl, work, baseline_tab_ids, work_tab_id)`
- `ctrl`：浏览器总控，用于管理标签页
- `work`：任务所在的那个标签页（新开的窗口）
- `baseline_tab_ids`：连接前就存在的标签页 ID（不能关）
- `work_tab_id`：任务标签页的 ID

---

### ⑩ `tools/element_finder.py` — 找按钮

**做什么**：
- `find_element(page, "tiktok", "post_button")`：去 `button_config.json` 里查 tiktok.post_button 的所有"找法"，依次尝试，返回找到的元素
- `add_selector("tiktok", "post_button", "新的找法")`：把新的按钮"找法"插到配置表最前面（被 `fix-selector` 命令调用）
- `load_selectors("tiktok")`：读取 `button_config.json`（带缓存，只读一次）

---

## 四、完整信息流：从上传到 AI 修复

### 4.1 正常上传流程（没有出错）

```
用户输入命令
    │
    ▼
① command_entry.py 接收命令，生成 run_id，分发给对应平台
    │
    ▼
⑤ video_check.py 检查视频文件合法性
    │
    ▼
⑨ browser_manager.py 连接 Chrome，新开一个窗口
    │
    ▼
⑥ tiktok.py（或⑦⑧）开始执行上传步骤：
    │
    │   每一步都调用 ④ repair_engine.py 的 log_step() 记录结果
    │   找按钮时调用 ⑩ element_finder.py → 读 ② button_config.json
    │
    ▼
上传成功 → 关闭任务窗口 → 返回 exit(0)
```

### 4.2 按钮找不到时的 AI 自动修复流程

这是整个项目最核心的机制。当平台改版导致按钮找不到时：

```
第一阶段：脚本发现问题并报告
═══════════════════════════

⑥ tiktok.py 调用 ⑩ element_finder.py 找"发布按钮"
    │
    │  element_finder 去 ② button_config.json 查所有"找法"
    │  → 全部没找到
    │
    ▼
⑥ tiktok.py 调用 ④ repair_engine.py 的 report_failure()
    │
    │  report_failure() 内部做了三件事：
    │  ├─ 1. 运行 JS，提取页面上所有按钮信息（"拍快照"，≤1500字）
    │  ├─ 2. 写 summary.jsonl（500字摘要）+ detail_{run_id}.jsonl（含快照）
    │  └─ 3. 终端输出 DIAG|run_id=abc12|platform=tiktok|step=publish|error=selector_not_found
    │
    ▼
脚本退出（exit 1），终端显示：
    ❌ [publish] 失败 — selector_not_found
    DIAG|run_id=abc12|platform=tiktok|step=publish|error=selector_not_found


第二阶段：AI 读取关键信息 ⭐ AI 介入点
═══════════════════════════════════

AI（Cursor Agent / OpenClaw）看到终端输出的 DIAG| 行
    │
    │  第一步：读摘要，判断错误类型
    │  运行: tail -1 ~/.social_uploader/summary.jsonl
    │  得到: {"run_id":"abc12","platform":"tiktok","failed_at":"publish","error":"selector_not_found",...}
    │  → 判断是 selector_not_found → 可以自动修
    │
    │  第二步：获取修复建议
    │  运行: social-upload suggest-selectors --run-id abc12
    │
    ▼
④ repair_engine.py 的 suggest_selectors() 函数被调用：
    │
    │  1. 读 detail_abc12.jsonl 中保存的 DOM 快照
    │  2. 用 STEP_KEYWORDS 字典做语义匹配：
    │     "publish" 步骤 → 找包含 "post"、"发布"、"submit" 的元素
    │  3. 把匹配到的元素转换成修复命令
    │
    ▼
终端输出（~200字，AI 只需要看这些）：
    STEP: post_button
    PLATFORM: tiktok
    RUN_ONE:
      1. social-upload fix-selector --target tiktok --key post_button --selector "@data-e2e=publish_btn"
      2. social-upload fix-selector --target tiktok --key post_button --selector "text:Post video"


第三阶段：AI 执行修复 ⭐ AI 修改点
═══════════════════════════════

AI 复制第 1 条命令运行：
    social-upload fix-selector --target tiktok --key post_button --selector "@data-e2e=publish_btn"
    │
    ▼
① command_entry.py 路由到 ⑩ element_finder.py 的 add_selector() 函数
    │
    │  add_selector() 做的事：
    │  1. 读 ② button_config.json
    │  2. 在 tiktok.post_button 列表最前面插入 "@data-e2e=publish_btn"
    │  3. 写回 ② button_config.json
    │
    ▼
② button_config.json 被修改（这是唯一被改的文件）：
    "post_button": ["@data-e2e=publish_btn", ...原来的找法...]
                     ↑ 新加的排在最前面，下次优先用


第四阶段：AI 从断点重试
═══════════════════════

AI 运行:
    social-upload tiktok --video "..." --title "..." --description "..." --resume-from publish
    │
    ▼
⑥ tiktok.py 跳过已完成的步骤，从 publish 步骤开始
    │
    │  找"发布按钮"→ ⑩ element_finder.py → ② button_config.json
    │  → 第一个就是刚加的 "@data-e2e=publish_btn" → 找到了！
    │
    ▼
上传成功 🎉
```

### 4.3 AI 修复的约束规则

| 规则 | 说明 |
|------|------|
| **零代码** | AI 全程只运行命令，不写代码、不直接编辑文件 |
| **只改一个文件** | 只改 `button_config.json`，Python 代码一行不动 |
| **最多 3 轮** | 连续修复 3 次仍失败 → 停止，通知用户 |
| **每轮独立** | 每次修复只看最新一轮的日志，不累积上下文 |
| **每轮 ~2.5KB** | summary(500字) + detail(1500字) + 修复输出(500字) |

---

## 五、文件之间的调用关系图

```
用户
 │
 ▼
command_entry.py ─────────────────────────────────────┐
 │                                                     │
 ├─→ uploaders/tiktok.py ──┐                           │
 ├─→ uploaders/instagram.py ├─→ video_check.py         │
 └─→ uploaders/youtube.py ─┘                           │
       │        │        │                              │
       │        │        └─→ repair_engine.py          │
       │        │             │ log_step()              │
       │        │             │ report_failure()        │
       │        │             │   ├─ 写 summary.jsonl   │
       │        │             │   ├─ 写 detail.jsonl    │
       │        │             │   └─ 输出 DIAG|         │
       │        │             │                         │
       │        │             └─→ suggest_selectors()  ←┤ (suggest-selectors 命令)
       │        │                  读 detail → 推荐修复  │
       │        │                                       │
       │        └─→ element_finder.py ─────────────────→┤ (fix-selector 命令)
       │             │ find_element()                    │  add_selector()
       │             │   读 button_config.json           │  写 button_config.json
       │             │                                   │
       │             └─→ browser_manager.py              │
       │                  connect_browser()              │
       │                  find_first()                   │
       │                  dismiss_overlays()             │
       │                                                │
       └─→ error_classifier.py                          │
            classify_error()                            │
            is_agent_fixable()                          │
                                                        │
AI Agent ←── 看到 DIAG| ──→ 运行 suggest-selectors ────┘
         └──────────────→ 运行 fix-selector ────────────┘
         └──────────────→ 运行 --resume-from 重试
```

---

## 六、安全原则

1. **绝不接触用户凭证** — 不保存、不输入、不传输任何账号密码
2. **登录由用户自行完成** — 工具只负责上传，登录环节由用户手动完成
3. **凭证拒绝机制** — 用户提供密码时 Agent 必须拒绝使用
4. **未登录即终止** — 检测到未登录时输出安全提示并 exit(1)
5. **新窗口隔离** — 每次任务在新开的独立窗口中进行，不影响用户已有的标签页

---

## 七、CLI 命令规格

### 7.1 安装方式

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

### 7.2 命令格式

```bash
# 上传
social-upload tiktok    --video "路径" --title "标题" --description "描述" [--cover "封面"] [--no-publish]
social-upload instagram --video "路径" --caption "文案" [--no-publish]
social-upload youtube   --video "路径" --title "标题" --description "描述" [--no-publish]

# 断点恢复
social-upload tiktok --video "..." --title "..." --description "..." --resume-from publish

# 诊断与修复
social-upload diag [--area "CSS选择器"]
social-upload suggest-selectors --run-id {run_id}
social-upload fix-selector --target {平台} --key {按钮名} --selector "找法"
```

### 7.3 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 成功 |
| `1` | 失败 |

### 7.4 终端输出格式

**给人看的（stdout）**：
```
10:30:01 [INFO]   ✅ [login] 完成
10:30:05 [INFO]   ✅ [file_inject] 完成
10:30:12 [ERROR]  ❌ [publish] 失败 — selector_not_found
DIAG|run_id=abc12345|platform=tiktok|step=publish|error=selector_not_found
```

**给 AI 解析的（stderr）**：
```json
{"step":"login","status":"ok"}
{"step":"file_inject","status":"ok"}
{"step":"publish","status":"fail","error":"selector_not_found","detail":"post_button 未找到"}
```

---

## 八、各平台上传步骤

### TikTok（`uploaders/tiktok.py`）

```
视频校验 → 连接浏览器 → 打开上传页 → 登录检测
→ 清理弹窗 → 注入视频文件 → 等待上传完成（含错误检测）
→ 填写标题+描述 → 设置封面（可选）→ 滚动到底部 → 等待版权检查
→ [no_publish 检查] → 点击发布 → 处理二次确认 → 等待发布成功确认
```

### Instagram（`uploaders/instagram.py`）

```
视频校验 → 连接浏览器 → 打开首页 → 登录检测
→ 关闭干扰弹窗 → 点击"新帖"按钮 → 注入视频文件
→ 等待裁剪界面 → 选择原始比例
→ 下一步（裁剪→滤镜）→ 下一步（滤镜→信息填写）
→ 填写文案 → [no_publish 检查] → 点击分享 → 等待发布完成
```

### YouTube（`uploaders/youtube.py`）

```
视频校验 → 连接浏览器 → 打开 YouTube Studio → 登录检测
→ 关闭残留弹窗 → 唤出上传弹窗（快捷图标/创建菜单降级）
→ 注入视频文件 → 填写标题+描述
→ 设置"不面向儿童"（5种策略轮替+验证）→ 循环点击下一步×3
→ [no_publish 检查] → 设置公开可见性 → 点击发布 → 等待发布成功确认
```

---

## 九、依赖

### Python 包

```toml
[project]
name = "social-uploader"
version = "0.1.0"
requires-python = ">=3.9"
dependencies = ["DrissionPage>=4.0"]
```

### 系统要求

- macOS 或 Windows + Google Chrome
- Python >= 3.9
- Chrome 以调试模式启动（端口 9222）
- 用户已在浏览器中手动登录目标平台

---

## 十、AI Agent 操作手册位置

Agent 的完整操作指南在 `.cursor/skills/social-media-uploader/SKILL.md`，它告诉 Agent：
- 什么时候执行上传命令
- 看到 `DIAG|` 时怎么启动修复
- 修复时运行哪些命令、按什么顺序
- 最多修几轮、什么时候放弃通知用户

这个文件本身不是代码，是给 AI 看的"操作手册"。
