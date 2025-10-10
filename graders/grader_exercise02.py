#!/usr/bin/env python3
"""
Grader for Assignment 3 - Exercise 2 (Merkle root + inclusion proof)

Validates BOTH:
1) The Merkle root reported by the student.
2) The inclusion proof path for the REQUIRED_TXID by checking each sibling
   against the actual sibling in the tree built from exercise01's tx list.

Inputs:
- solutions/exercise01.txt : newline-separated txids (big-endian hex), block order
- solutions/exercise02.txt : line 1 = merkle root (big-endian hex)
                             lines 2..N = proof siblings (big-endian hex), leaf->root
- data/coinbase_txid.txt   : (optional) first non-empty line is coinbase txid (hex)
- REQUIRED_TXID env var    : (optional) required txid (big-endian hex)
- data/required_txid.txt   : (fallback) first non-empty line is required txid (hex)

Conventions (Bitcoin-compatible):
- txids submitted/displayed as big-endian hex.
- Internally, Merkle uses little-endian bytes for nodes:
    parent = sha256d( left || right )
  where left/right are the little-endian 32-byte node values.
- When a level has an odd number of nodes, duplicate the last.

Exit codes:
- 0 on success
- 1 on failure
"""

import sys
from pathlib import Path
import hashlib

TX_LIST_PATH = Path("solutions/exercise01.txt")
PROOF_PATH = Path("solutions/exercise02.txt")
REQUIRED_TXID = "4c50e3dad7f98bceb6441f96b23748dea84fbdb7cedd603441e6ea4a574d04a6"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(root_hex: str, depth: int) -> None:
    print("OK")
    print(f"Merkle root: {root_hex}")
    print(f"Proof depth checked: {depth} level(s)")
    sys.exit(0)


def read_tx_list() -> list[str]:
    if not TX_LIST_PATH.exists():
        fail(f"Missing tx list at '{TX_LIST_PATH}'.")
    txs = []
    for ln in TX_LIST_PATH.read_text(encoding="utf-8").splitlines():
        s = ln.strip().lower()
        if s:
            validate_hex(s, 32, "txid")
            txs.append(s)
    if not txs:
        fail("No txids found in solutions/exercise01.txt.")
    return txs


def read_student_root_and_proof() -> tuple[str, list[str]]:
    if not PROOF_PATH.exists():
        fail(f"Missing proof submission at '{PROOF_PATH}'.")
    lines = [
        ln.strip()
        for ln in PROOF_PATH.read_text(encoding="utf-8").splitlines()
        if ln.strip()
    ]
    if not lines:
        fail("solutions/exercise02.txt is empty.")
    root_hex = lines[0].lower()
    validate_hex(root_hex, 32, "merkle root (line 1)")
    proof = []
    for i, ln in enumerate(lines[1:], start=2):
        s = ln.strip().lower()
        validate_hex(s, 32, f"proof hash (line {i})")
        proof.append(s)
    return root_hex, proof


def validate_hex(h: str, bytelen: int, kind: str) -> None:
    if len(h) != 2 * bytelen:
        fail(f"{kind} must be {bytelen} bytes ({2 * bytelen} hex chars), got {len(h)}.")
    try:
        bytes.fromhex(h)
    except ValueError:
        fail(f"{kind} is not valid hex.")


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def merkle_root_be_hex(txids_be_hex: list[str]) -> str:
    if not txids_be_hex:
        fail("Cannot compute Merkle root of empty list.")
    level = [bytes.fromhex(tx) for tx in txids_be_hex]  # LE bytes
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        nxt = []
        for i in range(0, len(level), 2):
            nxt.append(sha256(level[i] + level[i + 1]))
        level = nxt
    return level[0].hex()  # back to BE hex


def build_next_level(level: list[bytes]) -> list[bytes]:
    """Given a level of LE 32-byte nodes, return the next level (parents, LE)."""
    nodes = level[:]
    if len(nodes) % 2 == 1:
        nodes.append(nodes[-1])
    nxt = []
    for i in range(0, len(nodes), 2):
        nxt.append(sha256(nodes[i] + nodes[i + 1]))
    return nxt


def main():
    required_txid_be = REQUIRED_TXID
    txs_be = read_tx_list()

    # locate required txid
    try:
        idx = txs_be.index(required_txid_be)
    except ValueError:
        fail(f"Required txid not found in the block tx list: {required_txid_be}")

    # read student's merkle root and proof path
    student_root_be, proof_be = read_student_root_and_proof()

    # Prepare leaf level (LE bytes)
    level = [bytes.fromhex(tx) for tx in txs_be]  # leaves as LE
    current = level[idx]  # LE 32-byte node for the required txid
    current_index = idx

    # Recompute expected sibling and verify against each submitted proof hash
    depth_checked = 0
    for step, proof_hash_be in enumerate(proof_be):
        # Validate sibling equals the true sibling in this level
        # Determine sibling index with duplication rule
        size = len(level)
        last_dup = size % 2 == 1 and current_index == size - 1
        if last_dup:
            sib = level[current_index]  # duplicated self
        else:
            sib_index = current_index ^ 1  # toggle last bit: even<->odd
            if sib_index >= size:
                # Shouldn't happen with proper duplication, but guard anyway
                sib_index = size - 1
            sib = level[sib_index]

        # Compare with student's proof hash (convert student's BE->LE)
        submitted_sib_le = bytes.fromhex(proof_hash_be)
        if submitted_sib_le != sib:
            exp_be = sib.hex()
            fail(
                "Proof mismatch at level {}.\nExpected sibling: {}\nSubmitted       : {}".format(
                    step, exp_be, proof_hash_be
                )
            )

        # Compute parent using left/right order
        if last_dup:
            parent = sha256(current + sib)  # same value twice
        else:
            if current_index % 2 == 0:  # current is LEFT
                parent = sha256(current + sib)
            else:  # current is RIGHT
                parent = sha256(sib + current)

        # Advance to next level
        # To keep checking siblings at the next level, we must construct the entire parent level.
        parent_level = build_next_level(level)
        # Compute the index of our parent in the parent level:
        current_index = current_index // 2
        # Sanity: parent we computed must equal parent_level[current_index]
        if parent != parent_level[current_index]:
            fail(
                "Internal consistency error while building parent level (unexpected parent mismatch)."
            )

        # Move up
        level = parent_level
        current = parent
        depth_checked += 1

        # Stop early if we reached root before consuming all proof hashes
        if len(level) == 1:
            # If proof still has more elements, it's too long
            if step != len(proof_be) - 1:
                fail(
                    f"Proof has extra elements beyond the root (excess at position {step + 2})."
                )
            break

    # After consuming the proof, we should be at the root
    if len(level) != 1:
        # Compute full root from tx list for an informative message
        full_root = merkle_root_be_hex(txs_be)
        need_levels = 0
        tmp = len(txs_be)
        while tmp > 1:
            need_levels += 1
            tmp = (tmp + 1) // 2
        fail(
            f"Proof too short. Expected about {need_levels} sibling(s) for this tree height."
            f"\nFull root would be: {full_root}"
        )

    computed_root_be = current.hex()

    # Cross-check with full recomputation of the Merkle root from the entire list
    recomputed_full_root_be = merkle_root_be_hex(txs_be)
    if recomputed_full_root_be != computed_root_be:
        fail(
            "Computed root mismatch with full recomputation.\n"
            f"From proof path : {computed_root_be}\n"
            f"From full recompute: {recomputed_full_root_be}"
        )

    # Finally, compare with student's submitted root
    if student_root_be != computed_root_be:
        fail(
            "Merkle root mismatch.\n"
            f"Expected: {computed_root_be}\n"
            f"Got     : {student_root_be}"
        )

    ok(computed_root_be, depth_checked)


if __name__ == "__main__":
    main()
