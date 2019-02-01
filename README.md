# token-monitor
Monitors the balance changes of an ERC20 token contract

`./get_nonce.py` scans the bytecode of an ERC20 token contract to identify the internal nonce that's associated with the storage pattern of the balances map.

`./scan.py` analyzes the execution of an arbitrary transaction and identifies the holder addresses whose corresponding balances have changed in the internal map.
