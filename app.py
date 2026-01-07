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
        instructions = message["instructions"]

        for ix in instructions:
    program = ix.get("programId")

    # Track program usage safely
    if program:  # skip None
        for acc in message.get("accountKeys", []):
            if isinstance(acc, str) and acc != wallet:
                links[acc]["shared_programs"].add(program)



            # SOL transfers
            if ix.get("programId") == SYSTEM_PROGRAM and "parsed" in ix:
                info = ix["parsed"]["info"]
                src = info.get("source")
                dst = info.get("destination")

                if src == wallet:
                    links[dst]["sol_transfers"] += 1
                if dst == wallet:
                    links[src]["sol_transfers"] += 1
                    if not funding_wallet:
                        funding_wallet = src

            # SPL token transfers
            if ix.get("programId") == TOKEN_PROGRAM and "parsed" in ix:
                info = ix["parsed"]["info"]
                src = info.get("source")
                dst = info.get("destination")
                mint = info.get("mint")

                if src == wallet:
                    links[dst]["token_transfers"] += 1
                    links[dst]["shared_tokens"].add(mint)
                if dst == wallet:
                    links[src]["token_transfers"] += 1
                    links[src]["shared_tokens"].add(mint)

    # Funding correlation
    if funding_wallet:
        for w in links:
            sigs2 = get_signatures(w)
            for s in sigs2:
                tx = get_transaction(s["signature"])
                if not tx:
                    continue
                for ix in tx["transaction"]["message"]["instructions"]:
                    if "parsed" in ix:
                        info = ix["parsed"].get("info", {})
                        if info.get("destination") == w and info.get("source") == funding_wallet:
                            links[w]["funded_by_same"] = True

    # Scoring
    for w, d in links.items():
        score = 0
        score += d["sol_transfers"] * 10
        score += d["token_transfers"] * 12
        score += len(d["shared_tokens"]) * 8
        score += len(d["shared_programs"]) * 5
        if d["funded_by_same"]:
            score += 35
        d["score"] = min(score, 100)

    return links

# ---------------- UI ----------------
st.set_page_config(page_title="Solana Wallet Cluster Tracker", layout="wide")

st.title("🧠 Solana Wallet Cluster Tracker")
st.caption("Full on-chain activity analysis · probabilistic linking")

wallet = st.text_input("Enter Solana wallet address")

if wallet:
    with st.spinner("Analyzing Solana blockchain activity..."):
        links = analyze_wallet(wallet)

    if not links:
        st.warning("No linked wallets found.")
    else:
        st.subheader("Linked Wallets")

        for w, d in sorted(links.items(), key=lambda x: x[1]["score"], reverse=True):
            st.markdown(
                f"""
**{w}**
- SOL transfers: {d['sol_transfers']}
- Token transfers: {d['token_transfers']}
- Shared tokens: {len(d['shared_tokens'])}
- Shared programs: {len(d['shared_programs'])}
- Same funding wallet: {'✅' if d['funded_by_same'] else '❌'}
- **Confidence score: {d['score']}%**
"""
            )

        # Graph
        G = nx.Graph()
        G.add_node(wallet)

        for w, d in links.items():
            if d["score"] >= 25:
                G.add_edge(wallet, w, weight=d["score"])

        fig, ax = plt.subplots(figsize=(9, 9))
        nx.draw(G, with_labels=True, node_size=2200, font_size=7)
        st.pyplot(fig)

st.markdown("---")
st.caption("⚠️ On-chain analysis only · not proof of ownership")
