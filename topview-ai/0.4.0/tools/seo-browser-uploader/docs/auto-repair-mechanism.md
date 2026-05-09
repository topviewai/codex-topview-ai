# 自动修复机制说明（给人看的版本）

## 这是什么？

当 TikTok / Instagram / YouTube 更新了网页界面，导致上传脚本找不到按钮时，
系统会自动尝试修复，**不需要人去改代码**。

---

## 用大白话讲，修复过程就三步：

### 第一步：脚本发现「按钮找不到了」

比如 TikTok 把发布按钮的代码从 `post_video_button` 改成了 `publish_btn`。

脚本用旧的名字去找 → 找不到 → 脚本做三件事：
1. **拍快照**：把当前页面上所有按钮的信息记下来（像拍了张照片）
2. **记笔记**：把"我在找哪个按钮"（`selectors_tried`）写到日志里，这样后面分析快照时就知道该匹配哪种按钮
3. **喊一声**：在终端输出一行 `DIAG|...`，意思是"我这里出问题了"

### 第二步：AI 看到出错，问系统「该怎么修」

AI 运行一条命令：
```
social-upload suggest-selectors --run-id xxx
```

系统自动做这些事：
1. 翻出刚才拍的快照
2. 从日志里找到"我在找哪个按钮"（`selectors_tried`，比如 `post_button`）
3. 看看快照里哪个按钮长得像"发布按钮"（比如上面写着"发布"两个字）
4. 把找到的按钮信息**翻译成脚本能用的格式**
5. 直接输出一条可以复制运行的修复命令

### 第三步：AI 运行修复命令，然后重试

```
social-upload fix-selector --target tiktok --key post_button --selector "@data-e2e=publish_btn"
social-upload tiktok --video "..." --title "..." --resume-from publish
```

修复命令会把新的按钮名字写进配置文件，然后脚本从断点继续跑。

---

## 涉及哪些文件？各自干什么？

```
src/social_uploader/
│
├── button_config.json      ← 📋 "通讯录"：记录每个平台每个按钮怎么找
│                              修复时唯一被改的文件
│                              你手动改这里也行
│
├── tools/
│   ├── element_finder.py   ← 🔍 "找按钮的人"（双轨并行）：
│   │                          - find_element(): 轨道 A 快速选择器 → 轨道 B AI 语义定位
│   │                          - find_and_click(): 找到并点击，带点击后状态检查
│   │                          - add_selector(): 往通讯录里添加新按钮名字（供 CLI 修复用）
│   │
│   ├── ai_locator.py     ← 🧠 "AI 大脑"（轨道 B 核心）：
│   │                          - UltimateLocator: 页面预热 + 结构化语义查询 + 视觉校验
│   │                          - 调用 agentql_client.py 的 API，不回写结果
│   │
│   └── platform_semantics.py ← 📖 "语义字典"：
│                                每个平台每个按钮的结构化描述（container + target）
│                                供 UltimateLocator 提高 AI 定位精度
│
├── repair_engine.py       ← 📸 "拍照 + 分析照片的人"：
│                              - report_failure(): 出错时拍页面快照、写日志（含 selectors_tried）
│                              - suggest_selectors(): 读取 selectors_tried → 分析快照 → 推荐修复方案
│                              - get_dom_snippet(): 拍快照的具体方法
│                              - STEP_KEYWORDS: "发布按钮长什么样"的知识库（用 selectors_tried 查找）
│
├── error_classifier.py     ← 🏷️ "分类标签"：
│                              判断这个错误是 AI 能自己修的，
│                              还是需要通知用户的
│
└── command_entry.py        ← 🚪 "前台接待"：
                               - suggest-selectors 命令入口
                               - fix-selector 命令入口
```

---

## 如果你要改东西，改哪里？

### 场景 1：平台加了新按钮，你想提前加上去

改 **`button_config.json`**，在对应平台下加一条：

```json
"tiktok": {
    "新按钮名": ["用什么方式去找它"]
}
```

### 场景 2：自动推荐的修复不准，想调整"发布按钮长什么样"的判断

改 **`repair_engine.py`** 里的 `STEP_KEYWORDS` 字典：

```python
STEP_KEYWORDS = {
    "post_button": ["post", "publish", "发布", "submit"],  ← 加关键词
    ...
}
```

意思是：如果页面上某个按钮的文字/属性里包含这些词，就认为它可能是发布按钮。

### 场景 3：想加一种新的错误类型

改 **`error_classifier.py`**：

```python
ERROR_TYPES = {
    "新错误名": "agent_fix",      # AI 自己修
    "另一个错误": "notify_user",  # 通知用户
}
```

### 场景 4：想改修复命令的输出格式

改 **`repair_engine.py`** 里的 `suggest_selectors()` 函数末尾，那里拼接输出文本。

### 场景 5：想改"怎么把新按钮名写进配置"的逻辑

改 **`tools/element_finder.py`** 里的 `add_selector()` 函数。

---

## 整个流程一张图

```
TikTok/Instagram/YouTube 改了界面
         │
         ▼
button_config.json 里的旧按钮名 → 轨道 A 找不到
         │
         ▼
element_finder.py 自动切换到轨道 B（AI 语义定位）
         │
         ├─→ ai_locator.py 预热页面 + 结构化语义查询
         ├─→ platform_semantics.py 提供 container + target 约束
         └─→ agentql_client.py 调用 AgentQL API 定位
                │
         ┌──── ▼ ────┐
         │ 轨道 B 成功 │ → 直接返回元素，不回写配置
         └──── │ ────┘
               │
         ┌──── ▼ ────┐
         │ 轨道 B 失败 │ → 进入 DIAG 修复流程
         └──── │ ────┘
               │
               ▼
tiktok.py 调用 repair_engine.py 的 report_failure()
         │
         ├─→ 拍页面快照（get_dom_snippet）
         ├─→ 写日志文件到 ~/.social_uploader/
         └─→ 终端输出 DIAG| 信号
                │
                ▼
         AI 看到 DIAG|
                │
                ▼
         AI 运行 suggest-selectors 命令
                │
                ▼
         repair_engine.py 分析快照 + 推荐修复方案
                │
                ▼
         AI 运行 fix-selector 命令
                │
                ▼
         element_finder.py 把新按钮名写进 button_config.json
                │
                ▼
         AI 用 --resume-from 重试 → 成功！
```

## 日志文件在哪？

```
~/.social_uploader/
├── summary.jsonl           ← 每次失败一行摘要（哪个平台、哪个步骤、什么错误）
└── detail_abc12345.jsonl   ← 具体这次失败的详情（含页面快照）
```

这些文件会自动生成，不需要你手动创建。
