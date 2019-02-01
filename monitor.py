#! /usr/bin/env python
# coding: utf8

from lib.keccak import Keccak256
from lib.rpc import Parity


ERC20_TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ERC20_BALANCE_SELECTOR = '0x70a08231'

node = Parity('http://localhost:8545')    


def get_storage_location(key, nonce):
    assert key.startswith('0x') and len(key) < 2 + 64
    msg = bytes.fromhex(key[2:].zfill(64))
    msg += bytes.fromhex('{0:064x}'.format(nonce))
    return '0x' + Keccak256(msg).hexdigest()


def parse_seed(seed_tx):
    # get the transaction receipt
    result = node.call('eth_getTransactionReceipt', seed_tx)
    
    # find the first ERC20 Transfer() log
    transfer = [log for log in result['logs'] if log['topics'][0] == ERC20_TRANSFER_TOPIC][0]

    # get the token contract address
    token_contract = transfer['address']
    sender_address = '0x' + transfer['topics'][1][-40:]
    receiver_address = '0x' + transfer['topics'][2][-40:]
    print('Token contract:', token_contract)

    # create a set of storage locations that got changed in the token contract by this transaction
    result = node.call('trace_replayTransaction', seed_tx, ['stateDiff'])
    sloc_changed = set(result['stateDiff'][token_contract]['storage'].keys())

    # monitor the stack on a balanceOf(sender_address) call
    data = ERC20_BALANCE_SELECTOR + sender_address[2:].zfill(64)
    result = node.call('trace_call', {'data': data, 'to': token_contract}, ['vmTrace'], 'latest')
    stack_values = set()
    for op in result['vmTrace']['ops']:
        stack_values.update(op['ex']['push'])
    
    # the storage location of the sender_address balance should be present in both sets
    common_values = stack_values & sloc_changed
    assert len(common_values) == 1
    sender_sloc = common_values.pop()

    # brute force the nonce
    nonce = 0
    while 1:
        if get_storage_location(sender_address, nonce) == sender_sloc:
            break
        nonce += 1

    print('Found nonce:', nonce)
    return token_contract, nonce


def monitor_tx(tx, token_contract, nonce):
    # retrieve the state diffs on the token contract
    result = node.call('trace_replayTransaction', tx, ['stateDiff'])
    token_diffs = result['stateDiff'][token_contract]['storage']
    sloc_changed = set(token_diffs.keys())

    # collect all the address-like values that got pushed on the stack
    result = node.call('trace_replayTransaction', tx, ['vmTrace'])
    holder_candidates = set()
    for op in result['vmTrace']['ops']:
        holder_candidates.update(
            val for val in op['ex']['push'] if len(val) <= 42
        )

    # compute the minified rainbow table
    rainbow_table = {
        get_storage_location(candidate, nonce): candidate
        for candidate in holder_candidates
    }

    # get the subset of diffs related to the balance mapping
    balance_slocs = sloc_changed & set(rainbow_table.keys())

    # export the events
    events = []
    for sloc in balance_slocs:
        holder = rainbow_table[sloc]
        old_value = int(token_diffs[sloc]['*']['from'], 16)
        new_value = int(token_diffs[sloc]['*']['to'], 16)
        events.append((tx, holder, old_value, new_value))
    return events


def parse_targets(txs, token_contract, nonce):
    balance_events = []
    for tx in txs:
        balance_events.extend(monitor_tx(tx, token_contract, nonce))
    return balance_events


if __name__ == '__main__':
    seed_tx = '0x8ab5e67b3d6d0ebfb21dc98b0824d24daf0434efcc9c9db6eacfb5b313006313'
    txs = [
        '0x8ab5e67b3d6d0ebfb21dc98b0824d24daf0434efcc9c9db6eacfb5b313006313',
    ]
    token_contract, nonce = parse_seed(seed_tx)
    events = parse_targets(txs, token_contract, nonce)
    for ev in events:
        print(ev)
