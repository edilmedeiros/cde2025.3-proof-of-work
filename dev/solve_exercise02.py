#!/usr/bin/env python3
"""
Generate a valid solution for Assignment 3 - Exercise 2.

Reads:
- solutions/exercise01.txt : newline-separated txids (big-endian hex), block order
- data/coinbase_txid.txt   : (optional) first non-empty line is coinbase txid (big-endian)
- REQUIRED_TXID env var    : (optional) required txid (big-endian)
- data/required_txid.txt   : (fallback) first non-empty line is required txid (big-endian)

Writes:
- solutions/exercise02.txt : line1 = Merkle root (big-endian hex),
                             subsequent lines = proof siblings (big-endian hex), leaf->root

This code mirrors the grader's logic:
- Internal nodes are little-endian bytes; parent = sha256d(left || right)
- Duplicate last node when level has an odd count
"""

from pathlib import Path
import sys
import hashlib

TX_LIST_PATH = Path("data/ex02_txid_list.txt")
REQUIRED_TXID = "49ff8cccf1ca12179e9ae7a4760f550b5a18401b27e1e057604e27c3e10c08fb"
OUTPUT_PATH = Path("solutions/exercise02.txt")


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def validate_hex(h: str, bytelen: int, kind: str) -> None:
    h = h.strip().lower()
    if len(h) != 2 * bytelen:
        fail(f"{kind} must be {bytelen} bytes ({2 * bytelen} hex chars), got {len(h)}.")
    try:
        bytes.fromhex(h)
    except ValueError:
        fail(f"{kind} is not valid hex: {h}")


def read_tx_list() -> list[str]:
    if not TX_LIST_PATH.exists():
        fail(f"Missing tx list: {TX_LIST_PATH}")
    txs = []
    for ln in TX_LIST_PATH.read_text(encoding="utf-8").splitlines():
        s = ln.strip().lower()
        if s:
            validate_hex(s, 32, "txid")
            txs.append(s)
    if not txs:
        fail("Empty tx list in solutions/exercise01.txt.")
    return txs


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
    required_be = REQUIRED_TXID
    txs_be = read_tx_list()
    print(f"Input: {txs_be}")

    root_be, proof_be = build_inclusion_proof(txs_be, required_be)

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
