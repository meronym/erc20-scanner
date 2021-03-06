#! /usr/bin/env python
# coding: utf8

import argparse
import sys

from lib.rpc import Parity
from lib.utils import dump_stack, get_storage_location


node = Parity('http://localhost:8545')

ADDRESS_MASK = int('0xffffffffffffffffffffffff0000000000000000000000000000000000000000', 16)


def scan_tx(tx, nonce):
    # get the token contract address
    result = node.call('eth_getTransactionReceipt', tx)
    token_contract = result['to'] or result['contractAddress']

    # retrieve the state diffs on the token contract induced by tx
    result = node.call('trace_replayTransaction', tx, ['stateDiff', 'vmTrace'])
    token_diffs = result['stateDiff'][token_contract]['storage']
    sloc_changed = set(token_diffs.keys())

    # collect all 'address-like' values that got pushed on the stack
    holder_candidates = {
        val for val in dump_stack(result['vmTrace'])
        if int(val, 16) & ADDRESS_MASK == 0
    }
    print('\nAnalyzing {} candidates...'.format(len(holder_candidates)), file=sys.stderr)

    # compute the minified rainbow table
    rainbow_table = {
        get_storage_location(candidate, nonce): '0x' + candidate[-40:]
        for candidate in holder_candidates
    }

    # get the subset of diffs related to the balance mapping
    balance_slocs = sloc_changed & set(rainbow_table.keys())

    # export the events
    for sloc in balance_slocs:
        holder = rainbow_table[sloc]
        if '*' in token_diffs[sloc]:
            old_value = int(token_diffs[sloc]['*']['from'], 16)
            new_value = int(token_diffs[sloc]['*']['to'], 16)
        elif '+' in token_diffs[sloc]:
            old_value = None
            new_value = int(token_diffs[sloc]['+'], 16)
        elif '-' in token_diffs[sloc]:
            old_value = int(token_diffs[sloc]['-'], 16)
            new_value = None
        delta = (new_value or 0) - (old_value or 0)
        print('Holder:{} {:+} Tx:{}'.format(holder, delta, tx))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Scan an ERC20 contract for balance changes')
    parser.add_argument('tx', help='hash of the target tx')
    parser.add_argument('--nonce', type=int)

    args = parser.parse_args()
    scan_tx(args.tx, args.nonce)
