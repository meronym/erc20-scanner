#! /usr/bin/env python
# coding: utf8

from lib.keccak import Keccak256
from lib.rpc import Parity


ADDRESS_MASK = int('0xffffffffffffffffffffffff0000000000000000000000000000000000000000', 16)
ERC20_TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ERC20_BALANCE_SELECTOR = '0x70a08231'

node = Parity('http://localhost:8545')    


def get_storage_location(key, nonce):
    assert len(key) == 2 + 64
    msg = bytes.fromhex(key[2:])
    msg += bytes.fromhex('{0:064x}'.format(nonce))
    return '0x' + Keccak256(msg).hexdigest()


def dump_stack(ops):
    values = set()
    for op in ops:
        for val in op['ex']['push']:
            assert val.startswith('0x') and len(val) <= 2 + 64
            values.add('0x' + val[2:].zfill(64))
    return values


def parse_seed(seed_tx):
    # get the transaction receipt
    result = node.call('eth_getTransactionReceipt', seed_tx)
    
    # find the first ERC20 Transfer() log
    transfer = [log for log in result['logs'] if log['topics'][0] == ERC20_TRANSFER_TOPIC][0]

    # get the token contract address
    token_contract = transfer['address']
    sender_address = transfer['topics'][1]
    assert sender_address.startswith('0x') and len(sender_address) == 2 + 64
    print('Token contract:', token_contract)

    # create a set of storage locations that got changed in the token contract by this transaction
    result = node.call('trace_replayTransaction', seed_tx, ['stateDiff'])
    sloc_changed = set(result['stateDiff'][token_contract]['storage'].keys())

    # monitor the stack on a balanceOf(sender_address) call
    data = ERC20_BALANCE_SELECTOR + sender_address[2:]
    result = node.call('trace_call', {'data': data, 'to': token_contract}, ['vmTrace'], 'latest')
    stack_values = dump_stack(result['vmTrace']['ops'])

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
    # retrieve the state diffs on the token contract induced by tx
    result = node.call('trace_replayTransaction', tx, ['stateDiff'])
    token_diffs = result['stateDiff'][token_contract]['storage']
    sloc_changed = set(token_diffs.keys())

    # collect all the address-like values that got pushed on the stack
    result = node.call('trace_replayTransaction', tx, ['vmTrace'])
    holder_candidates = {
        val for val in dump_stack(result['vmTrace']['ops'])
        if int(val, 16) & ADDRESS_MASK == 0
    }

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
        if '*' in token_diffs[sloc]:
            old_value = int(token_diffs[sloc]['*']['from'], 16)
            new_value = int(token_diffs[sloc]['*']['to'], 16)
        elif '+' in token_diffs[sloc]:
            old_value = None
            new_value = int(token_diffs[sloc]['+'], 16)
        events.append((tx, holder, old_value, new_value))
    return events


def parse_targets(txs, token_contract, nonce):
    balance_events = []
    for tx in txs:
        balance_events.extend(monitor_tx(tx, token_contract, nonce))
    return balance_events


if __name__ == '__main__':
    seed_tx = '0x7cd824bc5c11a16dc52f738fef5c6e3aca923af7a7cd9ecc136547c9606eac13'
    txs = [
        '0x436fc7d21ed4a0a634f41b50ccb42fca12be7322de5bf9a20c97bdccbb5b2a04',
        # '0xd9c9e291a3f8bf892b96c37266dbe5b1acefec23ab5f513fd3edbb4a7f12fea1',
        '0x99aca286a38ec8382bcadb13a176d9f2b20fd2ddb8670939e0b6324266744d63',
    ]
    token_contract, nonce = parse_seed(seed_tx)
    events = parse_targets(txs, token_contract, nonce)
    for ev in events:
        print(ev)
