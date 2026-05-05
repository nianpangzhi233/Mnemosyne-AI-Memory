#!/usr/bin/env python3
"""公共工具：Windows 编码修复 + HF_HUB_OFFLINE"""

import os
import sys


def fix_windows_encoding():
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            os.environ['PYTHONIOENCODING'] = 'utf-8'


def ensure_hf_offline():
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
