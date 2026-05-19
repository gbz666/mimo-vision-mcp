#!/usr/bin/env python3
"""
MiMo Vision MCP Server
通过MiMo 2.5视觉API处理图片，返回文本描述。
适用于不支持多模态的模型（如MiMo 2.5 Pro）借助视觉模型识图。
"""

import base64
import mimetypes
import os
import sys
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

# ============ 配置 ============
API_KEY = os.environ.get("MIMO_API_KEY", "")
API_BASE = os.environ.get("MIMO_API_BASE", "https://token-plan-cn.xiaomimimo.com/anthropic")
DEFAULT_MODEL = os.environ.get("MIMO_MODEL", "mimo-2.5")

# ============ 初始化 ============
mcp = FastMCP("mimo-vision")


def _resolve_image_path(image_path: str) -> Path:
    """解析图片路径，支持绝对路径和相对路径"""
    p = Path(image_path)
    if p.is_absolute():
        return p
    return Path.cwd() / p


def _detect_media_type(file_path: Path) -> str:
    """根据文件扩展名检测MIME类型"""
    ext = file_path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    if ext in mime_map:
        return mime_map[ext]
    guessed, _ = mimetypes.guess_type(str(file_path))
    return guessed or "image/png"


def _is_data_uri(s: str) -> bool:
    return s.startswith("data:image/")


def _is_url(s: str) -> bool:
    return s.startswith("http://") or s.startswith("https://")


def _build_content_block(image_path: str, prompt: str, media_type: str, data_b64: str) -> dict:
    """构造Anthropic Messages API格式的content block"""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": data_b64,
        },
    }


def _prepare_image(image_path: str) -> tuple[dict, str]:
    """
    准备图片数据，返回 (content_block, media_type)。
    支持: 本地路径、URL、data URI
    """
    if _is_data_uri(image_path):
        # data:image/jpeg;base64,...
        parts = image_path.split(",", 1)
        header = parts[0]  # data:image/jpeg;base64
        data_b64 = parts[1] if len(parts) > 1 else ""
        media_type = header.split(";")[0].split(":")[1] if ":" in header else "image/png"
        return _build_content_block(image_path, "", media_type, data_b64), media_type

    if _is_url(image_path):
        # URL - 下载后转base64
        resp = httpx.get(image_path, timeout=30, follow_redirects=True)
        resp.raise_for_status()
        media_type = resp.headers.get("content-type", "image/png").split(";")[0].strip()
        data_b64 = base64.b64encode(resp.content).decode("utf-8")
        return _build_content_block(image_path, "", media_type, data_b64), media_type

    # 本地文件
    resolved = _resolve_image_path(image_path)
    if not resolved.exists():
        raise FileNotFoundError(f"图片文件不存在: {resolved}")

    media_type = _detect_media_type(resolved)
    data_b64 = base64.b64encode(resolved.read_bytes()).decode("utf-8")
    return _build_content_block(image_path, "", media_type, data_b64), media_type


def _call_mimo_api(image_block: dict, prompt: str, model: str) -> str:
    """调用MiMo API（Anthropic Messages格式）"""
    if not API_KEY:
        return "错误: 未设置 API Key，请设置环境变量 MIMO_API_KEY"

    url = f"{API_BASE.rstrip('/')}/v1/messages"
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    image_block,
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }

    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Anthropic格式: content[].text
            blocks = data.get("content", [])
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    except httpx.HTTPStatusError as e:
        return f"API请求失败 ({e.response.status_code}): {e.response.text}"
    except httpx.RequestError as e:
        return f"网络请求异常: {e}"


# ============ MCP Tools ============


@mcp.tool()
def describe_image(image_path: str, prompt: str = "请详细描述这张图片的内容") -> str:
    """
    使用MiMo 2.5视觉模型分析图片并返回文字描述。
    当主模型不支持图片输入时，用此工具获取图片信息。

    Args:
        image_path: 图片路径（绝对路径或相对路径）、URL或data URI
        prompt: 对图片的提问或指令，默认描述图片内容
    """
    try:
        image_block, _ = _prepare_image(image_path)
        model = DEFAULT_MODEL
        return _call_mimo_api(image_block, prompt, model)
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"处理失败: {type(e).__name__}: {e}"


@mcp.tool()
def ocr_image(image_path: str, language: str = "中英文") -> str:
    """
    提取图片中的文字内容（OCR）。
    适用于截图、文档照片、代码截图等。

    Args:
        image_path: 图片路径、URL或data URI
        language: 图片中的语言，默认中英文
    """
    prompt = f"请提取这张图片中的所有文字内容，保持原始排版。如果包含{language}，请准确识别。只输出文字内容，不要额外描述。"
    try:
        image_block, _ = _prepare_image(image_path)
        return _call_mimo_api(image_block, prompt, DEFAULT_MODEL)
    except FileNotFoundError as e:
        return str(e)
    except Exception as e:
        return f"处理失败: {type(e).__name__}: {e}"


# ============ 启动 ============

if __name__ == "__main__":
    mcp.run()
