#!/usr/bin/env python3
"""log_scanner CLI — 手动触发对话日志扫描"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.utils import fix_windows_encoding

fix_windows_encoding()

from log_scanner.scanner import scan


def main():
    db_path = str(Path.home() / ".local" / "share" / "opencode" / "opencode.db")
    fragments = scan(db_path)

    if not fragments:
        print("[run_scan] No fragments extracted")
        return

    print(f"\n[run_scan] Extracted {len(fragments)} fragments:")
    for i, frag in enumerate(fragments[:5], 1):
        preview = frag["content"][:80].replace("\n", " ")
        tools = "T" if frag["has_tools"] else " "
        fb = "F" if frag["has_feedback"] else " "
        print(f"  {i}. [{tools}{fb}] {preview}...")

    if len(fragments) > 5:
        print(f"  ... and {len(fragments) - 5} more")


if __name__ == "__main__":
    main()
