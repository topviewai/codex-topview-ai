# 飞书表格写入

本步骤把 `/tmp/collector_verified.jsonl` 中已经验证的数据写入飞书表格。字段不固定，必须按用户本次采集目标决定表头和列顺序。

---

## 1. 生成行数据

示例：通用采集表格。

```bash
SKILL_DIR="$HOME/.codex/skills/multi-platform-content-collector"

python3 - <<'PY'
import json
rows = []
with open('/tmp/collector_verified.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        rows.append([
            d.get('platform', 'N/A'),
            d.get('title') or d.get('source') or d.get('author', 'N/A'),
            d.get('author') or d.get('creator', 'N/A'),
            d.get('date', 'N/A'),
            d.get('metric') or d.get('likes') or d.get('views') or d.get('score') or 'N/A',
            d.get('url', 'N/A'),
            d.get('summary') or d.get('insight') or d.get('reason') or d.get('prompt') or '',
        ])
print(f'Loaded {len(rows)} verified rows')
with open('/tmp/rows.json', 'w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False)
PY
```

如果用户要的是提示词库，可把最后一列换成 `prompt`，表头使用“完整提示词”。

---

## 2. 创建表格

按本次字段创建表头，例如：

```bash
lark-cli sheets +create --as user \
  --title "<关键词> 多平台数据采集" \
  --headers '["平台","标题/来源","作者","发布时间","指标","链接","摘要/发现"]'
```

记录返回的 `url`，然后获取 `sheet_id`：

```bash
lark-cli sheets +info --url "<URL>" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(data['data']['sheets']['sheets'][0]['sheet_id'])"
```

---

## 3. 写入数据

```bash
python3 "$SKILL_DIR/scripts/write_rows.py" "<URL>" "<sheet_id>" /tmp/rows.json
```

脚本会逐行写入，避免长文本被截断，并支持失败重试。

---

## 4. 写后验证

```bash
lark-cli sheets +read --as user --url "<URL>" --sheet-id "<sheet_id>"
```

检查：

- 行数 = `/tmp/rows.json` 中的行数。
- 关键字段不为空。
- 长文本末尾没有被截断。

如有缺失行，用 `start_index` 参数断点续写：

```bash
python3 "$SKILL_DIR/scripts/write_rows.py" "<URL>" "<sheet_id>" /tmp/rows.json <失败行索引>
```
