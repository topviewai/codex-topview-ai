# social-uploader

社交媒体视频自动上传 CLI 工具，支持 TikTok / Instagram / YouTube。

基于 [DrissionPage](https://drissionpage.cn) 浏览器自动化，连接本地 Chrome 调试端口完成上传操作。

---

## 快速安装

### macOS

```bash
cd 项目根目录
bash scripts/install.sh
```

### Windows

```cmd
cd 项目根目录
scripts\install.bat
```

> **Windows 注意**：离线 wheel 包为 macOS 版本，Windows 安装时需要联网下载依赖（脚本会自动从 PyPI 下载）。

<details>
<summary>手动安装（如一键脚本出错）</summary>

**macOS:**
```bash
cd 社交媒体skill
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install ./DrissionPage
.venv/bin/pip install -e .
.venv/bin/social-upload --help
```

**Windows:**
```cmd
cd 社交媒体skill
python -m venv .venv
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install .\DrissionPage
.venv\Scripts\pip install -e .
.venv\Scripts\social-upload --help
```
</details>

## 前置条件

1. **Google Chrome** 浏览器已安装
2. **Python 3.9+**
   - macOS: `brew install python@3.10` 或从 python.org 下载
   - Windows: 从 [python.org](https://www.python.org/downloads/) 下载，安装时勾选 **Add Python to PATH**

## 使用方式

### 第一步：启动 Chrome 调试模式

| 系统 | 命令 |
|------|------|
| macOS | `bash scripts/start_chrome_debug.sh` |
| Windows | 双击 `scripts\start_chrome_debug.bat` 或在命令行执行 |

### 第二步：在浏览器中手动登录目标平台

本工具不接触任何账号密码，需要你自己先登录。

### 第三步：上传视频

**macOS:**
```bash
# TikTok
.venv/bin/social-upload tiktok --video "视频.mp4" --title "标题" --description "描述"

# TikTok 定时发布
.venv/bin/social-upload tiktok --video "视频.mp4" --title "标题" --description "描述" --schedule "2026-04-10 15:00"

# Instagram
.venv/bin/social-upload instagram --video "视频.mp4" --caption "文案 #hashtag"

# YouTube
.venv/bin/social-upload youtube --video "视频.mp4" --title "标题" --description "描述"

# YouTube 定时发布 + 不公开列出
.venv/bin/social-upload youtube --video "视频.mp4" --title "标题" --description "描述" --schedule "2026-04-10 15:00" --visibility unlisted

# 仅填表单不发布
.venv/bin/social-upload tiktok --video "视频.mp4" --title "标题" --description "描述" --no-publish
```

**Windows:**
```cmd
:: TikTok
.venv\Scripts\social-upload tiktok --video "视频.mp4" --title "标题" --description "描述"

:: TikTok 定时发布
.venv\Scripts\social-upload tiktok --video "视频.mp4" --title "标题" --description "描述" --schedule "2026-04-10 15:00"

:: Instagram
.venv\Scripts\social-upload instagram --video "视频.mp4" --caption "文案 #hashtag"

:: YouTube
.venv\Scripts\social-upload youtube --video "视频.mp4" --title "标题" --description "描述"

:: YouTube 定时发布 + 不公开列出
.venv\Scripts\social-upload youtube --video "视频.mp4" --title "标题" --description "描述" --schedule "2026-04-10 15:00" --visibility unlisted

:: 仅填表单不发布
.venv\Scripts\social-upload tiktok --video "视频.mp4" --title "标题" --description "描述" --no-publish
```

> **定时发布说明**：`--schedule` 使用的是平台内置的定时发布功能（视频立即上传，到设定时间自动公开），不是系统级定时任务。

## 在 Cursor 中使用（Skill 模式）

本项目包含 Cursor Agent Skill 定义（`.cursor/skills/social-media-uploader/SKILL.md`）。

在 Cursor 中打开本项目后，直接对 AI 说：

> "帮我把桌面上的 vlog.mp4 上传到 TikTok，标题叫'周末探店'"

AI 会自动检测操作系统并调用对应命令完成上传。

## 项目结构

```
项目根目录/
├── pyproject.toml                      # 包定义 + 依赖
├── README.md                           # 本文件
│
├── src/social_uploader/                # 【正式代码】CLI 包
│   ├── command_entry.py                # 命令入口（接收指令、分发任务）
│   ├── repair_engine.py              # 日志记录 + 自动修复引擎
│   ├── error_classifier.py            # 错误分类（判断 AI 能否自修）
│   ├── button_config.json             # 按钮配置表（修复时只改这里）
│   ├── state_patterns.json            # 状态信号 + 交互配方（recipe）
│   ├── profiles/
│   │   └── default.json               # 默认上传配置
│   ├── uploaders/                      # 各平台上传逻辑
│   │   ├── __init__.py                 # 公共工具函数（should_skip 等）
│   │   ├── video_check.py              # 视频文件校验 + 登录提示
│   │   ├── tiktok.py
│   │   ├── instagram.py
│   │   └── youtube.py
│   └── tools/
│       ├── browser_manager.py          # 浏览器管理（连接 + 新窗口 + 清弹窗）
│       ├── element_finder.py           # 找按钮 + 加按钮
│       ├── upload_profile.py           # 上传配置加载、合并与约束校验
│       ├── pattern_checker.py          # 状态信号检测（成功/失败/弹窗）
│       ├── recipe_runner.py            # 交互配方执行器（三层兜底）
│       ├── agentql_client.py            # AgentQL AI 语义元素发现（Tier 2b）
│       └── dom_heuristic.py           # 启发式 DOM 元素发现（Tier 2a）
│
├── scripts/                            # 所有脚本
│   ├── install.sh                      # macOS 一键安装
│   ├── install.bat                     # Windows 一键安装
│   ├── start_chrome_debug.sh           # macOS Chrome 调试模式启动
│   ├── start_chrome_debug.bat          # Windows Chrome 调试模式启动
│   ├── verify_code.py                  # 代码修改后自动化验证（P0+P1 检查）
│   └── test_logic.py                   # 全链路模拟测试（117 项检查点）
│
├── docs/                               # 文档
│   ├── 项目规划文档.md                   # 项目规划与结构说明
│   └── 自动修复机制说明.md               # 自动修复原理（通俗版）
│
├── DrissionPage/                       # DrissionPage 库源码（仅作依赖安装，勿在此运行脚本）
│   ├── DrissionPage/                   # 库本体
│   └── setup.py
│
├── .cursor/rules/                      # AI Agent 全局规则
│   └── task-orchestration.mdc          # 任务调度（意图路由 + 多 Skill 编排）
│
└── .cursor/skills/                     # AI Agent 指令
    ├── social-media-uploader/          # 社交媒体上传 Skill
    │   ├── SKILL.md
    │   ├── examples.md
    │   ├── troubleshooting.md
    │   └── platforms/                  # 各平台配置项说明
    ├── auto-repair/                    # 自动修复 Skill
    │   └── SKILL.md
    ├── code-rules/                     # 代码规范 Skill
    │   └── SKILL.md
    ├── code-review/                    # 代码修改后验证 Skill
    │   └── SKILL.md
    └── topview-skill/                  # AI 内容生成 Skill（视频/图片/配音）
        ├── SKILL.md
        └── scripts/                    # Topview API 脚本
```

## 故障排查

| 问题 | macOS | Windows |
|------|-------|---------|
| Python 未找到 | `brew install python@3.10` | 从 python.org 下载，安装时勾选 Add to PATH |
| Chrome 连接失败 | `bash scripts/start_chrome_debug.sh` | 双击 `scripts\start_chrome_debug.bat` |
| 依赖安装失败 | 检查网络，或手动 `pip install ./DrissionPage` | 确保联网，Windows 需在线安装依赖 |
| 上传按钮找不到 | 平台 UI 可能更新，用 `social-upload suggest-selectors` 修复 | 同左 |
| `python3` 命令不存在 (Windows) | — | Windows 使用 `python` 而非 `python3` |
