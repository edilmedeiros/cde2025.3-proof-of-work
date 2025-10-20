#!/usr/bin/env python3
"""
Parallel miner for Assignment 3 - Exercise 3.

Reads:
- solutions/exercise01.txt : newline-separated txids (big-endian hex), block order
- data/coinbase_txid.txt   : (optional) first non-empty line is coinbase txid (BE hex)

Writes:
- solutions/exercise03.txt : ONE line with the raw 80-byte header in hex (160 chars)

Usage (examples):
  python tools/make_ex3_solution_parallel.py --nbits 207fffff --jobs 10
  python tools/make_ex3_solution_parallel.py --nbits 207fffff --jobs 10 --chunk 1000000
  python tools/make_ex3_solution_parallel.py --nbits 207fffff --prevhash <64-hex> --time 1739990000

Notes:
- Header layout (LE fields): <version(4)><prev(32)><merkle(32)><time(4)><nbits(4)><nonce(4)>
- Merkle root recomputed exactly like the grader (internal LE, sha256d, duplicate odd).
- Parallel strategy: iterate across the 32-bit nonce space in CHUNK-sized blocks; submit one chunk per worker;
  as soon as one finds a valid nonce, cancel the rest.
"""

from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed

TX_LIST_PATH = Path("solutions/exercise01.txt")
COINBASE_PATH = Path("data/coinbase_txid.txt")
OUTPUT_PATH = Path("solutions/exercise03.txt")

# ---------- Common helpers (match grader behavior) ----------


def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def int32_be(n: int) -> bytes:
    return (n & 0xFFFFFFFF).to_bytes(4, "big")


def int64_be(n: int) -> bytes:
    return (n & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "big")


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


def build_header_prefix(
    version: int,
    prevhash_be: str,
    merkleroot_be: str,
    timestamp: int,
) -> bytes:
    ver_b = int32_be(version)
    prev_b = bytes.fromhex(prevhash_be)
    mrkl_b = bytes.fromhex(merkleroot_be)
    time_b = int32_be(timestamp)
    return ver_b + prev_b + mrkl_b + time_b


# ---------- Parallel mining ----------


def mine_chunk(
    prefix: bytes, target: int, start_nonce: int, count: int
) -> Optional[Tuple[str, str, int]]:
    """
    Try 'count' consecutive nonces starting at 'start_nonce'.
    Returns (header_hex, block_hash_be, nonce) if success, else None.
    """
    nonce = start_nonce & 0xFFFFFFFFFFFFFFFF
    # We handle wrap-around simply by stopping when attempts == count
    for _ in range(count):
        hdr = prefix + int64_be(nonce)  # 80 bytes
        h_le = sha256(hdr)
        h_int = int.from_bytes(h_le, "big")
        if h_int <= target:
            return hdr.hex(), h_le.hex(), nonce
        nonce = (nonce + 1) & 0xFFFFFFFFFFFFFFFF
    return None


def parallel_mine(
    version: int,
    prevhash_be: str,
    merkle_root_be: str,
    nbits_be_hex: str,
    timestamp: int,
    jobs: int,
    chunk: int,
) -> Tuple[str, str, int, int]:
    """
    Returns (header_hex, block_hash_be, nonce, used_time)
    """
    merkleroot_be = merkle_root_be
    target = decode_compact_target_be(nbits_be_hex)

    # Prepare the constant 72 bytes of the header (nonce varies)
    prefix = build_header_prefix(version, prevhash_be, merkleroot_be, timestamp)

    print(f"Target: {target.to_bytes(32, 'big').hex()}")
    print(f"Block prefix: {prefix.hex()}")

    # Iterate chunks across the 32-bit nonce space until success
    # Chunk i for worker k starts at: base + k*chunk + i*(jobs*chunk)
    base = 0
    with ProcessPoolExecutor(max_workers=max(1, jobs)) as ex:
        while True:
            futures = []
            for k in range(jobs):
                start = (base + k * chunk) & 0xFFFFFFFFFFFFFFFF
                print(
                    f"Starting job {k} with initial nonce {start} and timestamp {timestamp}"
                )
                futures.append(ex.submit(mine_chunk, prefix, target, start, chunk))
            # First result that is not None wins
            for fut in as_completed(futures):
                res = fut.result()
                if res is not None:
                    header_hex, block_hash_be, nonce = res
                    # Cancel outstanding work quickly
                    for f in futures:
                        if f is not fut:
                            f.cancel()
                    return header_hex, block_hash_be, nonce, timestamp
            # No success in this round; advance base
            base = (base + jobs * chunk) & 0xFFFFFFFFFFFFFFFF
            if base == 0:
                # We wrapped the whole nonce space; bump time and recompute prefix
                timestamp += 1
                prefix = build_header_prefix(
                    version, prevhash_be, merkleroot_be, timestamp, nbits_be_hex
                )


def main():
    jobs = 10
    version = 2
    prevhash = "00000000d1145790a8694403d4063f323d499e655c83426834d4ce2f8dd4a2ee"
    merkle_root = "c0a692de10b69e2381a2856dcb0d0736dcd307bf25af7ce74831bf25793de626"
    nbits = "20ffffff"
    min_timestamp = 1230999305
    max_timestamp = 1231723825
    chunk = 100_000_000

    header_hex, block_hash_be, nonce, used_time = parallel_mine(
        version=version,
        prevhash_be=prevhash,
        merkle_root_be=merkle_root,
        nbits_be_hex=nbits,
        timestamp=min_timestamp,
        jobs=jobs,
        chunk=chunk,
    )

    # Write the single-line header hex expected by the grader
    out = "solutions/exercise03-test.txt"
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(header_hex + "\n", encoding="utf-8")

    print("Solved!")
    print(f"Header (hex): {header_hex}")
    print(f"Block hash  : {block_hash_be}")
    print(f"Nonce       : {nonce}")
    print(f"Time        : {used_time}")
    print(f"Jobs        : {jobs}  |  Chunk: {chunk}")
    print(f"Wrote       : {out_path}")


if __name__ == "__main__":
    main()
