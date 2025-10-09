#!/usr/bin/env python3
"""
Grader for Assignment 3 - Exercise 1 (Transaction selection)

Validates a student's block candidate against:
- Data source: data/mempool.csv

Rules enforced (from README):
- Total weight <= 4,000,000 (4MvB)
- No duplicate transactions
- Every listed txid must exist in the mempool
- Parent/ancestor constraint: all listed parents must appear earlier in the block
- Block cannot be empty
- Optional: block MUST include a specific txid (if configured)

Configuration for the required txid (choose ONE of the following):
1) Env var REQUIRED_TXID
2) File data/required_txid.txt (first non-empty line)
If neither exists, the check is skipped (useful while your README is a draft).

Exit codes:
- 0 on success
- 1 on failure

Printed output is concise but actionable for students & CI logs.
"""

import os
import sys
import csv
from pathlib import Path

MEMPOOL_PATH = Path("data/mempool.csv")
SUBMISSION_PATH = Path("solutions/exercise01.txt")
REQUIRED_TXID = "4c50e3dad7f98bceb6441f96b23748dea84fbdb7cedd603441e6ea4a574d04a6"
WEIGHT_LIMIT = 4_000_000


def load_mempool():
    if not MEMPOOL_PATH.exists():
        fail(f"Missing mempool file at '{MEMPOOL_PATH}'.")
    mempool = {}
    with MEMPOOL_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        # Expect rows: txid, fee, weight, parents
        # No header assumed.
        for i, row in enumerate(reader, start=1):
            if len(row) < 3:
                fail(
                    f"Malformed CSV at line {i}: expected at least 3 columns (txid,fee,weight[,parents])."
                )
            txid = row[0].strip().lower()
            if not txid:
                fail(f"Empty txid at line {i}.")
            try:
                fee = int(row[1])
                weight = int(row[2])
            except ValueError:
                fail(
                    f"Malformed fee/weight at line {i}: got fee='{row[1]}', weight='{row[2]}'."
                )
            parents_raw = row[3].strip() if len(row) >= 4 else ""
            parents = []
            if parents_raw:
                # parents are semicolon-separated txids; ignore blanks
                parents = [
                    p.strip().lower() for p in parents_raw.split(";") if p.strip()
                ]
            mempool[txid] = {"fee": fee, "weight": weight, "parents": parents}
    if not mempool:
        fail("Empty mempool.csv.")
    return mempool


def load_submission():
    if not SUBMISSION_PATH.exists():
        fail(
            f"Missing submission file at '{SUBMISSION_PATH}'. Expected newline-separated txids."
        )
    lines = [
        ln.strip().lower()
        for ln in SUBMISSION_PATH.read_text(encoding="utf-8").splitlines()
    ]
    # Filter out empty lines just in case
    txids = [tx for tx in lines if tx]
    if not txids:
        fail("Submission is empty. The block cannot be empty.")
    return txids


def check_all(mempool, submission, required_txid):
    # 1) Uniqueness
    seen = set()
    for tx in submission:
        if tx in seen:
            fail(f"Duplicate txid in submission: {tx}")
        seen.add(tx)

    # 2) Existence in mempool
    missing = [tx for tx in submission if tx not in mempool]
    if missing:
        fail(f"{len(missing)} txid(s) not found in mempool (first: {missing[0]}).")

    # 3) Weight limit
    total_weight = sum(mempool[tx]["weight"] for tx in submission)
    if total_weight > WEIGHT_LIMIT:
        fail(f"Total weight {total_weight} exceeds limit {WEIGHT_LIMIT}.")

    # 4) Parent ordering rule (parents must appear earlier)
    index = {tx: i for i, tx in enumerate(submission)}
    for i, tx in enumerate(submission):
        parents = mempool[tx]["parents"]
        for p in parents:
            if p not in index:
                fail(f"Parent {p} of {tx} is not included in the block.")
            if index[p] >= i:
                fail(
                    f"Parent {p} of {tx} appears at position {index[p]}, which is not earlier than child at {i}."
                )

    # 5) Block not empty was already checked on load.

    # 6) Required txid (if configured)
    if required_txid:
        if required_txid not in index:
            fail(f"Required txid not found in block: {required_txid}")

    # If all checks passed:
    ok(total_weight, len(submission))


def ok(total_weight, count):
    print("OK")
    print(f"Tx count: {count}")
    print(f"Total weight: {total_weight}")
    sys.exit(0)


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def main():
    required_txid = REQUIRED_TXID
    mempool = load_mempool()
    submission = load_submission()
    check_all(mempool, submission, required_txid)


if __name__ == "__main__":
    main()
