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
    """Take a semantic snapshot of the current clipboard."""
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
    """Restore clipboard from a previously taken snapshot."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()

    for t, raw in snapshot.items:
        try:
            pb.setData_forType_(raw, t)
        except Exception:
            # Private / unsupported types may fail -- acceptable and expected
            pass


def overwrite_clipboard_with_text(text: str) -> None:
    """Replace clipboard contents with plain text."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.writeObjects_([text])
