#! /usr/bin/env python
# coding: utf8

import argparse

from lib.rpc import Parity
from lib.utils import dump_stack, get_storage_location


ERC20_TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ERC20_BALANCE_SELECTOR = '0x70a08231'

node = Parity('http://localhost:8545')    


def get_nonce(sample_tx):
    # get the transaction receipt
    result = node.call('eth_getTransactionReceipt', sample_tx)
    
    # find the first ERC20 Transfer() log
    transfer = [log for log in result['logs'] if log['topics'][0] == ERC20_TRANSFER_TOPIC][0]

    # get the token contract address
    token_contract = transfer['address']
    sender_address = transfer['topics'][1]
    assert sender_address.startswith('0x') and len(sender_address) == 2 + 64
    print('Token contract:', token_contract)

    # create a set of storage locations that got changed in the token contract by this transaction
    result = node.call('trace_replayTransaction', sample_tx, ['stateDiff'])
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
    print('Balance map nonce:', nonce)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Scan an sample ERC20 transfer tx to determine the contract's internal balance map nonce")
    parser.add_argument('--sample', help='hash of the sample transfer tx')
    
    args = parser.parse_args()
    get_nonce(args.sample)
