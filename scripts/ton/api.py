"""
TON API wrapper — all requests go through Exton proxy at api.exton.app.

User's TONAPI_KEY is NEVER stored on their device.
Exton proxy handles authentication to tonapi.io internally.
"""

import json
import urllib.request
import urllib.parse
import urllib.error

# All TON API calls go through our proxy — user never needs an API key
EXTON_API_BASE = "https://api.exton.app/ton"


_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "ExtonWalletSkill/1.0",
}


def _api_get(path: str) -> dict:
    """GET request to Exton TON proxy."""
    url = f"{EXTON_API_BASE}{path}"
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _api_post(path: str, body: dict) -> dict:
    """POST request to Exton TON proxy."""
    url = f"{EXTON_API_BASE}{path}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers={
        **_HEADERS, "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def get_balance(address: str) -> dict:
    """Get account balance and status."""
    encoded = urllib.parse.quote(address, safe="")
    data = _api_get(f"/v2/accounts/{encoded}")
    balance_nano = data.get("balance", 0)
    status = data.get("status", "unknown")
    return {
        "balance_nano": balance_nano,
        "balance_ton": balance_nano / 1e9,
        "status": status,
    }


def get_seqno(address: str) -> int:
    """Get current sequence number for signing."""
    encoded = urllib.parse.quote(address, safe="")
    try:
        data = _api_get(f"/v2/wallet/{encoded}/seqno")
        return data.get("seqno", 0)
    except urllib.error.HTTPError:
        return 0


def get_transactions(address: str, limit: int = 20) -> list:
    """Get recent transactions."""
    encoded = urllib.parse.quote(address, safe="")
    data = _api_get(f"/v2/accounts/{encoded}/events?limit={limit}")
    events = data.get("events", [])
    result = []
    for event in events:
        actions = event.get("actions", [])
        for action in actions:
            action_type = action.get("type", "")
            status = action.get("status", "")
            if status != "ok":
                continue
            if action_type == "TonTransfer":
                detail = action.get("TonTransfer", {})
                result.append({
                    "type": "ton_transfer",
                    "hash": event.get("event_id", ""),
                    "timestamp": event.get("timestamp", 0),
                    "sender": detail.get("sender", {}).get("address", ""),
                    "recipient": detail.get("recipient", {}).get("address", ""),
                    "amount_nano": detail.get("amount", 0),
                    "amount_ton": detail.get("amount", 0) / 1e9,
                    "comment": detail.get("comment", ""),
                })
    return result


def broadcast(boc_base64: str) -> dict:
    """Broadcast signed BOC to TON network."""
    return _api_post("/v2/blockchain/message", {"boc": boc_base64})


def resolve_domain(domain: str) -> str:
    """Resolve .ton domain → friendly address."""
    encoded = urllib.parse.quote(domain, safe="")
    data = _api_get(f"/v2/dns/{encoded}/resolve")
    wallet = data.get("wallet", {})
    addr = wallet.get("address", "")
    if not addr:
        account = wallet.get("account", {})
        addr = account.get("address", "")
    return addr


def run_get_method(address: str, method: str) -> list:
    """Call GET method on a smart contract."""
    encoded = urllib.parse.quote(address, safe="")
    data = _api_get(f"/v2/blockchain/accounts/{encoded}/methods/{method}")
    stack = data.get("stack", [])
    result = []
    for entry in stack:
        if isinstance(entry, dict):
            entry_type = entry.get("type", "")
            if entry_type == "num":
                val = entry.get("value") or entry.get("num", "0")
                if isinstance(val, str) and val.startswith("0x"):
                    result.append(int(val, 16))
                else:
                    result.append(int(val) if val else 0)
            else:
                result.append(entry.get("value"))
        else:
            result.append(entry)
    return result


def get_jettons(address: str) -> list:
    """Get jetton balances for address."""
    encoded = urllib.parse.quote(address, safe="")
    data = _api_get(f"/v2/accounts/{encoded}/jettons")
    balances = data.get("balances", [])
    result = []
    for item in balances:
        jetton = item.get("jetton", {})
        result.append({
            "symbol": jetton.get("symbol", "?"),
            "name": jetton.get("name", ""),
            "balance": item.get("balance", "0"),
            "decimals": jetton.get("decimals", 9),
            "wallet_address": item.get("wallet_address", {}).get("address", ""),
        })
    return result
