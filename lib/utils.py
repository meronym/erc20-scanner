from .keccak import Keccak256


def get_storage_location(key, nonce):
    assert len(key) == 2 + 64
    msg = bytes.fromhex(key[2:])
    msg += bytes.fromhex('{0:064x}'.format(nonce))
    return '0x' + Keccak256(msg).hexdigest()


def parse_op(op, values):
    # op = { 'cost': int, 'ex': {}, 'pc': int, 'sub': <trace or null> }
    for val in op['ex']['push']:
        assert val.startswith('0x') and len(val) <= 2 + 64
        values.add('0x' + val[2:].zfill(64))
    if op['sub'] is not None:
        parse_trace(op['sub'], values)


def parse_trace(trace, values):
    # trace = { 'code': '', 'ops': [op1, op2, ...] }
    for op in trace['ops']:
        parse_op(op, values)


def dump_stack(trace):
    values = set()
    # double recursivity ftw
    parse_trace(trace, values)
    return values
