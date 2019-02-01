# token-monitor
Monitor the balance changes of an ERC20 token contract

## Inputs
- A *seed transaction* is any transaction that triggered a (logged) transfer for your token of choice

We need the hash of any seed transaction for reverse engineering the memory mapping of the token contract

- The *target transactions* are the transactions for which you want to compute the balance change events
If this is a list of all the transactions that have ever changed (directly or indirectly) the state of the token contract, the resulting output will be a full list of token balance changes derived from the memory updates of the internal balance mapping.

## Outputs
- A list of *balance change events* on the form `BalanceUpdate(holderAddress, oldValue, newValue)`
