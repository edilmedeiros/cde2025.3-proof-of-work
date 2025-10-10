#!/usr/bin/env python3
"""
Grader for Assignment 3 — Exercise 3 (Block header + Proof of Work)

Submission format:
- solutions/exercise03.txt: a SINGLE line with the 80-byte block header
  serialized exactly as in Bitcoin, written as hex (160 hex chars, no spaces).

Header layout (80 bytes total):
- version      : 4 bytes, little-endian
- prevhash     : 32 bytes, little-endian (displayed big-endian normally)
- merkleroot   : 32 bytes, little-endian (displayed big-endian normally)
- time         : 4 bytes, little-endian (uint32)
- nbits        : 4 bytes, little-endian (compact target)
- nonce        : 4 bytes, little-endian (uint32)

Checks:
1) Header length & hex validity.
2) Recompute Merkle root from solutions/exercise01.txt (+ optional data/coinbase_txid.txt)
   and compare with the header's merkleroot (accounting for endianness).
3) Decode compact nBits -> target.
4) Compute double-SHA256 of the 80-byte header.
5) Verify hash <= target.

Exit codes:
- 0 on success
- 1 on failure
"""

import sys
import hashlib
from pathlib import Path

TX_LIST_PATH = Path("solutions/exercise01.txt")
CB_TXID_PATH = Path("data/coinbase_txid.txt")
SUBMISSION_PATH = Path("solutions/exercise03.txt")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def ok(block_hash_be: str, target_be: str) -> None:
    print("OK")
    print(f"Block hash : {block_hash_be}")
    print(f"Target     : {target_be}")
    sys.exit(0)


def read_header_bytes() -> bytes:
    if not SUBMISSION_PATH.exists():
        fail(f"Missing submission file: {SUBMISSION_PATH}")
    line = SUBMISSION_PATH.read_text(encoding="utf-8").strip().lower()
    if not line:
        fail("Submission is empty; expected 160 hex chars (80-byte header).")
    if len(line) != 160:
        fail(f"Wrong length: expected 160 hex chars, got {len(line)}.")
    try:
        hdr = bytes.fromhex(line)
    except ValueError:
        fail("Header line is not valid hex.")
    if len(hdr) != 80:
        fail(f"Internal length error: decoded {len(hdr)} bytes (expected 80).")
    return hdr


def read_tx_list() -> list[str]:
    if not TX_LIST_PATH.exists():
        fail(f"Missing tx list: {TX_LIST_PATH}")
    txs = []
    for ln in TX_LIST_PATH.read_text(encoding="utf-8").splitlines():
        s = ln.strip().lower()
        if s:
            if len(s) != 64:
                fail("Each txid must be 32 bytes (64 hex chars).")
            try:
                bytes.fromhex(s)
            except ValueError:
                fail("Invalid txid hex in solutions/exercise01.txt.")
            txs.append(s)
    if not txs:
        fail("Empty tx list in solutions/exercise01.txt.")
    return txs


def maybe_prepend_coinbase(txs: list[str]) -> list[str]:
    if not CB_TXID_PATH.exists():
        return txs
    for ln in CB_TXID_PATH.read_text(encoding="utf-8").splitlines():
        s = ln.strip().lower()
        if s:
            if len(s) != 64:
                fail("coinbase txid must be 32 bytes (64 hex chars).")
            try:
                bytes.fromhex(s)
            except ValueError:
                fail("Invalid coinbase txid hex.")
            return [s] + txs
    return txs


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def merkle_root_be_hex(txids_be_hex: list[str]) -> str:
    """Bitcoin-style Merkle (internal LE, double-SHA256, duplicate odd). Returns BE hex."""
    level = [bytes.fromhex(tx) for tx in txids_be_hex]  # leaves in LE
    if not level:
        fail("Cannot compute Merkle root of empty list.")
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        nxt = []
        for i in range(0, len(level), 2):
            nxt.append(sha256(level[i] + level[i + 1]))
        level = nxt
    return level[0].hex()  # convert root back to BE hex


def decode_compact_target_from_le(nbits: str) -> int:
    """
    nBits is stored LE in the header; reverse to get BE display/binary.
    Compact format (BE): [E (1 byte)] [M (3 bytes big-endian)]
    Target = M * 256^(E-3)
    """
    nbits_le = bytes.fromhex(nbits)
    if len(nbits_le) != 4:
        fail("nbits field must be 4 bytes.")
    nbits_be = nbits_le
    E = nbits_be[0]
    M = int.from_bytes(nbits_be[1:], "big")
    if M == 0:
        fail("nbits mantissa is zero.")
    if E < 3 or E > 34:  # conservative bounds
        fail(f"nbits exponent out of expected range: {E}")
    target = M * (1 << (8 * (E - 3)))
    if target <= 0 or target >= (1 << 256):
        fail("Decoded target out of 256-bit range.")
    return target


def int_to_be_hex(n: int, bytelen: int) -> str:
    return n.to_bytes(bytelen, "big").hex()


def main():
    # 1) Read raw header (80 bytes)
    hdr = read_header_bytes()

    # 2) Slice fields
    ver_le = hdr[0:4]
    prev_le = hdr[4:36]
    mrkl_le = hdr[36:68]
    time_le = hdr[68:72]
    nonce_le = hdr[72:80]

    # 3) Recompute merkle root from Exercise 1 (+ optional coinbase)
    txs_be = maybe_prepend_coinbase(read_tx_list())
    mrkl_be_expected = merkle_root_be_hex(txs_be)
    mrkl_be_in_header = mrkl_le.hex()  # LE -> BE for comparison

    if mrkl_be_in_header != mrkl_be_expected:
        fail(
            "Merkle root does not match transactions from exercise 1.\n"
            f"Expected: {mrkl_be_expected}\n"
            f"Got     : {mrkl_be_in_header}"
        )

    # 4) Decode compact target and compute PoW
    nbits = "207fffff"
    target_int = decode_compact_target_from_le(nbits)
    block_hash_le = sha256(hdr)
    block_hash_be = block_hash_le.hex()
    hash_int = int.from_bytes(block_hash_le, "big")

    if hash_int > target_int:
        fail(
            "Insufficient proof of work.\n"
            f"Hash   : 0x{block_hash_be}\n"
            f"Target : 0x{int_to_be_hex(target_int, 32)}"
        )

    ok(block_hash_be, int_to_be_hex(target_int, 32))


if __name__ == "__main__":
    main()
