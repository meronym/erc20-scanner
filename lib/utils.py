
from .keccak import Keccak256


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


