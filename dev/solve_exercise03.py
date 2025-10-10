#!/usr/bin/env python3
"""
Generate a valid solution for Assignment 3 - Exercise 3.

Reads:
- solutions/exercise01.txt : newline-separated txids (big-endian hex), block order
- data/coinbase_txid.txt   : (optional) first non-empty line is coinbase txid (BE)

Parameters (CLI):
  --version INT             Block version (default: 4)
  --prevhash HEX64          Previous block hash (BE hex; default: 64 '00's)
  --nbits HEX8              Compact target (BE hex, e.g., '207fffff' regtest-easy)
  --time INT                UNIX seconds (defaults to current time)
  --start-nonce INT         Nonce to start from (default: 0)
  --max-tries INT           Max nonce attempts before failing (default: 50_000_000)
  --allow-time-increment    If set, when nonce space is exhausted, bump time and continue
  --tx-file PATH            Override tx list path (default: solutions/exercise01.txt)
  --out PATH                Output file (default: solutions/exercise03.txt)

Writes:
- solutions/exercise03.txt : ONE line with the raw 80-byte header in hex (160 chars)

Notes:
- Header layout is *little-endian* per field inside (version/prev/merkle/time/nbits/nonce).
- Txids are given/kept as big-endian hex; internal merkle uses LE nodes.
"""

import hashlib
from pathlib import Path
from typing import List

TX_LIST_PATH = Path("solutions/exercise01.txt")
COINBASE_PATH = Path("data/coinbase_txid.txt")
OUTPUT_PATH = Path("solutions/exercise03.txt")


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def merkle_root_be_hex(txids_be_hex: List[str]) -> str:
    level = [bytes.fromhex(tx) for tx in txids_be_hex]  # leaves LE
    if not level:
        raise SystemExit("ERROR: Cannot compute Merkle root of empty list.")
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        nxt = []
        for i in range(0, len(level), 2):
            nxt.append(sha256(level[i] + level[i + 1]))
        level = nxt
    return level[0].hex()  # BE hex


def uint32_be(n: int) -> bytes:
    return (n & 0xFFFFFFFF).to_bytes(4, "big")


def uint64_be(n: int) -> bytes:
    return (n & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "big")


def int32_be(n: int) -> bytes:
    return (n & 0xFFFFFFFF).to_bytes(4, "big")


def decode_compact_target_be(nbits_be_hex: str) -> int:
    b = bytes.fromhex(nbits_be_hex)
    if len(b) != 4:
        raise SystemExit("ERROR: nbits must be 4 bytes (8 hex).")
    E = b[0]
    M = int.from_bytes(b[1:], "big")
    if M == 0 or E < 3 or E > 34:
        raise SystemExit("ERROR: Invalid compact target (mantissa/exponent).")
    target = M * (1 << (8 * (E - 3)))
    if target <= 0 or target >= (1 << 256):
        raise SystemExit("ERROR: Decoded target out of 256-bit range.")
    return target


def read_tx_list(path: Path) -> List[str]:
    if not path.exists():
        raise SystemExit(f"ERROR: Missing tx list: {path}")
    txs = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip().lower()
        if not s:
            continue
        if len(s) != 64:
            raise SystemExit("ERROR: Each txid must be 64 hex chars.")
        try:
            bytes.fromhex(s)
        except ValueError:
            raise SystemExit("ERROR: Invalid txid hex in tx list.")
        txs.append(s)
    if not txs:
        raise SystemExit("ERROR: Empty tx list.")
    return txs


def build_header_hex(
    version: int,
    prevhash_be: str,
    merkleroot_be: str,
    timestamp: int,
    nonce: int,
) -> str:
    ver_b = int32_be(version)
    prev_b = bytes.fromhex(prevhash_be)
    mrkl_b = bytes.fromhex(merkleroot_be)
    time_b = uint32_be(timestamp)
    nonce_b = uint64_be(nonce)
    hdr = ver_b + prev_b + mrkl_b + time_b + nonce_b  # 80 bytes
    return hdr.hex()


def mine(
    version: int,
    prevhash_be: str,
    nbits_be_hex: str,
    timestamp: int,
    start_nonce: int,
    max_tries: int,
    allow_time_increment: bool,
    txs_be: List[str],
    out_path: Path,
) -> None:
    merkleroot_be = merkle_root_be_hex(txs_be)
    target = decode_compact_target_be(nbits_be_hex)

    nonce = start_nonce
    tries = 0
    cur_time = timestamp

    while True:
        header_hex = build_header_hex(
            version, prevhash_be, merkleroot_be, cur_time, nonce
        )
        hdr = bytes.fromhex(header_hex)
        h_le = sha256(hdr)
        h_be_hex = h_le.hex()
        h_int = int.from_bytes(h_le, "big")
        if h_int <= target:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(header_hex + "\n", encoding="utf-8")
            print("Solved!")
            print(f"Header (hex): {header_hex}")
            print(f"Block hash  : {h_be_hex}")
            print(f"Target      : {target.to_bytes(32, 'big').hex()}")
            print(f"Nonce       : {nonce}")
            print(f"Time        : {cur_time}")
            print(f"Wrote       : {out_path}")
            return

        # next attempt
        nonce = (nonce + 1) & 0xFFFFFFFF
        tries += 1

        if tries >= max_tries:
            if allow_time_increment:
                cur_time += 1
                tries = 0
                # keep nonce rolling to avoid repeating same header
            else:
                raise SystemExit(
                    "ERROR: Mining aborted: max-tries reached (increase --max-tries or enable --allow-time-increment)."
                )


def main():
    txs = read_tx_list(Path(TX_LIST_PATH))

    version = 4
    prev = "00000000d1145790a8694403d4063f323d499e655c83426834d4ce2f8dd4a2ee"
    nbits = "207fffff"
    timestamp = 1230999306
    start_nonce = 0
    max_tries = 50000000
    allow_time_increment = True

    # minimum stamp 1230999305
    # max stamp 1231723825
    #
    mine(
        version=version,
        prevhash_be=prev,
        nbits_be_hex=nbits,
        timestamp=timestamp,
        start_nonce=start_nonce,
        max_tries=max_tries,
        allow_time_increment=allow_time_increment,
        txs_be=txs,
        out_path=Path(OUTPUT_PATH),
    )


if __name__ == "__main__":
    main()
