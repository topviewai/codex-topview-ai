---
name: seedance2-prompt-writer
description: "Use when the user needs a Seedance 2.0 video prompt, video script, storyboard, shot list, AI video generation prompt, or prompt rewrite before generating with TopView. 包含6种模板、10条黄金法则、8大题材套路、完整创作流程、常见错误避坑、专业术语速查。"
---

# Seedance 2.0 提示词/脚本创作指南

基于 626 条优秀提示词案例总结的实战创作方法论。

## 创作流程（9步，约10分钟）

1. **明确创意核心**（10秒）— 一句话卖点是什么？
2. **选模板**（30秒）— 从6种模板中选最合适的，不确定就选模板A
3. **设全局参数**（1分钟）— 风格 + 技术参数 + 时长 + 情绪
4. **搭场景**（2分钟）— 地点 + 光线 + 天气 + 氛围，要极度具体
5. **定角色**（1分钟）— 外貌 + 服装 + 情绪，有参考图用 @Image1 锁定
6. **编分镜**（3-5分钟）— 时间戳逐镜头：景别 + 运镜 + 动作 + SFX
7. **打磨结尾**（1分钟）— 定格/拉远/反转/循环，要有记忆点
8. **加负面提示**（30秒）— no subtitles, no text overlays, no watermark
9. **检查角色一致性**（30秒）— Identity Lock 语句

## 6种模板

根据题材选择模板。详见 [templates.md](references/templates.md)。

| 模板 | 适用场景 | 核心特征 |
|------|---------|---------|
| A. 电影级分镜叙事 | 90%通用需求 | 时间戳分镜 + 景别运镜 + SFX |
| B. JSON结构化 | 品牌广告、产品展示 | JSON字段：scene/style/camera/lighting |
| C. FPV飞行穿越 | 古迹/城市/微观/科幻穿越 | 一段话 + 逗号堆叠视觉元素 |
| D. Beat-Synced节奏 | MV、动作序列 | BPM + 逐拍镜头 |
| E. 一镜到底 | 超现实变形、环境穿越 | one continuous shot 句式 |
| F. 中文分镜脚本 | 换装/情感/脱口秀 | 【风格】【场景】【角色】+ 镜头N |

## 10条黄金法则

1. **开头2秒定生死** — 第一镜必须有视觉冲击
2. **一个提示词只做一件事** — 聚焦单一核心创意
3. **动词驱动，非形容词** — "Camera dives" > "beautiful landscape"
4. **物理细节 = 真实感** — water splash, dust, hair flowing, fabric stretching
5. **色彩逻辑要声明** — "Color Grade: ochre to blood-red to gold"
6. **相机行为要具体** — "slow orbit, low angle rising to eye level" > "camera moves"
7. **结尾要有记忆点** — Freeze Frame / Pull-back / Twist / Loop
8. **中英混合效果最佳** — 中文写意图，英文写术语
9. **反差制造爆点** — 古装+电竞、老太太+说唱
10. **先短后长** — 50词验证方向 → 再写完整分镜

## 6大共性（优秀提示词必备）

1. **结构化分层**：全局设定 → 环境场景 → 角色主体 → 动作时间线
2. **时间戳分镜**：`[0:00-0:03] Shot 1:` 格式，80%优秀作品使用
3. **感官叠加**：视觉 + 听觉SFX + 触觉暗示 + 动态物理
4. **负面提示**：明确写"不要什么"
5. **Identity Lock**：@Image + "maintain identical facial features throughout"
6. **极度具象化**：❌"漂亮衣服" → ✅"蓝色飘逸盘领襕衫，佩戴职业电竞耳机"

## 题材套路速查

根据题材选择对应套路。详见 [genres.md](references/genres.md)。

## 常见错误

详见 [mistakes.md](references/mistakes.md)。

## 术语速查

详见 [glossary.md](references/glossary.md)。

## 推荐提示词长度

- 200-500词是"甜蜜区"（足够详细但不冗余）
- FPV/幽默类可短至50-150词
- 分镜脚本/商业广告可长至500+词
