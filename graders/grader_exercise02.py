#!/usr/bin/env python3
"""
Grader for Assignment 3 - Exercise 2 (Merkle root + inclusion proof)

Validates BOTH:
1) The Merkle root reported by the student.
2) The inclusion proof path for the REQUIRED_TXID by checking the hash
    of the proofs of the valid solution tree against the student's tree.

Inputs:
- graders/ex2_solution.txt : hashed valid solution
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
import hashlib
import sys

def main():


    solution_list = []
    for line in open("ex2_solution.txt"):
        solution_list.append(line.strip())

    student_solution = []
    for line in open("../solutions/exercise02.txt"):
        student_solution.append(line.strip())

    # check merkle root
    fail = False

    student_root = student_solution.pop(0)
    try:
        assert solution_list.pop(0) == hashlib.sha256(bytes.fromhex(student_root)).digest().hex()
    except AssertionError:
        fail = True
        print("FAIL: {} is the incorrect Merkle Root".format(student_root))

    try:
        assert len(solution_list) == len(student_solution)
    except AssertionError:
        fail = True
        print("FAIL: solution is incorrect length was {}, should be {}".format(len(student_solution) + 1,
                                                                               len(solution_list) + 1))

    for i in range(min(len(solution_list), len(student_solution))):
        try:
            assert solution_list[i] == hashlib.sha256(bytes.fromhex(student_solution[i])).digest().hex()
        except AssertionError:
            fail = True
            print("FAIL: {} is the incorrect proof at level {}".format(student_solution[i], i))

    if fail:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
