#!/usr/bin/env python3
"""
Assignment 3 - Exercise 1 solver (Transaction selection)

Reads:  data/mempool.csv   with rows: txid,fee,weight,parents
Writes: solutions/exercise01.txt  (newline-separated txids in valid block order)

Rules enforced:
- Total weight <= 4,000,000
- Parent appears earlier than child (topological order)
- No duplicates
- Block not empty
- Must include REQUIRED_TXID (hard-coded below)
- Total fees >= 50,000 sats

Heuristic:
- First include the required txid + all of its missing ancestors.
- Then repeatedly pick the "best package" (a tx plus any not-yet-included ancestors) by
  highest effective feerate (eff_fee / eff_weight), breaking ties by higher eff_fee,
  lighter eff_weight, then lexicographical txid.
- Append each chosen package in a topological order that respects parent-before-child.

NOTE: Parents listed in mempool rows are *immediate* parents only; ancestors of parents
      are discovered recursively. If a parent is not present in the mempool (already
      confirmed), it's considered satisfied and does not need to be included.
"""

from __future__ import annotations
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple

MEMPOOL = Path("data/mempool.csv")
OUTPUT = Path("solutions/exercise01.txt")
WEIGHT_LIMIT = 4_000_000
MIN_TOTAL_FEES = 50_000

# === Required txid for this assignment (from README) ===
REQUIRED_TXID = (
    "4c50e3dad7f98bceb6441f96b23748dea84fbdb7cedd603441e6ea4a574d04a6".lower()
)


@dataclass(frozen=True)
class Tx:
    txid: str
    fee: int
    weight: int
    parents: Tuple[str, ...]  # immediate parents (txids), may be empty


def load_mempool(path: Path) -> Dict[str, Tx]:
    if not path.exists():
        raise SystemExit(f"ERROR: missing mempool file: {path}")
    mp: Dict[str, Tx] = {}
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, start=1):
            if len(row) < 3:
                raise SystemExit(
                    f"ERROR: malformed line {i}: need at least 3 cols (txid,fee,weight[,parents])"
                )
            txid = row[0].strip().lower()
            try:
                fee = int(row[1].strip())
                weight = int(row[2].strip())
            except ValueError:
                raise SystemExit(
                    f"ERROR: malformed fee/weight at line {i}: {row[1]}/{row[2]}"
                )
            parents_raw = row[3].strip() if len(row) >= 4 else ""
            parents = tuple(
                p.strip().lower() for p in parents_raw.split(";") if p.strip()
            )
            if not txid:
                raise SystemExit(f"ERROR: empty txid at line {i}")
            if txid in mp:
                raise SystemExit(
                    f"ERROR: duplicate txid in mempool at line {i}: {txid}"
                )
            mp[txid] = Tx(txid=txid, fee=fee, weight=weight, parents=parents)
    if REQUIRED_TXID not in mp:
        # Required tx can still be valid if it's *not* in the mempool? For this assignment, it must be.
        raise SystemExit(f"ERROR: required txid not found in mempool: {REQUIRED_TXID}")
    return mp


def all_ancestors(txid: str, mp: Dict[str, Tx]) -> Set[str]:
    """Return the transitive closure of in-mempool ancestors for `txid`."""
    stack = list(mp[txid].parents)
    anc: Set[str] = set()
    while stack:
        p = stack.pop()
        if p in anc:
            continue
        if p in mp:  # only count parents that are in the mempool
            anc.add(p)
            stack.extend(mp[p].parents)
        # if a parent is not in mempool, it's assumed mined already -> ignore
    return anc


def topo_order_for_subset(subset: Set[str], mp: Dict[str, Tx]) -> List[str]:
    """
    Return a topological order of the given subset of txids (parents before children).
    Assumes the subgraph induced by `subset` has no cycles.
    """
    # Kahn's algorithm on the induced subgraph
    indeg = {t: 0 for t in subset}
    children: Dict[str, List[str]] = {t: [] for t in subset}
    for t in subset:
        for p in mp[t].parents:
            if p in subset:
                indeg[t] += 1
                children[p].append(t)
    # start with zero indegree; stable order by txid for determinism
    from heapq import heappush, heappop

    heap: List[str] = []
    for t in sorted(indeg.keys()):
        if indeg[t] == 0:
            heappush(heap, t)
    order: List[str] = []
    while heap:
        u = heappop(heap)
        order.append(u)
        for v in children[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heappush(heap, v)
    if len(order) != len(subset):
        raise SystemExit(
            "ERROR: cycle detected in selected subset (unexpected in valid mempool)."
        )
    return order


def package_missing_for(txid: str, included: Set[str], mp: Dict[str, Tx]) -> Set[str]:
    """Tx + any ancestors not yet included."""
    if txid not in mp:
        return set()  # shouldn't happen
    missing = {txid}
    missing.update(all_ancestors(txid, mp))
    missing.difference_update(included)
    return missing


def package_eff_fee_weight(missing: Set[str], mp: Dict[str, Tx]) -> Tuple[int, int]:
    fee = sum(mp[t].fee for t in missing)
    wt = sum(mp[t].weight for t in missing)
    return fee, wt


def select_block(mp: Dict[str, Tx]) -> Tuple[List[str], int, int]:
    included: Set[str] = set()
    order: List[str] = []
    total_w = 0
    total_fee = 0

    # 1) Force-include REQUIRED tx + its missing ancestors, if they fit
    req_missing = package_missing_for(REQUIRED_TXID, included, mp)
    # order those correctly
    req_order = topo_order_for_subset(req_missing, mp)
    req_w = sum(mp[t].weight for t in req_order)
    req_f = sum(mp[t].fee for t in req_order)
    if req_w > WEIGHT_LIMIT:
        raise SystemExit("ERROR: required tx package exceeds weight limit.")
    # append
    for t in req_order:
        if t not in included:
            if total_w + mp[t].weight > WEIGHT_LIMIT:
                raise SystemExit(
                    "ERROR: required tx package no longer fits unexpectedly."
                )
            included.add(t)
            order.append(t)
            total_w += mp[t].weight
            total_fee += mp[t].fee

    # 2) Greedy loop by best package feerate
    #    Repeat until no candidate fits
    remaining = set(mp.keys()) - included
    while remaining:
        best = None  # (score, eff_fee, eff_w, key_txid, order_list)
        for txid in remaining:
            missing = package_missing_for(txid, included, mp)
            if not missing:
                continue
            eff_fee, eff_w = package_eff_fee_weight(missing, mp)
            if eff_w <= 0 or total_w + eff_w > WEIGHT_LIMIT:
                continue
            # Build the topo order only for the missing subset
            try:
                miss_order = topo_order_for_subset(missing, mp)
            except SystemExit:
                # cycle inside missing -> skip
                continue
            score = eff_fee / eff_w
            key = (-score, -eff_fee, eff_w, txid)  # min-heap style ordering for ties
            if (best is None) or (key < best[0]):
                best = (key, eff_fee, eff_w, txid, miss_order)

        if best is None:
            # nothing else fits
            break

        _, eff_fee, eff_w, key_txid, miss_order = best
        # append missing package in topo order
        for t in miss_order:
            if t not in included:
                w = mp[t].weight
                if total_w + w > WEIGHT_LIMIT:
                    # shouldn't happen because we checked eff_w earlier; just stop the loop
                    remaining.discard(t)
                    break
                included.add(t)
                order.append(t)
                total_w += w
                total_fee += mp[t].fee

        remaining = set(mp.keys()) - included

    # Final validations
    if not order:
        raise SystemExit("ERROR: block would be empty.")
    if REQUIRED_TXID not in included:
        raise SystemExit("ERROR: required txid is not included (logic bug).")
    if total_fee < MIN_TOTAL_FEES:
        # Not fatal for autograder (it doesn't check fee amount), but enforce per README.
        raise SystemExit(
            f"ERROR: total fees {total_fee} < required minimum {MIN_TOTAL_FEES} sats."
        )

    return order, total_w, total_fee


def main():
    mp = load_mempool(MEMPOOL)
    order, total_w, total_fee = select_block(mp)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for txid in order:
            f.write(txid + "\n")
    print("OK")
    print(f"Tx count : {len(order)}")
    print(f"Weight   : {total_w}")
    print(f"Fees     : {total_fee}")
    print(f"Wrote    : {OUTPUT}")


if __name__ == "__main__":
    main()
