总体时序（你现在这个版本就用它）
⌨️ 用户按下「结束录音」
   ↓
🎙️ ChatGPT 正在生成转写（~0.2–0.5s）
   ↓
📋【后台】对当前剪贴板做完整快照（一次）
   ↓
📝 转写文本拿到
   ↓
📋 覆盖剪贴板（写入转写文本）
   ↓
⌘V 粘贴到当前输入位置
   ↓
📋 立刻恢复剪贴板（用户原内容）


关键点

快照发生在「等待转写」期间 → 不占用用户可感知时间

粘贴窗口极短 → 无需处理并发剪贴板异常

第一版：全量保存，不做类型筛选

技术边界确认（结论）

✅ 剪贴板快照 & 恢复 100% 在 Python 内完成

❌ 不需要 Accessibility 权限

❌ 不需要 AppleScript 参与剪贴板

✅ AppleScript 只用于 ⌘V

Python 实现（整理后的最终版本）
1️⃣ 依赖
python3 -m pip install pyobjc

2️⃣ 剪贴板快照 / 恢复模块（clipboard_guard.py）
# clipboard_guard.py
from dataclasses import dataclass
from typing import List, Tuple

from AppKit import NSPasteboard


@dataclass
class PasteboardSnapshot:
    """
    Semantic snapshot of NSPasteboard.generalPasteboard().
    Stores (type, raw_bytes) for all materialized types.
    """
    items: List[Tuple[str, bytes]]


def snapshot_clipboard() -> PasteboardSnapshot:
    """
    Take a semantic snapshot of the current clipboard.
    """
    pb = NSPasteboard.generalPasteboard()
    types = pb.types() or []

    items: List[Tuple[str, bytes]] = []

    for t in types:
        data = pb.dataForType_(t)
        if data is None:
            # Some lazy/promised types may not materialize; safe to skip
            continue
        items.append((str(t), bytes(data)))

    return PasteboardSnapshot(items=items)


def restore_clipboard(snapshot: PasteboardSnapshot) -> None:
    """
    Restore clipboard from a previously taken snapshot.
    """
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()

    for t, raw in snapshot.items:
        try:
            pb.setData_forType_(raw, t)
        except Exception:
            # Private / unsupported types may fail — acceptable and expected
            pass


def overwrite_clipboard_with_text(text: str) -> None:
    """
    Replace clipboard contents with plain text.
    """
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.writeObjects_([text])

3️⃣ 触发 ⌘V（AppleScript）
# paste.py
import subprocess

def paste_cmd_v():
    script = r'''
    tell application "System Events"
      keystroke "v" using {command down}
    end tell
    '''
    subprocess.run(["osascript", "-e", script], check=True)

4️⃣ 组合成你的最终调用逻辑
# micpipe_paste_flow.py
import time

from clipboard_guard import (
    snapshot_clipboard,
    restore_clipboard,
    overwrite_clipboard_with_text,
)
from paste import paste_cmd_v


def paste_transcription(transcribed_text: str):
    """
    Final production flow:
    - snapshot clipboard (already done earlier)
    - overwrite clipboard
    - Cmd+V
    - restore clipboard
    """
    # 覆盖剪贴板
    overwrite_clipboard_with_text(transcribed_text)

    # 给系统极短时间同步剪贴板
    time.sleep(0.03)

    # 粘贴
    paste_cmd_v()

    # 再等一会，确保粘贴完成
    time.sleep(0.05)


# ===== 在你的录音流程中这样用 =====

def on_recording_finished_and_waiting_for_transcription():
    """
    用户按下『结束录音』后立即调用
    """
    snapshot = snapshot_clipboard()
    return snapshot


def on_transcription_ready(transcribed_text: str, snapshot):
    """
    ChatGPT 转写结果返回时调用
    """
    try:
        paste_transcription(transcribed_text)
    finally:
        restore_clipboard(snapshot)