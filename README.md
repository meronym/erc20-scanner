# ERC20 Scanner
*Monitors the balance changes of an ERC20 token contract.*

This is a bytecode analyzer that scans through the traces of a given transaction and figures out which token holder addresses had their corresponding balances changed as a result of the tx execution.

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

## Showcase
### Binance Token (BNB)
https://etherscan.io/address/0xB8c77482e45F1F44dE1745F52C74426C631bDD52#code
Market cap: $842M

```shell=
$ ./get_nonce.py --sample=0x7cd824bc5c11a16dc52f738fef5c6e3aca923af7a7cd9ecc136547c9606eac13

Token contract: 0xb8c77482e45f1f44de1745f52c74426c631bdd52
Balance map nonce: 5
```

- Opaque initial allocation in the contract constructor - doesn't emit `Transfer()`.

```shell=
$ ./scan.py --nonce=5 --tx=0x436fc7d21ed4a0a634f41b50ccb42fca12be7322de5bf9a20c97bdccbb5b2a04

Holder:0x00c5e04176d95a286fcce0e68c683ca0bfec8454 +200000000000000000000000000 Tx:0x436fc7d21ed4a0a634f41b50ccb42fca12be7322de5bf9a20c97bdccbb5b2a04
```

- Available balances can change via non-standard `freeze()` and `unfreeze()`
```shell=
$ ./scan.py --nonce=5 --tx=0x72af0f55b97b033af3b6e6162463681730c6429d0bc9c6c6ae9ad595aa2fbc57

Holder:0x00c5e04176d95a286fcce0e68c683ca0bfec8454 -64000000000000000000000000 Tx:0x72af0f55b97b033af3b6e6162463681730c6429d0bc9c6c6ae9ad595aa2fbc57
```

- Emits `Burn()` instead of `Transfer(_, 0x0)`
```shell=
$ ./scan.py --nonce=5 --tx=0xbc4290d9bd404f03575db80446bd82954698c3fe99729d1eb098a765bb0e479b

Holder:0x24b29cc8a5570bf728bd56679e1089d6c27891bb -10 Tx:0xbc4290d9bd404f03575db80446bd82954698c3fe99729d1eb098a765bb0e479b
```

### Maker (MKR)
https://etherscan.io/address/0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2#code

Market cap: $276M
- Emits `Mint()` and `Burn()` instead of `Transfer(_, _)`


### Holo (HOT)
https://etherscan.io/address/0x6c6ee5e31d828de241282b9606c8e98ea48526e2#code

Market cap: 166M
- Emits a `Mint()` event instead of `Transfer(0x0, _)`
- Non-standard `Burn()` event, doesn't log the holder address

### 0X (ZRX)
https://etherscan.io/address/0xe41d2489571d322189246dafa5ebde1f4699f498#code

Market cap: $146M
- Doesn't log initial token allocation in constructor

### BasicAttentionToken (BAT)
https://etherscan.io/address/0x0d8775f648430679a709e98d2b0cb6250d2887ef#code

Market cap: $140M
- Creates token supply with dedicated ICO functions, logs it with a custom `CreateBAT()` event
- Participants can ask refunds during the ICO, these are logged with a custom `LogRefund()` event


### ChainLink Token (LINK)
https://etherscan.io/address/0x514910771af9ca656af840dff83e8264ecf986ca#code

Market cap: $140M
- Doesn't log initial token allocation in constructor


### FirstBlood Token (ST)
https://etherscan.io/address/0xaf30d2a7e90d7dc361c8c4585e9bb7d2f6f15bc7#code

Market cap: $2M
- Initial allocations from `allocateBountyAndEcosystemTokens()` are not logged.
