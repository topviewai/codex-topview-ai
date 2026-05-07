# 6种提示词写作模板

## 模板A：电影级分镜叙事（最通用，成功率最高）

**适用**：90% 的视频创作需求

**结构**：
```
[风格声明] Ultra-realistic cinematic, 8K, ARRI Alexa, 50mm lens
[时长] 15 seconds
[场景] 具体环境 + 光线 + 天气 + 氛围
[角色] 外貌 + 服装 + 情绪，@Image1 锁脸
[分镜]
[00:00-03:00] Shot 1: 景别 + 运镜 + 动作 + SFX
[03:00-06:00] Shot 2: ...
[06:00-10:00] Shot 3: ...（高潮）
[10:00-15:00] Shot 4: ...（收尾/记忆点）
```

**示例**：
```
Ultra-realistic cinematic, 8K, ARRI Alexa Mini, 35mm anamorphic lens. 15 seconds.

SCENE: Rain-slicked Tokyo street at night, neon signs reflecting on wet pavement, steam rising from manhole covers. Volumetric fog, low-key lighting.

CHARACTER: @Image1 — A woman in her 30s, short black hair, red wool coat, focused expression.

[0:00-0:03] CU — Her eyes snap open. Rack focus from raindrops on glass to her face. SFX: heartbeat.
[0:03-0:07] MS tracking shot — She walks through frozen crowd. Camera orbits 180°.
[0:07-0:11] WS crane up — City reveals itself. Golden light breaks through clouds.
[0:11-0:15] ECU her hand — She snaps fingers. SMASH CUT to black. SFX: thunderclap.

Maintain identical facial features throughout. No subtitles, no text overlays.
```

## 模板B：JSON 结构化（商业/广告级）

**适用**：品牌广告、高端产品展示

**结构**：
```json
{
  "visual_style": "Cinematic, photorealistic, premium feel",
  "duration": "15 seconds",
  "color_palette": "Deep navy, gold accents, warm highlights",
  "camera_movement": "Slow orbit transitioning to push-in",
  "lighting_mood": "Soft studio lighting with rim light separation",
  "main_subject": "产品/角色描述",
  "background_setting": "环境描述",
  "scene_description": [
    {"time": "0:00-0:05", "action": "...", "camera": "...", "sfx": "..."},
    {"time": "0:05-0:10", "action": "...", "camera": "...", "sfx": "..."},
    {"time": "0:10-0:15", "action": "...", "camera": "...", "sfx": "..."}
  ],
  "audio_cue": "Ambient electronic, builds to crescendo",
  "negative": "no text, no watermark, no subtitles"
}
```

## 模板C：FPV 飞行穿越

**适用**：古迹穿越、城市航拍、微观世界、科幻场景

**核心句式**：
```
Extremely fast-paced cinematic FPV flying through [场景], hyper-realistic, 4K, [光线条件], [视觉元素逗号堆叠], epic scale, volumetric lighting, continuous movement, no cuts
```

50-150词即可。速度感 + 视觉堆叠 + continuous movement 收尾。

**示例**：
```
Extremely fast-paced cinematic FPV drone shot flying through an ancient Chinese temple complex at golden hour, hyper-realistic, 4K, weaving between red pillars, swooping under curved rooftops, diving through incense smoke, skimming over koi ponds, rushing past stone lion guardians, volumetric god rays through lattice windows, cherry blossom petals swirling in the wake, epic scale, continuous forward movement
```

## 模板D：Beat-Synced 多镜头节奏

**适用**：MV、节奏感强的短片、动作序列

**结构**：
```
FORMAT: 15s / [BPM] / [镜头数] SHOTS / beat-synced

SUBJECT: 角色描述
WARDROBE: 服装
ENVIRONMENT: 环境
MOOD: 情绪基调
MUSIC: 音乐风格
COLOR LOGIC: 色彩方案

SHOT 1 — [景别+焦距+运镜] / [动作] / [SFX]
SHOT 2 — ...
SHOT N — ...
```

## 模板E：一镜到底（One-Shot）

**适用**：超现实变形、环境穿越、连续叙事

**核心句式**：
```
A cinematic [时长]-second [题材] in one continuous shot. Start with [开场]. The camera [运镜]. [动作发展]. Final beat: [结尾/反转].
```

**示例**：
```
A cinematic 15-second surreal transformation in one continuous shot. Start with a close-up of a woman's eye reflecting a city skyline. The camera slowly pulls back revealing her face is made of crumbling concrete. As pieces fall away, butterflies emerge from the cracks. The camera orbits as her entire form dissolves into a swarm of luminescent butterflies. Final beat: they converge into the shape of a door, which opens to blinding white light. No cuts, no text.
```

## 模板F：中文分镜脚本

**适用**：中文创作者，换装、情感、脱口秀等垂类

**结构**：
```
【风格】超写实电影级 / 电影类型 / 画幅比例 / 光线氛围
【时长】15秒
【场景】具体环境描述
【角色】角色名@图片1（外貌/服装描述）

镜头1（0-3秒）：景别 + 拍法 + 动作描述
镜头2（3-6秒）：景别 + 拍法 + 动作描述
镜头3（6-10秒）：景别 + 拍法 + 动作描述
镜头4（10-15秒）：景别 + 拍法 + 收尾
```

**示例**：
```
【风格】超写实电影级 / 武侠奇幻 / 2.39:1宽画幅 / 暮色逆光
【时长】15秒
【场景】深圳人才公园湖畔，夕阳西下，湖面金光粼粼
【角色】女主@图片1（身穿蓝色飘逸盘领襕衫，佩戴电竞耳机，手持发光长剑）

镜头1（0-3秒）：特写，女主缓缓睁眼，瞳孔中倒映剑光。镜头从湖面极速拉起。
镜头2（3-7秒）：全景俯拍，女主凌空跃起，飞剑化为漫天剑雨席卷而去。
镜头3（7-12秒）：中景跟拍，女主在剑雨中旋转舞剑，每击带起金色弧光。
镜头4（12-15秒）：超远景，女主悬浮湖面之上，万剑归鞘，画面定格。
```
