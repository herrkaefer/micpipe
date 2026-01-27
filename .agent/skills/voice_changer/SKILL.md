---
name: voice_changer
description: 使用 FFmpeg 和 Rubberband 滤镜修改视频中的音频音调（Pitch）和语速（Tempo），使其听起来不同于原生。
---

# Voice Changer Skill

此 Skill 允许用户通过 FFmpeg 修改视频的音频特性，特别适用于需要对演示视频进行脱敏或改变解说声音音色的场景。

## 核心功能
- **修改音调 (Pitch)**: 独立调整音高，不影响语速。
- **修改语速 (Tempo)**: 独立调整语速，不影响音高。
- **自动转码**: 无论输入格式如何，统一输出为兼容性最佳的 MP4 (H.264 + AAC)。

## 使用指南

### 1. 环境要求
确保系统中已安装支持 `rubberband` 的 FFmpeg：
```bash
/usr/local/bin/ffmpeg -filters | grep rubberband
```

### 2. 标准操作
将视频音频调低（大叔音，推荐值 0.85）：
```bash
/usr/local/bin/ffmpeg -i input.mov -filter:a "rubberband=pitch=0.85,aresample=44100" -c:v libx264 -preset fast -crf 22 -c:a aac -y output.mp4
```

将视频音频调高（柯南音/年轻化，推荐值 1.15）：
```bash
/usr/local/bin/ffmpeg -i input.mov -filter:a "rubberband=pitch=1.15,aresample=44100" -c:v libx264 -preset fast -crf 22 -c:a aac -y output.mp4
```

### 3. 参数说明
- `pitch`: 音调比例。大于 1.0 为高音，小于 1.0 为低音。
- `tempo`: 语速比例。默认 1.0。
- `aresample=44100`: 关键步骤，确保音频流在变换后依然完整且同步。

## 故障排除
- **后面没声音了**: 确保使用了 `aresample` 滤镜。
- **听不清内容**: 避免使用过极端的 `pitch` 值（推荐范围 0.7 - 1.3）。
