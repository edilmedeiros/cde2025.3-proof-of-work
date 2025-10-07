# Proving you did the work

In the previous assignment we explored how elliptic curve digital signatures work.
Digital signatures are the main authorization mechanism used in cryptocurrencies to avoid someone from spending your funds, they effectively define who owns what.
In particular, we saw that digital signatures are not infallible.
Even the most sophisticated mathematical constructions can be used in an insecure manner.

Another key aspect of security on cryptocurrency systems is determining the order in which transactions are to be considered.
Transactions in cryptocurrencies trigger a change in state maintained by the nodes in the network.
This is true for UTXO-based systems, like Bitcoin, that maintain a record of all the existing UTXOs; but also for balance-based systems, like Ethereum.
Proof of work is a fundamental piece of Nakamoto Consensus, a synchronization mechanism based on finding partial collisions of cryptographic hash functions that we explored in Assignment 1.

In this assignment we are going to explore what miners are doing in the Bitcoin network: selecting the transactions that will compose the next block, compute proof that those transactions were committed to the block, and grind hashes until they find a block with sufficient proof of work.

### Expected submissions

Your solutions should be in the form of text files in the `solutions` folder of your repo, containing the requested data in hex format.
The autograder will run the scripts in the `graders` folder to verify your answers.
You can use them to check your answers, but DO NOT MODIFY THE GRADER SCRIPTS.

**All cryptographic operations must use the secp256k1 elliptic curve and the sha256 hash function**.
This is the same curve used by Bitcoin and Ethereum, making your implementations directly relevant to real cryptocurrency systems.

You can use any programming language you prefer, the graders will check only the final results you provide in text files.

Please commit your source code to the `implementation` folder so instructors can provide feedback on your approach.
The autograder is triggered when you push changes to the `main` branch.
Check its output on the `Actions` tab in the GitHub interface.

---

### Exercise 1: Transaction selection

Nodes maintain a list of valid unconfirmed transactions, called the *mempool*.
This is where miners look for transactions to include in blocks.

You are given the file `data/mempool.csv` that described a node's mempool with the format: `<txid>,<fee>,<weight>,<parent_txids>`.

- `txid` is the transaction identifier;
- `fee` is the absolute fee paid by the transaction;
- `weight` is the total "space" required by the transaction in the block;
- `parent_txids` is a list of txids of the transactions immediate parents, in the format `<txid1>;<txid2>;...`. Ancestors that are not immediate parents (e.g. parents of parents) and parent transactions that are already in the chain are not included in the list.

Your program should select transactions in this list to compose a block according to the following rules:

- The total weight of transactions in a block must not exceed 4,000,000 weight (4MvB).
- A transaction may appear in a block if, and only if, all of its ancestors appear *earlier* in the block.
- A transaction must not appear more than once in the block.
- A transaction may have zero, one, or many ancestors in the mempool. It may also have zero, one, or many children in the mempool.
- For this exercise, assume that there is no coinbase transaction.
- For this exercise, a block can't be empty.
- For this exercise, your block MUST include the transaction `TXID`

*Expected output*: a text file `solutions/exercise01.txt` with the list of selected txids, separated by newlines, which make a valid block, maximizing the fee to the miner.
Transactions must appear in order.
No transaction should appear unless its parents are included, no transaction should appear before its parents, and no transaction may appear more than once.

*Bonus for fun*:
Of course, you want to maximize the total amount of fees paid by the transactions included in your block, even though the autograder will not check for the amount paid in fees.
You are welcome to bribe yourself in the Discord server.
Let's see who can take the most out of this mempool!

TODO: Add example of output

---

### Exercise 2: Committing the selected transactions

For performance reasons, we don't hash the list of transactions that compose the block.
Instead, we build a block header that includes a commitment to those transactions; i.e., we include a (single) hash that can be used to efficiently prove that all the selected transactions were indeed included in the block.
We call this hash a *merkle root*.

Your program should compute the merkle root for the transactions you selected in Exercise 1, according to the following rules:

- Txids should be parsed as raw bytes (not pure strings).
- All hashes should be (single) `sha256`.
- Hashes should be combined in pairs by concatenating raw bytes, without any separators.
- If a hash has not a pair to combine, concatenate it with itself.

*Expected output*: a text file `solutions/exercise02.txt` with the merkle root of your block in the first line and proofs that the transaction `TXID` was included in the block in the subsequent lines.

TODO: Add example of output.

---

### Exercise 3: Grinding the proof of work

Now, let's build the block header and do the heavy computations.
You should be able to leverage Exercise 6 from Assignment 1 for this.

For this exercise, the block header will be composed by the following fields:

- `version`: 4 bytes. Should be greater than 1.
- `previous_block`: 32 bytes. Should be exactly `00000000d1145790a8694403d4063f323d499e655c83426834d4ce2f8dd4a2ee`.
- `merkle_root`: 32 bytes, as calculated in the previous exercise.
- `timestamp`: 4 bytes, unix time.
- `nonce`: 8 bytes.

The timestamp should be greater than `Jan 03 2009 16:15:05 UTC` and less than `Jan 12 2009 01:30:25 UTC`.

The proof of work target is `00000000ffff0000000000000000000000000000000000000000000000000000`, i.e. the hash of your block header should be less than or equal to the target value.

TODO: Adjust this target so it's feasible. Currently is the initial target of the Bitcoin network.

*Expected output*: a text file `solutions/exercise03.txt` with a valid block header, in hex format.

TODO: Add example of output.

*Bonus for fun*: Please report in the Discord server the time it took for your implementation to mine your block.
