# 社交媒体数据简报

> 生成时间: {{ generated_at }}  |  分析周期: 最近 {{ period_days }} 天

{% set ns = namespace(total_views=0, total_likes=0, total_comments=0, platform_count=0) %}
{% for platform, data in platforms.items() %}
{% set ns.platform_count = ns.platform_count + 1 %}
{% set ns.total_views = ns.total_views + (data.metrics.get('views', 0) | float) %}
{% set ns.total_likes = ns.total_likes + (data.metrics.get('likes', 0) | float) %}
{% set ns.total_comments = ns.total_comments + (data.metrics.get('comments', 0) | float) %}
{% endfor %}

---

## 一、下一步创作建议

{% if advice.summary %}
> {{ advice.summary }}
{% endif %}

{% if advice.recommended_topics %}
### 推荐主题
{% for topic in advice.recommended_topics %}
{{ loop.index }}. {{ topic }}
{% endfor %}
{% endif %}

{% if advice.content_format %}
### 内容形式
{{ advice.content_format }}
{% endif %}

{% if advice.title_hooks %}
### 标题参考
{% for hook in advice.title_hooks %}
- {{ hook }}
{% endfor %}
{% endif %}

{% if advice.publish_schedule %}
### 发布节奏
{{ advice.publish_schedule }}
{% endif %}

{% if advice.improvements %}
### 改进方向
{% for item in advice.improvements %}
- {{ item }}
{% endfor %}
{% endif %}

---

## 二、关键发现

{% if highlights %}
{% for h in highlights[:3] %}
- ✅ {{ h }}
{% endfor %}
{% endif %}
{% if warnings %}
{% for w in warnings[:3] %}
- ⚠️ {{ w }}
{% endfor %}
{% endif %}
{% if not highlights and not warnings %}
- 📊 已采集 {{ ns.platform_count }} 个平台数据，暂无显著异动
{% endif %}

---

## 三、数据总览

{% for platform, data in platforms.items() %}
### {{ platform | upper }}

| 指标 | 当前值 | 变化 |
|------|--------|------|
{% for metric, info in data.trend.items() %}
| {{ metric_label(metric) }} | {{ info.current | format_number }} | {{ trend_arrow(info.change_pct) }} |
{% endfor %}

{% if data.engagement_rate is not none %}
**互动率**: {{ data.engagement_rate }}%
{% endif %}

{% endfor %}

{% set cross = build_cross_platform_summary(platforms) %}
{% if cross %}
### 跨平台对比

| 指标 |{% for p in platforms %} {{ p | upper }} |{% endfor %}

|------|{% for p in platforms %}--------|{% endfor %}

{% for row in cross %}
| {{ row.metric }} |{% for p in platforms %} {{ row['values'].get(p, '-') }} |{% endfor %}

{% endfor %}
{% endif %}

{% if publish_cadence.total_uploads > 0 %}
### 发布节奏

| 项目 | 数值 |
|------|------|
| 周期内上传次数 | {{ publish_cadence.total_uploads }} |
| 成功 / 失败 | {{ publish_cadence.successful_uploads }} / {{ publish_cadence.failed_uploads }} |
{% if publish_cadence.avg_interval_days %}
| 平均发布间隔 | {{ publish_cadence.avg_interval_days }} 天 |
{% endif %}
{% for p, count in publish_cadence.by_platform.items() %}
| {{ p }} 上传次数 | {{ count }} |
{% endfor %}
{% endif %}

---

## 四、内容表现

{% for platform, data in platforms.items() %}
{% if data.videos.ranked %}
{% set cols = detect_video_columns(data.videos.ranked) %}
{% set display_cols = cols[:6] %}
### {{ platform | upper }} 视频详情 (共 {{ data.videos.count }} 条)

| # | 标题 |{% for c in display_cols %} {{ video_metric_label(c) }} |{% endfor %} 标记 |
|---|------|{% for c in display_cols %}--------|{% endfor %}------|
{% for v in data.videos.ranked %}
| {{ loop.index }} | {{ v.title | truncate(40) }} |{% for c in display_cols %} {{ v.get(c) | format_number }} |{% endfor %} {% if v in data.videos.hits %}🔥 爆款{% elif v in data.videos.flops %}⚠️ 低迷{% endif %} |
{% endfor %}

{% if data.videos.mean_views is defined %}
> 平均播放量: {{ data.videos.mean_views | format_number }}  |  爆款阈值: > 均值 {{ hit_threshold }}x  |  低迷阈值: < 均值 {{ flop_threshold }}x
{% endif %}

{% if data.videos.hits %}
**🔥 爆款视频** (播放 > 均值 {{ hit_threshold }}x):
{% for v in data.videos.hits %}
- {{ v.title }} ({{ v.views | format_number }} 播放)
{% endfor %}
{% endif %}

{% if data.videos.flops %}
**⚠️ 低迷视频** (播放 < 均值 {{ flop_threshold }}x):
{% for v in data.videos.flops %}
- {{ v.title }} ({{ v.views | format_number }} 播放)
{% endfor %}
{% endif %}
{% endif %}
{% endfor %}

{% if highlights %}
### 亮点

{% for h in highlights %}
- ✅ {{ h }}
{% endfor %}
{% endif %}

{% if warnings %}
### 预警

{% for w in warnings %}
- ⚠️ {{ w }}
{% endfor %}
{% endif %}

---

*报告由 social-upload monitor 自动生成 | 建议来源: {{ advice.source | default("rules") }}*
