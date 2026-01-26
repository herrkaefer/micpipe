# MicPipe

[English](README.md)

## 简介

MicPipe 是一个 macOS 菜单栏应用，通过 Chrome 里的 ChatGPT 听写界面把语音转成文字，然后粘贴回你原本正在使用的应用。

### 主要功能
- 一个按键两种模式：**按住说话** 或 **点击开关**
- 录音中按 **Esc** 可取消听写（不会粘贴）
- 开始/结束提示音可在菜单中开关
- 自动返回原应用并粘贴结果
- 如果从 ChatGPT 页面启动录音，文本保留在 ChatGPT 输入框内

## 运行环境

- macOS 10.14+
- Python 3.11+
- Google Chrome（需开启 JavaScript from Apple Events，见下方说明）

## 快速开始（uv）

```bash
uv run python main.py
```

## 安装与运行

### 1. 安装依赖

- Python 3.11+
- Google Chrome
- `uv`（Python 包管理器）

### 2. 配置 Chrome（重要）

在 Chrome 中开启 **允许 Apple Events 执行 JavaScript**：

1. 打开 Chrome
2. 点击菜单栏 **View（视图）** → **Developer（开发者）** → **Allow JavaScript from Apple Events（允许 Apple Events 执行 JavaScript）**
3. 确保该选项被勾选 ✓

> ⚠️ 如果看不到此选项，请确保使用的是完整版 Google Chrome（非 Chromium）。

### 3. 启动应用

```bash
uv run python main.py
```

首次运行时请按提示授予权限。

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

### 取消录音

- 录音过程中按 **Esc** 键可取消当前录音
- 取消后不会粘贴任何文字

### 菜单栏图标状态

- 🎙️ 麦克风图标：待机中
- 🔴 红色脉动：录音中
- ⚙️ 圆圈图标：转写中

点击菜单中选项可开关提示音。

### 自定义快捷键

当前快捷键硬编码为 **Fn**（keycode 63）。如需更改，请编辑 `main.py` 第 31 行：

```python
TRIGGER_KEY_CODE = 63  # 修改此值，代码注释中列出了常用键码
```

> 暂不支持通过菜单修改快捷键。

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
