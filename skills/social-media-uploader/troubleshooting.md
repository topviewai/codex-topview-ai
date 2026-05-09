# 故障排查

## 连接浏览器失败
- 确认 Chrome 已以调试模式启动：`bash scripts/start_chrome_debug.sh`
- 验证端口：`curl -s http://localhost:9222/json/version`

## 未登录
- 脚本会自动检测登录状态，未登录则 exit(1)
- 请在浏览器中手动访问对应平台完成登录后重试
- 本工具不会处理任何账号密码

## 找不到元素 / 页面结构变化（双轨并行 + 配方三层兜底）

元素查找使用双轨并行机制：
- **轨道 A（快速路径）**：读取 `button_config.json` 选择器列表，1.5s 内快速尝试
- **轨道 B（AI 路径）**：轨道 A 未命中时，`ai_locator.py` 的 UltimateLocator 通过 `platform_semantics.py` 的结构化语义描述 + AgentQL AI API 定位元素（不回写结果，每次基于实时页面状态）
- **失败兜底**：双轨均未命中时输出 `DIAG|` 诊断行，交给 Agent 人工介入

交互配方（定时发布、可见性等）仍使用三层兜底：
- **Tier 1**：按 `state_patterns.json` 中的配方（recipe）执行，使用预定义选择器
- **Tier 2a**：选择器失败时，`dom_heuristic` 用语义关键词启发式搜索替代元素（本地、免费）
- **Tier 2b**：启发式失败时，`agentql_client` 调用 AgentQL AI API 语义定位元素（需 API Key）
- **Tier 3**：全部失败时输出 `DIAG|` 诊断行，交给 Agent 人工介入

### 按钮选择器修复
- Agent 修复全程只需运行命令，不需要编辑任何文件：
  1. `social-upload suggest-selectors --run-id {run_id}` — 获取候选修复命令列表
  2. `social-upload fix-selector --target {平台} --key {按钮名} --selector "..."` — 执行推荐的修复
  3. 用 `--resume-from {步骤}` 从断点重试
- 选择器配置在 `src/social_uploader/button_config.json`

### 交互配方（Recipe）修复
- 可见性、定时发布等复杂交互使用 Recipe 配方系统：
  1. `social-upload show-recipe --target {平台} --recipe {配方名}` — 查看当前配方配置
  2. `social-upload fix-recipe --target {平台} --recipe {配方名} --step {步骤ID} --selector "新选择器"` — 更新某步的选择器
- 配方定义在 `src/social_uploader/state_patterns.json`
- 常用配方名：`schedule_recipe`（定时发布）、`visibility_recipe`（可见性，仅 TikTok）

## DIAG 日志说明
- 脚本每一步都输出结构化 JSON 到 stderr（供自动化解析）
- 失败时写入两层文件到 `~/.social_uploader/`：
  - `summary.jsonl`：一行索引，含错误类型和 detail 文件路径
  - `detail_{run_id}.jsonl`：含 DOM 片段等详细上下文
- 终端中的 `DIAG|` 行是给 Agent 的触发信号，格式：`DIAG|run_id=xxx|platform=xxx|step=xxx|error=xxx`
- 用 `social-upload diag` 子命令可手动提取当前浏览器页面的精简 DOM

## 关于代码
- `src/social_uploader/uploaders/` 是正式版本（CLI 调用的），具备日志和自动修复能力
- 早期独立脚本已归档到 `DrissionPage/_archive/`，不应再使用
- **请始终使用 `social-upload` CLI 命令**

## 切换 Chrome 账号后仍连接旧账号

调试浏览器使用独立的数据目录（`~/.chrome-social-upload`），与日常 Chrome 完全隔离。在日常 Chrome 中切换 Google 账号**不会影响**调试浏览器的登录状态。

**解决方法：**
```bash
# 1. 终止旧的调试浏览器
.venv/bin/social-upload restart-browser

# 2. 重新启动调试浏览器
bash scripts/start_chrome_debug.sh          # macOS
scripts\start_chrome_debug.bat              # Windows

# 3. 在调试浏览器中退出旧账号，登录新账号，然后重新执行上传命令
```

**根因**：`connect_browser()` 通过 `127.0.0.1:9222` 连接调试浏览器。该浏览器有独立的 cookies 和登录状态（存储在 `~/.chrome-social-upload`），不受日常 Chrome 的 Profile 切换影响。要换账号必须在调试浏览器内操作。

## 上传超时
- 检查网络连接
- 检查视频文件大小（过大的文件上传耗时更长）
- 脚本默认等待 60-120 秒，超时后请手动检查浏览器

## CLI 命令找不到
- 确认已安装：`.venv/bin/pip install -e .`
- 确认使用正确的 Python 环境：`.venv/bin/social-upload --help`
