# MiMo Vision MCP Server

为 Claude Code 提供图片识别能力的 MCP 服务器，解决 **MiMo v2.5 Pro 不支持多模态** 的问题。

## 问题背景

MiMo 系列中，支持图片输入的模型只有：

- `mimo-v2.5`
- `mimo-v2-omni`

**`mimo-v2.5-pro` 不支持图片识别。**

当你在 Claude Code 中使用 `mimo-v2.5-pro` 作为主模型时，如果直接发送图片（比如拖入截图、粘贴报错截图），Claude Code 会尝试把图片发给模型，触发类似以下错误：

```
There's an issue with the selected model (mimo-v2.5-pro[1m]).
It may not exist or you may not have access to it.
Run /model to pick a different model.
```

**更严重的是，这个错误会导致当前会话直接崩溃，之后连普通文本对话也无法继续。**

## 三种解决办法

| 方案 | 做法 | 优点 | 缺点 |
|------|------|------|------|
| 治标 | `/compact` 压缩上下文 | 快速恢复会话 | 压缩后仍不能发图片，且会丢失上下文 |
| 治头 | 换成 `mimo-v2.5` 模型 | 原生支持图片 | 性能远不如 Pro，代码生成能力下降 |
| **治本** | **安装本 MCP 服务器** | **兼顾 Pro 性能 + 图片识别** | 需要额外配置一次 |

## 本方案原理

```
用户发送图片
    ↓
Claude Code（mimo-v2.5-pro）—— 不直接处理图片
    ↓ 调用 MCP 工具
MiMo Vision MCP Server
    ↓ 转发给支持视觉的模型
mimo-2.5（支持多模态）—— 返回文字描述
    ↓
Claude Code 拿到文字描述，继续正常对话
```

主模型保持 `mimo-v2.5-pro` 的高性能，图片识别通过 MCP 借助 `mimo-2.5` 完成，互不干扰。

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/gbz666/mimo-vision-mcp.git
cd mimo-vision-mcp
```

### 2. 安装依赖

```bash
cd mcp-servers/mimo-vision
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 配置环境变量

环境变量会从两个地方读取（优先级从高到低）：

1. **Claude Code settings.json 的 `env` 字段**（推荐）—— MCP 进程启动时自动注入，无需手动设置系统变量
2. **系统环境变量** —— 如果 settings.json 中未配置，则 fallback 到系统环境变量

可配置项：

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `MIMO_API_KEY` | 是 | - | MiMo API Key |
| `MIMO_API_BASE` | 否 | `https://token-plan-cn.xiaomimimo.com/anthropic` | API 地址 |
| `MIMO_MODEL` | 否 | `mimo-2.5` | 视觉模型名称 |

> 建议搭配 [ccswitch](https://github.com/gbz666/ccswitch) 一起使用，方便快速切换 API Key 和模型配置。

### 4. 注册 MCP 服务器

编辑 Claude Code 配置文件 `~/.claude/settings.json`，在 `mcpServers` 字段中添加：

```json
{
  "mcpServers": {
    "mimo-vision": {
      "command": "python",
      "args": ["C:/Users/<你的用户名>/.claude/mcp-servers/mimo-vision/mimo_vision.py"],
      "env": {
        "MIMO_API_KEY": "your-api-key"
      }
    }
  }
}
```

重启 Claude Code 即可生效。

## 提供的工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `describe_image` | 分析图片并返回文字描述 | `image_path`（路径/URL/data URI）、`prompt`（提问，默认"描述图片内容"） |
| `ocr_image` | 提取图片中的文字（OCR） | `image_path`（路径/URL/data URI）、`language`（语言，默认"中英文"） |

### 使用示例

在 Claude Code 中直接说：

```
帮我看看这张截图的内容：D:\screenshots\error.png
```

Claude Code 会自动调用 `describe_image` 工具，无需手动指定。

## 重要：配置系统级提示词

**仅安装 MCP 服务器还不够。** 如果不加提示词约束，Claude Code 在遇到图片时仍可能尝试用 Read 工具直接读取图片，触发模型报错导致会话崩溃。

**必须**在全局提示词文件 `~/.claude/CLAUDE.md` 中加入以下规则：

```markdown
# 图片读取规则

当模型为 mimov2.5pro 时，读取图片必须优先使用 mimo-vision MCP 提供的 `mcp__mimo-vision__describe_image` 或 `mcp__mimo-vision__ocr_image` 工具，不要用 Read 工具直接读取图片。
```

> 为什么是全局 `~/.claude/CLAUDE.md` 而不是项目级？因为这个问题与具体项目无关，只要主模型是 `mimo-v2.5-pro`，任何项目都会遇到。放在全局配置中才能保证所有项目生效。

## 已知限制：VS Code 终端无法直接拖入图片

目前 **没有找到办法** 解决 VS Code 终端直接拖入图片识别的问题。

在 VS Code 终端中拖入图片后，Claude Code 会尝试将图片直接发给主模型处理（而不是通过 MCP），触发如下错误：

```
❯ [Image #1]
[image content]

● There's an issue with the selected model (mimo-v2.5-pro[1m]).
It may not exist or you may not have access to it.
Run /model to pick a different model.
```

**替代方案：** 先将图片保存到本地文件，然后告诉 Claude 图片路径，Claude 会通过 mimo-vision MCP 工具进行识别。

```
帮我看看这张截图：D:\screenshots\error.png
```

> 根本原因是 Claude Code 在终端拖入图片时会直接将图片内联发送给模型，绕过了 MCP 工具调用流程，目前无法拦截或重定向。

## 依赖

- Python 3.10+
- `mcp>=1.0.0`
- `httpx>=0.27.0`

