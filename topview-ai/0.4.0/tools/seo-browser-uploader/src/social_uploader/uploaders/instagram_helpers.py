"""Instagram 平台专属辅助函数（不含步骤编排）。

【架构约定】
- `tools/` = 全平台通用基础设施
- `uploaders/instagram_helpers.py` = Instagram 专属辅助（仅 instagram.py 可 import）
- `uploaders/instagram.py` = 步骤编排器（不写底层逻辑）

禁止跨平台 import：tiktok.py / youtube.py 不得 import 本模块。

【现状】
Instagram 上传流程目前不包含 schedule/visibility 等需要复杂 recipe 的环节
（IG Web 不支持 schedule，且无可见性控制），主流程已能用 `find_element` + 直接
click 完成全部步骤，故本模块暂无需迁移函数。

【何时往这里加函数】
- 需要 JS 注入操作 Instagram 特定 UI（如 Reels 专属按钮、Story 编辑面板）
- 引入 IG 专属 recipe（如未来 Meta 上线 IG 定时发布）
- 出现 Instagram Shadow DOM / iframe 适配（如 Threads 集成的内嵌组件）
- 平台特定的状态检测或重试策略

【禁止往这里加】
- 通用工具（应放 tools/）
- TikTok / YouTube 共用的逻辑（应放 tools/ 或保留各自的 helpers）
- 步骤编排（应留在 instagram.py）
"""

import logging

logger = logging.getLogger(__name__)

# 暂无函数。新增时请遵循上方约定。
