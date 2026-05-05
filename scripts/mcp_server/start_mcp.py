#!/usr/bin/env python3
"""Mnemosyne MCP Server 启动入口"""
from pathlib import Path
import sys

server_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(server_dir))

from __init__ import main

if __name__ == "__main__":
    main()
