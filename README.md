# TopView AI Codex Plugin Marketplace

Ask Codex to install TopView AI with one message:

```text
请安装 TopView AI Codex 插件：https://github.com/topviewai/codex-topview-ai.git，安装后请提示我重启 Codex。
```

Codex can add this marketplace by running:

```bash
codex plugin marketplace add https://github.com/topviewai/codex-topview-ai.git
```

Then restart Codex if prompted. The `topview-ai` plugin is exposed by `.agents/plugins/marketplace.json`.
