# token-monitor
Monitors the balance changes of an ERC20 token contract

This is bytecode analyzer that scans through the tx traces and figures out who are the token holders whose balance have changed as a result of the tx execution.

This approach should work for any Solidity-based ERC20 contract, no ABI or source code needed. It also detects changes that happen at the time of contract creation (“pre-mines”) and hard-coded balances. Since it doesn’t rely on logs, it should catch minting/burning and other custom balance shifts as well, regardless of the emitted `Transfer()` events.

## `./get_nonce.py`
Scans the bytecode of an ERC20 token contract to identify the internal nonce that's associated with the storage pattern of the balances map.

### Current heuristic
*This can be improved, but works for now.*

- We start with a sample tx that is guaranteed to include a single `Transfer` event for the token we're interested in.
- The script replays the transaction (via a Parity `trace_replayTransaction` call) and monitors the state diffs to collect a set of storage location keys that got changed by the execution of the transaction. The potential balance values are a strict subset of this set of keys.
- We ask Parity to simulate a `balanceOf(sender)` and compile a list of all values that circulated on the stack during this call.
- We expect the only common element of the two sets created above is the storage location key of the balance for the token sender, which would need to have be accessed by both the routines. Let this be called `sender_sloc`.
- Now we know that `sender_sloc = sha3(sender + nonce)` where `nonce` is a unique value allocated by the Solidity compiler to the mapping of balances. We assume all versions of Solidity use the same memory mapping strategy *needs to be validated*. This allows us to brute force the nonce in very few steps, as Solidity typically allocates the nonces in increasing order starting from zero, and there are not many data structures (hence nonces) defined in the typical token contracts.

### Example
```shell=
$ ./get_nonce.py --sample=0x7cd824bc5c11a16dc52f738fef5c6e3aca923af7a7cd9ecc136547c9606eac13

Token contract: 0xb8c77482e45f1f44de1745f52c74426c631bdd52
Balance map nonce: 5
```

## `./scan.py`
Receives a `nonce` and a `tx`. Analyzes the execution of `tx` and identifies the holder addresses whose corresponding balances have changed - by looking at the map identified by `nonce`.

### Current method
- Gather the set of storage location keys that were changed in the contract as a result of executing `tx`
- Gather all 'address-like' values that got pushed on the stack while executing `tx`. We assume these to be the only possible address values whose balance could change as a result of `tx`.
- We compute a rainbow table that maps each `sha3(candidate + nonce)` back to `candidate`. We expect to process a max. of 1000 candidates for an average token transfer transaction.
- We scan through the storage location keys that got touched during the execution and for each key we make a lookup in the rainbow table. If it's there, that means the key is related to the balance mapping of the rainbow table value.
- This lets us export event each time a balance key is touched, on the form `BalanceChange(holder_address, old_value, new_value)`

### Analysis
Both the time and memory complexity are linear in the number of values that get pushed in the VM stack when the tx gets executed, which in turn has an upper bound on the block gas limit. So the main computational overhead is linked to retrieving the traces from Parity. Other than that, there’s a relatively small (<1000) number of sha3 computations for each tx.

### TODO
- Check compatibility with openzeppelinos / proxy, upgradeable contracts
- Check compatibility with Augur (forking and stuff)
- Check compatibility with Jordi's MiniMe (e.g. Status Token)


## Setup
- Clone the repository
- Make sure you're running Python 3 (no external code dependencies, so no need for using Pip or the like)
- Tunnel your `localhost:8545` to a `json-rpc` instance of Parity with `--tracing` support enabled
- Run `python get_nonce.py` or `python scan.py` as described above. Or use `--help` to get minimal rescue
