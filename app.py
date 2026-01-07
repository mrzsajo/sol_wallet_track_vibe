import streamlit as st
import requests
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict

# ---------------- CONFIG ----------------
SOLANA_RPC = "https://api.mainnet-beta.solana.com"
TX_LIMIT = 50

SYSTEM_PROGRAM = "11111111111111111111111111111111"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
# ----------------------------------------

def rpc_call(method, params):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    r = requests.post(SOLANA_RPC, json=payload)
    return r.json().get("result")

def get_signatures(wallet):
    return rpc_call(
        "getSignaturesForAddress",
        [wallet, {"limit": TX_LIMIT}]
    ) or []

def get_transaction(signature):
    return rpc_call(
        "getTransaction",
        [signature, {"encoding": "jsonParsed"}]
    )

def analyze_wallet(wallet):
    links = defaultdict(lambda: {
        "sol_transfers": 0,
        "token_transfers": 0,
        "shared_programs": set(),
        "shared_tokens": set(),
        "funded_by_same": False,
        "score": 0
    })

    funding_wallet = None
    sigs = get_signatures(wallet)

    for s in sigs:
        tx = get_transaction(s["signature"])
        if not tx:
            continue

        message = tx["transaction"]["message"]
        instructions = message.get("instructions", [])

        for ix in instructions:
            program = ix.get("programId")

            # Track program usage safely
            if program:
                for acc in message.get("accountKeys", []):
                    if isinstance(acc, str) and acc != wallet:
                        links[acc]["shared_programs"].add(program)

            # SOL transfers
            if program == SYSTEM_PROGRAM and "parsed" in ix:
                info = ix["parsed"]["info"]
                src = info.get("source")
                dst = info.get("destinat
