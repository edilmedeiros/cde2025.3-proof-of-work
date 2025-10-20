#!/usr/bin/env python3

import sys
import csv
import hashlib
from pathlib import Path

OUTPUT_PATH = Path("solutions/exercise02-sample.txt")

txs = [
    "9919d4db3c0c32cfc19c6ffa32496f18bf28607d941fd7b89a5710031c43f599",
    "c63f430c09237dd7e43c31cb88512059416ef4c8fcd9134296ca6a919d185982",
    "7270b580dec8b8ae6fdb28d8260de1932f8355823b5758b0e95d5ed8cf7d041c",
    "03cd616cbb55a17f78bbe0c263f76c1007f9cd848f5c32a699b8805b9e436119",
    "4c50e3dad7f98bceb6441f96b23748dea84fbdb7cedd603441e6ea4a574d04a6",
]


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def merkle_root_be_hex(txids_be_hex: list[str]) -> str:
    level = [bytes.fromhex(tx) for tx in txids_be_hex]  # leaves in LE bytes
    if not level:
        fail("Cannot compute Merkle root of empty list.")
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        nxt = []
        for i in range(0, len(level), 2):
            nxt.append(sha256(level[i] + level[i + 1]))
        level = nxt
    return level[0].hex()  # back to BE hex


def build_parent_level(level: list[bytes]) -> list[bytes]:
    nodes = level[:]
    if len(nodes) % 2 == 1:
        nodes.append(nodes[-1])
    parents = []
    for i in range(0, len(nodes), 2):
        parents.append(sha256(nodes[i] + nodes[i + 1]))
    return parents


def build_inclusion_proof(txs_be: list[str], required_be: str) -> tuple[str, list[str]]:
    """Return (root_be_hex, proof_be_list) for the required txid."""
    try:
        idx = txs_be.index(required_be)
    except ValueError:
        fail(f"Required txid not found in tx list: {required_be}")

    # Prepare leaf level (LE bytes)
    level = [bytes.fromhex(tx) for tx in txs_be]
    current = level[idx]  # LE
    current_index = idx
    proof_be: list[str] = []

    # Walk up the tree, recording sibling at each level (in BE hex for output)
    while len(level) > 1:
        size = len(level)
        print("")
        print(f"level: {[tx.hex() for tx in level]}")
        print(f"size: {size}")
        print(f"current_index: {current_index}")
        print(f"current: {current.hex()}")
        # If odd and we're the last, sibling is ourselves (duplicated)
        if size % 2 == 1 and current_index == size - 1:
            sib = level[current_index]
        else:
            sib_index = current_index ^ 1  # pair index
            if sib_index >= size:
                sib_index = size - 1
            sib = level[sib_index]
        print(f"sib: {sib.hex()}")

        # Record sibling as BE hex for the output file
        proof_be.append(sib.hex())
        print(f"proof_be: {proof_be}")

        # Compute parent using left/right order
        if size % 2 == 1 and current_index == size - 1:
            parent = sha256(current + sib)  # duplicate of self
        else:
            if current_index % 2 == 0:  # current is LEFT
                parent = sha256(current + sib)
            else:  # current is RIGHT
                parent = sha256(sib + current)

        # Move to parent level
        parent_level = build_parent_level(level)
        current_index //= 2
        # Sanity check
        if parent != parent_level[current_index]:
            fail("Internal mismatch while ascending the tree.")
        level = parent_level
        current = parent

    root_be_hex = current.hex()
    return root_be_hex, proof_be


def main():
    txs_be = txs
    print(f"Input: {txs}")
    required_be = "7270b580dec8b8ae6fdb28d8260de1932f8355823b5758b0e95d5ed8cf7d041c"
    root_be, proof_be = build_inclusion_proof(txs, required_be)

    # Cross-check by full recompute
    recomputed = merkle_root_be_hex(txs_be)
    if recomputed != root_be:
        fail(
            f"Root mismatch after full recompute.\nFrom proof: {root_be}\nFull: {recomputed}"
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        f.write(root_be + "\n")
        for h in proof_be:
            f.write(h + "\n")

    print(f"Wrote {OUTPUT_PATH} with {1 + len(proof_be)} line(s).")
    print(f"Merkle root: {root_be}")
    print(f"Proof length: {len(proof_be)}")


if __name__ == "__main__":
    main()
