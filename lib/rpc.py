import json
import urllib.request


class Parity:
    def __init__(self, rpc_endpoint):
        self.endpoint = rpc_endpoint
    
    def call(self, method, *args):
        payload = json.dumps({
            "id": 0,
            "jsonrpc": "2.0",
            "method": method,
            "params": args
        }).encode('ascii')
        headers = {
            "Content-Type": "application/json"
        }
        req = urllib.request.Request(self.endpoint, data=payload, headers=headers)
        res = urllib.request.urlopen(req).read()
        return json.loads(res)['result']
