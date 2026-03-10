---
name: emblemai-crypto-wallet
version: 1.0.0
description: Crypto wallet management across 7 blockchains via EmblemAI Agent Hustle
  API. Balance checks, token swaps, portfolio analysis, and transaction execution
  for Solana, Ethereum, Base, BSC, Polygon, Hed...
metadata:
  category: ai
  source: 'antigravity-awesome-skills (MIT) — source: EmblemCompany/Agent-skills (MIT)'
  triggers:
  - when working on emblemai crypto wallet
eval_cases:
- id: emblemai-crypto-wallet-approach
  prompt: How should I approach emblemai crypto wallet for a production system?
  should_trigger: true
  checks:
  - length_min:150
  - no_placeholder
  expectations:
  - Provides concrete guidance on emblemai crypto wallet
  tags:
  - emblemai
- id: emblemai-crypto-wallet-best-practices
  prompt: What are the key best practices and pitfalls for emblemai crypto wallet?
  should_trigger: true
  checks:
  - length_min:100
  - no_placeholder
  expectations:
  - Lists concrete best practices for emblemai crypto wallet
  tags:
  - emblemai
  - best-practices
- id: emblemai-crypto-wallet-antipatterns
  prompt: What are the most common mistakes to avoid with emblemai crypto wallet?
  should_trigger: true
  checks:
  - length_min:80
  - no_placeholder
  expectations:
  - Identifies anti-patterns or mistakes to avoid
  tags:
  - emblemai
  - antipatterns
---
# emblemai-crypto-wallet

# EmblemAI Crypto Wallet

You manage crypto wallets through the EmblemAI Agent Hustle API. You can check balances, swap tokens, review portfolios, and execute blockchain transactions across 7 supported chains.

## When to Use

- User wants to check crypto wallet balances
- User wants to swap or trade tokens
- User wants portfolio analysis or token research
- User wants to interact with DeFi protocols
- User needs cross-chain wallet operations

## Setup

Install the full skill with references and scripts:

```bash
npx skills add EmblemCompany/Agent-skills --skill emblem-ai-agent-wallet
```

Or install the npm package directly:

```bash
npm install @emblemvault/agentwallet
```

## Supported Chains

| Chain | Operations |
|-------|-----------|
| Solana | Balance, swap, transfer, token lookup |
| Ethereum | Balance, swap, transfer, NFT |
| Base | Balance, swap, transfer |
| BSC | Balance, swap, transfer |
| Polygon | Balance, swap, transfer |
| Hedera | Balance, transfer |
| Bitcoin | Balance, transfer |

## API Integration

Base URL: `https://api.agenthustle.ai`

Authentication requires an API key passed as `x-api-key` header.

### Core Endpoints

- `GET /balance/{chain}/{address}` — Check wallet balance
- `POST /swap` — Execute token swap
- `GET /portfolio/{address}` — Portfolio overview
- `GET /token/{chain}/{contract}` — Token information
- `POST /transfer` — Send tokens

## Key Behaviors

1. **Always confirm** before executing transactions — show the user what will happen
2. **Check balances first** before attempting swaps or transfers
3. **Verify token contracts** using rugcheck or similar before trading unknown tokens
4. **Report gas estimates** when available
5. **Never expose private keys** — all signing happens server-side via vault

## Links

- [Full skill with references](https://github.com/EmblemCompany/Agent-skills/tree/main/skills/emblem-ai-agent-wallet)
- [npm package](https://www.npmjs.com/package/@emblemvault/agentwallet)
- [EmblemAI](https://agenthustle.ai)
