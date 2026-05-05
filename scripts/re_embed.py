#!/usr/bin/env python3
"""re_embed.py — 全量重嵌入脚本

用 Harrier (或指定 Embedder) 重新编码所有节点的向量。
旧向量（BGE-M3）将被替换，不可逆。会先备份 graph.db。

用法：
    python scripts/re_embed.py                    # 用 Harrier 重嵌入
    python scripts/re_embed.py --embedder bge-m3  # 用 BGE-M3 重嵌入
    python scripts/re_embed.py --dry-run          # 只看数量不执行
"""

import os
import shutil
import sys
import time

from pathlib import Path

import numpy as np
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "graph.db"
SCRIPTS_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(SCRIPTS_DIR))

from core.utils import fix_windows_encoding, ensure_hf_offline

fix_windows_encoding()
ensure_hf_offline()


def create_embedder(name: str):
    sys.path.insert(0, str(SCRIPTS_DIR))
    from core.embedder import BgeM3Embedder, HarrierEmbedder
    if name == "harrier":
        return HarrierEmbedder()
    elif name == "bge-m3":
        return BgeM3Embedder()
    else:
        raise ValueError(f"Unknown embedder: {name}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Re-embed all nodes")
    parser.add_argument("--embedder", default="harrier", choices=["harrier", "bge-m3"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=16)
    args = parser.parse_args()

    print(f"\n{'='*50}")
    print(f"  Mnemosyne 重嵌入工具")
    print(f"  Embedder: {args.embedder}")
    print(f"  Dry run: {args.dry_run}")
    print(f"{'='*50}\n")

    if not DB_PATH.exists():
        print("❌ graph.db 不存在")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM nodes WHERE vector IS NOT NULL")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM nodes")
    all_nodes = cur.fetchone()[0]
    print(f"  总节点: {all_nodes}，有向量: {total}\n")

    if total == 0:
        print("无需重嵌入")
        conn.close()
        return

    if args.dry_run:
        print(f"  [DRY RUN] 将重嵌入 {total} 个节点")
        conn.close()
        return

    # 备份
    backup_path = DB_PATH.with_suffix(f".db.bak-{int(time.time())}")
    print(f"  📦 备份 → {backup_path.name}")
    conn.close()
    shutil.copy2(str(DB_PATH), str(backup_path))

    # 加载 embedder
    print(f"  ⏳ 加载 {args.embedder} 模型...")
    embedder = create_embedder(args.embedder)
    dim = embedder.get_dimension()
    print(f"  ✅ 模型加载完成，维度={dim}\n")

    # 分批读取+重嵌入+写回
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT id, content FROM nodes WHERE vector IS NOT NULL")
    rows = cur.fetchall()

    done = 0
    errors = 0
    t0 = time.time()

    for i in range(0, len(rows), args.batch_size):
        batch = rows[i:i + args.batch_size]
        ids = [r[0] for r in batch]
        texts = [r[1] for r in batch]

        try:
            vectors = embedder.encode_batch(texts)
        except Exception as e:
            print(f"  ❌ 批次 {i//args.batch_size} 编码失败: {e}")
            # 逐条降级
            for nid, text in batch:
                try:
                    vec = embedder.encode(text)
                    blob = vec.astype(np.float32).tobytes()
                    cur.execute("UPDATE nodes SET vector=? WHERE id=?", (blob, nid))
                    done += 1
                except Exception as e2:
                    print(f"  ❌ 节点 {nid[:8]} 失败: {e2}")
                    errors += 1
            conn.commit()
            continue

        for nid, vec in zip(ids, vectors):
            blob = vec.astype(np.float32).tobytes()
            cur.execute("UPDATE nodes SET vector=? WHERE id=?", (blob, nid))
            done += 1

        conn.commit()

        elapsed = time.time() - t0
        rate = done / elapsed if elapsed > 0 else 0
        print(f"  📊 {done}/{total} ({done*100//total}%) — {rate:.1f} nodes/s", end='\r')

    print()
    conn.commit()
    conn.close()

    # 更新 meta
    conn = sqlite3.connect(str(DB_PATH))
    model_name = "microsoft/harrier-oss-v1-0.6b" if args.embedder == "harrier" else "BAAI/bge-m3"
    conn.execute("UPDATE meta SET value=? WHERE key=?", (model_name, "embedding_model"))
    conn.commit()
    conn.close()

    elapsed = time.time() - t0
    print(f"\n{'='*50}")
    print(f"  ✅ 重嵌入完成")
    print(f"  成功: {done}，失败: {errors}，耗时: {elapsed:.1f}s")
    print(f"  备份: {backup_path.name}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
