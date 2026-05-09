"""平台语义配置 — 为每个平台的按钮/元素定义结构化语义描述。

供 UltimateLocator 使用，通过 container + target 父子约束提高 AI 定位精度。
每个 key 对应 button_config.json 中的同名 key。
"""

PLATFORM_SEMANTICS = {
    "tiktok": {
        "file_input": {
            "container": "upload page main area",
            "target": "file input element for video upload",
        },
        "caption_box": {
            "container": "video editor form",
            "target": "contenteditable text input for title and description",
        },
        "post_button": {
            "container": "editor bottom action bar",
            "target": "red publish or post button to submit video",
        },
    },
    "instagram": {
        "create_button": {
            "container": "left sidebar navigation",
            "target": "create new post button or plus icon with svg",
        },
        "file_input": {
            "container": "create post dialog or overlay",
            "target": "hidden file input element for media upload",
        },
        "select_from_computer": {
            "container": "create post dialog",
            "target": "select from computer button to trigger file picker",
        },
        "next_button": {
            "container": "create post dialog header",
            "target": "next step button to proceed in post creation flow",
        },
        "caption_box": {
            "container": "create post dialog final step",
            "target": "write a caption text area or contenteditable div",
        },
        "share_button": {
            "container": "create post dialog header",
            "target": "share or publish button to submit the post",
        },
    },
    "youtube": {
        "upload_icon": {
            "container": "top header bar",
            "target": "upload video icon or camera plus icon",
        },
        "create_button": {
            "container": "top header bar",
            "target": "create button to open upload menu",
        },
        "upload_menu_item": {
            "container": "create dropdown menu",
            "target": "upload videos menu item",
        },
        "file_input": {
            "container": "upload dialog",
            "target": "hidden file input element for video upload",
        },
        "title_box": {
            "container": "upload dialog details form",
            "target": "title textbox input with id textbox",
        },
        "desc_box": {
            "container": "upload dialog details form",
            "target": "description textbox input for video description",
        },
        "next_button": {
            "container": "upload dialog bottom navigation",
            "target": "next button to proceed to next step",
        },
        "done_button": {
            "container": "upload dialog bottom navigation",
            "target": "done or publish button to finalize upload",
        },
        "close_buttons": {
            "container": "upload dialog header",
            "target": "close or dismiss button to close dialog",
        },
    },
}


def get_semantic_query(platform, key):
    """返回语义字典，未配置时返回降级字典。

    Args:
        platform: 平台名（tiktok/instagram/youtube）
        key: 元素 key（如 post_button、file_input）

    Returns:
        {"container": "...", "target": "..."}
    """
    platform_dict = PLATFORM_SEMANTICS.get(platform, {})
    if key in platform_dict:
        return platform_dict[key]
    return {"container": "page", "target": key.replace("_", " ")}
