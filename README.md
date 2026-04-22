# pathcourse-sdk

Official Python SDK for the [PathCourse Health](https://pathcoursehealth.com) AI gateway.

**Pay-per-inference billing in USDC on Base L2 via x402. No accounts required.**

---

## Install

```bash
pip install pathcourse-sdk
```

## How PathCourse works (in 30 seconds)

PathCourse is built for autonomous agents. You don't sign up. There's no dashboard. You fund an on-chain wallet, claim an API key, and make inference calls — all programmatically.

1. Your agent has (or creates) a Base L2 wallet holding at least **25 USDC**.
2. You send that USDC to the PCH treasury wallet.
3. You call `pathcourse.claim_key(tx_hash, wallet)` to retrieve your API key.
4. You construct `PathCourseClient(api_key=...)` and make inference calls.
5. Balance is deducted per request. Check it any time with `client.get_balance()`.

No credit card. No KYC. No human in the loop.

---

## First-time setup — get an API key

**Requirements:** a Base L2 wallet and at least 25 USDC in it. Treasury wallet address is published at [gateway.pathcoursehealth.com/.well-known/agent.json](https://gateway.pathcoursehealth.com/.well-known/agent.json) under `payment.treasury_wallet`.

```python
import pathcourse

# Step 1: You've already sent >= 25 USDC to the PCH treasury wallet on Base.
#         Capture the tx_hash and the wallet address you sent from.

# Step 2: Claim your API key. Polls up to ~3 minutes while the deposit confirms
#         and your account provisions.
result = pathcourse.claim_key(
    tx_hash="0xYourDepositTxHash",
    wallet="0xYourSendingWallet",
)

print(result["api_key"])      # pch_prod_b_...
print(result["tier"])         # uncertified | bronze | silver | gold
print(result["balance_usdc"]) # e.g. "25.00000000"

# Store result["api_key"] securely. It won't be shown again via this endpoint.
```

Set the key as an environment variable for future runs:

```bash
export PCH_API_KEY="pch_prod_b_..."
```

---

## Quick Start (once you have a key)

```python
from pathcourse import PathCourseClient, PCH_FAST

client = PathCourseClient()  # reads PCH_API_KEY from env
client.verify_key()          # confirms the key works (cheap, no billing)

response = client.chat(
    model=PCH_FAST,
    messages=[{"role": "user", "content": "Explain x402 micropayments in one paragraph."}],
)
print(response.text)
```

### One-call self-profile

```python
# Everything a headless agent needs to know about itself in one request
me = client.me()
print(me["tier"], me["balance"]["balance_usdc"], me["reputation"]["path_score"])
print(me["models_available"])   # models this tier can actually call
```

### Let the gateway pick the model

```python
hint = client.suggest_model(
    messages=[{"role": "user", "content": "Refactor this function and explain the trade-offs"}],
    max_tokens=2000,
)
# { "recommended_model": "pch-coder", "complexity": 0.52, "alternatives": [...] }
```

## Embeddings, translation, rerank

```python
from pathcourse import PathCourseClient, PCH_EMBED

client = PathCourseClient()

emb = client.embed("The quick brown fox jumps over the lazy dog.")
print(len(emb.embeddings[0]))  # embedding dimension

fr = client.translate("Hello world", target_language="fr")
print(fr["translated_text"])   # "Bonjour le monde"

ranked = client.rerank(
    query="how does x402 work?",
    documents=["USDC is a stablecoin...", "x402 is an HTTP status code...", "Base is an L2..."],
    top_n=2,
)
```

## Account controls

```python
# Current balance + top-up instructions
bal = client.get_balance()
print(bal["balance_usdc"], bal["low_balance"])

# Spend history from the on-chain ledger
usage = client.get_usage(limit=20)
print(usage["summary"]["total_spend_usdc"])

# Days of service at current burn rate
runway = client.get_runway()
print(runway["runway_days"], runway["status"])

# Server-side daily spend cap (resets at UTC midnight; pass 0 to remove)
client.set_budget(daily_limit_usdc=10.00)

# Webhook alerts when balance drops below threshold
client.register_webhook(
    url="https://my-agent.example.com/pch-events",
    threshold_usdc=25.00,
)
```

## Models

| Constant | Model | Use Case | Price |
|---|---|---|---|
| `PCH_FAST` | pch-fast | Fast reasoning, classification, routing | $0.44/M tokens |
| `PCH_PRO` | pch-pro | Deep reasoning, multi-step planning | $1.96/M tokens |
| `PCH_CODER` | pch-coder | Code generation, debugging | $3.50/M tokens |
| `PCH_IMAGE` | pch-image | Text-to-image generation | $0.028/image |
| `PCH_AUDIO` | pch-audio | Text-to-speech (standard) | $1.85/M chars |
| `PCH_AUDIO_PREMIUM` | pch-audio-premium | Text-to-speech (premium) | $37.00/M chars |
| `PCH_DOCUMENTS` | pch-documents | Document parsing, OCR | $0.26 in / $1.48 out per M tokens |
| `PCH_TALK` | pch-talk | Voice conversation | $0.001/min |
| `CLAUDE_HAIKU` | claude-haiku | Third-party (Silver+) | Common rate |
| `CLAUDE_SONNET` | claude-sonnet | Third-party (Gold) | Common rate |
| `PCH_EMBED` | pch-embed | Text embeddings | $0.015/M tokens |
| `PCH_TRANSCRIBE` | pch-transcribe | Speech-to-text | $0.0008/min |
| `PCH_TRANSLATE` | pch-translate | Translation | $0.08/M chars |
| `PCH_EXTRACT` | pch-extract | Zero-shot entity extraction | $0.012/M tokens |
| `PCH_RERANK` | pch-rerank | Retrieval reranking | $0.025/M tokens |

Machine-readable rate sheet: [gateway.pathcoursehealth.com/v1/pricing](https://gateway.pathcoursehealth.com/v1/pricing).

Call `client.get_models(scope="my_tier")` to list only the models your current tier can access.

## Additional capabilities

Every PCH API key unlocks four more capabilities beyond inference. Full working examples in [pch-integration-examples](https://github.com/pathcourse-health/pch-integration-examples).

- **`client.memory`** — persistent embedding store with semantic retrieval (`store`, `retrieve`, `update`, `forget`, `summarize`, namespaces)
- **`client.reputation`** — on-chain-compatible agent identity + Path Score (`score`, `check`, `history`, `erc8004`)
- **`client.obs`** — trace/span lifecycle, anomalies, analytics, cost attribution (`trace_start`, `trace_end`, `analytics`, `cost_attribution`)
- **`client.routing`** — agent discovery + registration (`find`, `register`, `heartbeat`, `available`)

## Environment variables

- `PCH_API_KEY` — your PathCourse API key
- `PCH_BASE_URL` — override gateway URL (default: `https://gateway.pathcoursehealth.com`)

## Error handling

```python
from pathcourse import (
    PathCourseClient,
    InsufficientBalanceError, AuthenticationError,
    ModelNotInTierError, InferenceUnavailableError,
)

client = PathCourseClient()

try:
    client.chat(model="pch-pro", messages=[{"role": "user", "content": "hi"}])
except InsufficientBalanceError:
    # balance hit the $10 floor — top up via the treasury_wallet
    ...
except AuthenticationError:
    # key is invalid or the service is suspended
    ...
except ModelNotInTierError:
    # this tier can't access the requested model — upgrade cert or pick another
    ...
```

## Settlement

All billing is in **USDC on Base L2** (chain_id 8453) via the **x402** payment protocol. USDC contract: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`. No accounts, no credit cards, no KYC.

## Links

- [PathCourse Platform](https://pathcoursehealth.com)
- [Agent Card (A2A discovery)](https://gateway.pathcoursehealth.com/.well-known/agent.json)
- [Live rate sheet](https://gateway.pathcoursehealth.com/v1/pricing)
- [Model listing (OpenAI-compatible)](https://gateway.pathcoursehealth.com/v1/models)
- [GitHub](https://github.com/pathcourse-health/pathcourse-sdk)
