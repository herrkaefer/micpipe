<img src="assets/logo.png" width="256">

# MicPipe 

Current version: `v1.5.1`


[English](README.md)

> ⚠️ **持续迭代中**：基础功能已验证可用，但部分边界情况与稳定性仍需完善。欢迎反馈意见、提交代码贡献，也欢迎点个 Star。

> **提示**：使用前请先在 Chrome 里正常登录 ChatGPT，以确保内置听写功能可用。

## 简介

MicPipe 是一个 macOS 小应用，让你能够直接在任何应用程序中使用 ChatGPT 网页版的语音输入功能。

[📺 查看演示视频](demo/demo1.mp4)


### 主要功能
- **听写支持两种触发方式**：既可以**按住说话**，也可以**点击开关**
- **听写后的 AI Pipe**：语音转写后，可自动通过预设 Prompt 让 AI 进行润色、改写或翻译，例如语法修正、邮件写作、编程指令整理等
- **听写直连 AI 模式**：不使用预设 Prompt，直接把说出的内容交给 AI，适合临时提问或自由指令
- **可编辑的听写预设槽位**：你可以自定义最多 5 个常用的 AI 处理方式，并直接在菜单中切换
- **实时语音对话**：按 **Control + Fn** 即可进入 ChatGPT 的 realtime voice conversation。再次按 **Fn** 或 **Esc** 结束对话
- **可自定义的听写快捷键**：直接在菜单中选择你喜欢的触发键（默认为 Fn）
- **不可见专属窗口**：服务在独立的隐藏 Chrome 窗口中运行，减少闪动并避免干扰日常浏览
- **Esc 可取消听写**：录音中按 **Esc** 可取消，且不会粘贴任何内容
- **设置自动保存**：你的所有偏好设置（服务选择、快捷键、自定义 Prompt 等）会自动保存，下次启动无需重新配置
- **剪贴板保护**：粘贴完成后自动恢复你原有的剪贴板内容

### 它是怎么工作的

MicPipe 本身并不实现语音识别或语音对话引擎。它的做法是维持一个指向 ChatGPT 的隐藏专属 Chrome 窗口，然后以编程方式去点击你平时手动会点的那两个 ChatGPT 按钮：

- **Dictate**：一次性语音转文字
- **Voice**：实时语音对话

这就是这个应用的核心思路：直接复用 ChatGPT 现有网页 UI 的能力，再用一个轻量的 macOS 菜单栏应用和全局快捷键把它变成系统范围可用的工具。

<img src="demo/chatgpt-ui.png" width="900" alt="ChatGPT 输入框右侧的 Dictate 和 Voice 按钮">

MicPipe 负责的则是这些外围工作：管理隐藏窗口、在合适的时候触发正确的按钮、把转写结果粘贴回当前应用，以及恢复原有剪贴板内容。


## 运行环境

- macOS 10.14+
- Python 3.11+
- Google Chrome（需开启 JavaScript from Apple Events，见下方说明）

## 快速开始

### 方式 1：脚本启动（推荐）
双击 **`MicPipe.command`**。该脚本会在启动应用后自动关闭终端窗口，是确保权限正常的最可靠方式。

### 方式 2：手动启动
```bash
uv sync
uv run python micpipe.py
```

## 安装与运行

### 1. 安装依赖

- Python 3.11+
- Google Chrome
- `uv`（Python 包管理器）

然后初始化项目环境：

```bash
uv sync
```

### 2. 配置 Chrome（重要）

在 Chrome 中开启 **允许 Apple Events 执行 JavaScript**：

1. 打开 Chrome
2. 点击菜单栏 **View（视图）** → **Developer（开发者）** → **Allow JavaScript from Apple Events（允许 Apple Events 执行 JavaScript）**
3. 确保该选项被勾选 ✓

> ⚠️ 如果看不到此选项，请确保使用的是完整版 Google Chrome（非 Chromium）。

### 3. 启动应用

- **MicPipe.command**：双击启动，在后台运行后会自动关闭终端窗口（推荐方式）。
- **终端启动**：运行 `uv run python micpipe.py`。

> **首次运行提示**：由于这是未签名应用，macOS 可能会拦截。如果双击没反应，请在 `MicPipe.command` 上**右键点击 -> 打开**，然后在弹窗中再次点击**打开**即可。

## 使用方法

MicPipe 使用 **Fn 键**触发录音，支持两种操作方式：

### Hold 模式（按住说话）

1. **按住 Fn** 开始录音（菜单栏图标变红）
2. 开始说话...
3. **松开 Fn** 停止录音并开始转写
4. 转写完成后自动粘贴到原应用

### Toggle 模式（点击开关）

1. **快速点击 Fn** 开始录音
2. 开始说话...
3. **再次点击 Fn** 停止录音并开始转写
4. 转写完成后自动粘贴到原应用

### 语音对话（仅限 ChatGPT）

1. 按 **Control+Fn** 即可与 ChatGPT 进行实时语音对话
2. ChatGPT 会通过语音回复你，无需文字粘贴
3. 再次按下 **Fn** 或按 **Esc** 结束对话

> ⚠️ 语音对话需要 **ChatGPT Plus**，且仅在服务选择为 ChatGPT 时可用。

### 语音 CLI

如果你想通过 **快捷指令** 或 **Siri** 控制语音对话，可以使用 CLI：

```bash
uv run micpipe voice start
uv run micpipe voice stop
uv run micpipe voice toggle
```

做自动化时建议优先使用 **`start`** / **`stop`**，因为它们是幂等的；`toggle` 更适合手动脚本或兼容现有热键语义。

如果你想在 macOS **快捷指令** 里接给 **Siri**，最简单的配置是：

1. 建两个快捷指令：分别命名为 `Start ChatGPT Voice` 和 `Stop ChatGPT Voice`
2. 在每个快捷指令里添加 **运行 Shell 脚本**
3. 脚本可以写成这样：

```bash
cd path-to-micpipe
path-to-micpipe/.venv/bin/python path-to-micpipe/micpipe.py voice start
```

停止语音对话则改成：

```bash
cd path-to-micpipe
path-to-micpipe/.venv/bin/python path-to-micpipe/micpipe.py voice stop
```

4. 之后可以直接对 Siri 说这两个快捷指令的名字

这些命令要求 MicPipe 主进程已经在菜单栏中运行。

### 取消录音

- 录音过程中按 **Esc** 键可取消当前录音
- 取消后不会粘贴任何文字

### 菜单栏图标状态

- 🎙️ 麦克风图标：待机中
- 🔴 红色脉动：录音中 / 听写进行中
- 🟣 紫色语音动画：ChatGPT 实时语音对话进行中
- ⚙️ 圆圈图标：转写中

点击菜单中选项可开关提示音。

<p align="left">
  <img src="demo/screenshot-menu-ai-pipe.png" width="600" alt="AI Pipe">
</p>


### 自定义快捷键

您现在可以直接通过菜单选择您喜欢的触发键：

1. 点击菜单栏的 **MicPipe** 图标。
2. 找到 **Hotkey** 菜单项。
3. 从支持的按键中选择：**Fn**、**左/右 Option** 或 **左/右 Shift**。

设置会自动保存并立即生效。
 
## AI Pipe (AI 二次处理)

AI Pipe 让你可以在粘贴之前，先让 AI 处理你的语音转写结果。比如自动修正语法、改写成正式邮件、或者整理成代码指令。

> ⚠️ **注意**：目前 AI Pipe (包括对话模式和预设 Prompt) 仅支持 **ChatGPT** 服务。Gemini 服务目前仅支持原始语音转文字。

### 使用方式

1. 点击菜单栏 **MicPipe** 图标 → **AI Pipe**
2. 选择你想要的处理方式：
   - **Off**: 关闭 AI 处理，直接输出原始转写文字
   - **Conversation Mode (对话模式)**: 把你说的话直接发给 AI，适合提问或下达复杂指令
   - **Slot 1-5 (预设 Prompt)**: 使用预先设定好的 Prompt 处理你的语音

### 自定义你的预设 Prompt

你可以根据自己的需求，修改 5 个预设 Prompt (提示词) 的标题和内容：

1. 在 **AI Pipe** 菜单中，将鼠标悬停在想要修改的预设上
2. 点击 **✎ Edit...**
3. 在弹出的编辑器中修改 **标题** 和 **Prompt 内容**
4. 点击保存，下次录音就会使用新的设置

## 服务切换 (ChatGPT / Gemini)

您可以通过菜单栏随时切换使用的转写服务：

1. 点击菜单栏的 **MicPipe** 图标。
2. 找到 **Service** 菜单项。
3. 选择 **ChatGPT** 或 **Gemini**。

- **ChatGPT**：支持完整功能，包括 Esc 取消。
- **Gemini**：支持语音转录，但由于 Gemini 网页版的技术限制，目前暂不支持通过 **Esc** 键取消录音。

## 权限说明（重要）

首次运行需要授予以下权限：

### 1. 辅助功能（必需）

- **用途**：监听 Fn 热键、模拟 `Cmd+V` 粘贴
- **设置位置**：系统设置 → 隐私与安全性 → 辅助功能
- 将运行 MicPipe 的终端应用（如 Terminal、iTerm2）添加到列表并勾选

### 2. 自动化 > Google Chrome（必需）

- **用途**：通过 AppleScript 控制 Chrome 中的 ChatGPT 标签页
- **设置位置**：系统设置 → 隐私与安全性 → 自动化
- 确保终端应用对 Google Chrome 的控制权限已开启

### 3. 麦克风（Chrome 内必需）

- **用途**：ChatGPT 听写功能需要麦克风权限
- **设置位置**：首次使用 ChatGPT 听写时，Chrome 会弹出权限请求，请点击允许

## 技术原理（简要）

- 在开始录音时记录当前前台应用。
- 一个按键两种动作：**按住 Fn** 录音（按住模式），**松开 Fn** 停止并转写。
- 通过 AppleScript/JavaScript 控制 Chrome 的 ChatGPT 标签页：
  - 点击 “Dictate” 开始
  - 点击 “Submit Dictation” 停止并获取文本
  - 按 Esc 时点击 “Stop Dictation” 取消
- 恢复原应用焦点，模拟 `Cmd+V` 粘贴文字。
- 开启时会播放短促的 WAV 提示音。

### 为何采用此路线？

在开发过程中，我们尝试过多种技术方案，最终选择了目前的 AppleScript 桥接方案：
- **方案 A：CDP (Chrome DevTools Protocol)** —— 失败。ChatGPT 具有极强的反爬虫检测，使用 CDP 会触发 Cloudflare 的人机验证（Turnstile），导致核心功能无法工作。
- **方案 B：Headless 模式（如 Puppeteer/Playwright）** —— 失败。最大的障碍是 **无法获取麦克风权限** 进行语音输入，且同样面临被识别人机验证的问题。

**最终方案**：通过 AppleScript 控制用户日常使用的 Google Chrome。
- **优势**：利用真实的浏览器环境和已有的登录 Session，完美绕过人机屏蔽，且能直接使用浏览器已有的麦克风权限。
- **局限性**：由于严重依赖 macOS 特有的 AppleScript 和 Quartz API，本项目目前**无法跨平台**。在 Linux 或 Windows 上需要参照类似的自动化原理进行独立实现。

## 兼容性

- macOS 10.14+
- Python 3.11+
- Google Chrome

## 开源协议

本项目采用 **GNU General Public License v3 (GPLv3)** 开源协议。详情请参阅 [LICENSE](LICENSE) 文件。
