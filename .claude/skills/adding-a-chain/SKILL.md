---
name: adding-a-chain
description: Use when onboarding, adding or documenting a new blockchain or network in the Node API docs (nodeapi/), adding a testnet to an existing chain, or moving a chain from Private to public Node API in this Validation Cloud Mintlify repo.
---

# Adding a chain to the Node API docs

## Overview

A **public** chain (customers create endpoints in the app) gets its own folder, overview, sidebar entry, home card and supported-chains rows. A **private** chain (provisioned on request) only gets rows on the supported chains page. Most new pages are copied from a similar chain, and copying is where the mistakes come from: other chains' hosts, links and example results left behind. `scripts/check-chains.py` catches the structural ones; the rest is on you.

## 1. Gather the facts first

Ask the user for anything you can't find. Don't guess chain IDs, URLs or costs.

| Fact | Where it comes from |
| --- | --- |
| Networks we run (mainnet, testnet name) | Infra repo `validationcloud/kubernetes-blockchain-nodes`: `blockchains/<chain>/clusters/values-<network>-prd-*.yaml` (a `networks/` file alone doesn't mean it's deployed) |
| Public or private | `node-api` repo `internal/domain/networks/types.go`: `HideOnWebApp: true` means private. Or ask |
| Methods and compute unit costs | Admin API `GET https://api.validationcloud.io/admin/v1/compute-unit-costs`, or the MCP tool `nodeapi.get_compute_unit_costs` (`<chain>/mainnet`) |
| Chain ID | `eth_chainId` on the chain's public RPC, or chainid.network |
| Endpoint hosts | `https://<network>.<slug>.validationcloud.io/v1/<YOUR_API_KEY_HERE>`; EVM WebSocket `wss://<network>.<slug>.validationcloud.io/v1/wss/<YOUR_API_KEY_HERE>`. The host slug can differ from the folder (`robinhood-chain` → `robinhood`, `xrp-ledger-xrpl` → `xrpl`). Check each host: `curl -s -o /dev/null -w '%{http_code}' https://<host>/v1/x` gives `401` when it exists; a DNS error means the network isn't routed yet, so stop and ask. A `401` proves the host, not WebSocket support |
| Archive depth, WSS, Debug, Trace | Infra values files, the Admin API `GET /chains`, or ask |
| Logo | Symbol id in `~/git/frontend/packages/fractal-ui/src/assets/sprite.svg` (same mapping as fractal-ui's `ProtocolLogo`) |
| Cover image | Design team: `nodeapi/assets/<folder>-overview-2x.png`, 3980×960. Never reuse another chain's cover; it shows that chain's name |
| Explorer, upstream docs, native token | The chain's own site; verify every link |

## 2. Private chain only

Add one row per network to `nodeapi/about/supported-chains.mdx` in alphabetical order, with Availability `Private` and URL `Available once provisioned`. Then go to step 4. Nothing else changes.

## 3. Public chain

1. **Method pages** in `nodeapi/<folder>/<api>/<method>.mdx` (folders such as `execution-api`, `debug-api`, `trace-api`). Copy them from the chain on the closest stack: OP Stack → `optimism` or `base`, Arbitrum Orbit → `arbitrum`, other EVM → `ethereum`. A method the source chain lacks can come from any other chain that documents it. On every copied page:
   - replace hosts and chain names; tab titles stay `mainnet` / `testnet` (or the network's name, such as `devnet`)
   - set `This method will use \`N\` [Compute Units](/nodeapi/about/billing).` from the cost source
   - replace chain-specific example results with this chain's values: `eth_chainId` (hex chain ID), `net_version` (decimal, and its list of network IDs), block numbers and addresses
   - delete pages for methods the chain doesn't serve, and `eth_subscribe` / `eth_unsubscribe` when there is no WebSocket
2. **Overview** `nodeapi/<folder>/overview.mdx` from `templates/chain-overview.mdx`. `AGENTS.md` describes the section order. Copy Getting Started from the new `eth_blockNumber` page. The Compute Units table lists every method page, with the same costs.
3. **Logo:** add `'<folder>': '<sprite-id>'` to `LOGOS` in `scripts/export-chain-logos.py`, then run `python3 scripts/export-chain-logos.py`. That writes `nodeapi/assets/chains/<folder>.svg` and `chain-logos.css`.
4. **Sidebar** in `docs.json`: in the Node API tab's `Chains` group, add an entry in alphabetical order by display name:
   ```json
   { "group": "<Chain name>", "icon": "/nodeapi/assets/chains/<folder>.svg", "root": "nodeapi/<folder>/overview",
     "pages": [ { "group": "Execution API", "pages": ["nodeapi/<folder>/execution-api/eth_blocknumber", "..."] } ] }
   ```
5. **Home card** in `nodeapi/index.mdx`, in alphabetical order:
   `<Card title="<Chain name>" icon="/nodeapi/assets/chains/<folder>.svg" href="/nodeapi/<folder>/overview" horizontal />`
6. **Supported chains:** one row per network, with the chain name linked to the overview and Availability `Node API`. If the chain was private, update its existing row.

A new chain needs no redirects; it has no old URLs. Don't add folder redirects like the ones from the GitBook migration. Leave `migration/` alone. Add a changelog entry (`nodeapi/about/changelog.mdx`) only if the user asks.

## 4. Verify, then open a PR

```bash
python3 scripts/check-chains.py      # template order, cost table, sidebar coverage, other chains' hosts and links
npx -y mint@4.2.1040 validate        # same CLI version as CI (.github/workflows/broken-links.yml)
npx -y mint@4.2.1040 broken-links
grep -rni '<source-chain-name>' nodeapi/<folder>    # leftovers from the chain you copied
npx -y mint@4.2.1040 dev --port 3333 # check the sidebar icon, logo before the title, home card and cover, light and dark
```

The only `grep` matches that may remain are upstream reference links, such as `ethereum.org` on EVM method pages.

Open a pull request. CI runs `broken-links` and `check-chains.py` on it.

## Common mistakes

| Mistake | What to check |
| --- | --- |
| Another chain's endpoint host left in an example | `check-chains.py` flags it |
| "See also" link pointing at the source chain's page | `check-chains.py` flags it |
| Copied `eth_chainId` / `net_version` result or network ID list from another chain | Compare with the chain ID in the supported chains table |
| Overview cost table out of sync with the method pages | `check-chains.py` flags it |
| Testnet listed that isn't deployed, or WebSocket shown when unsupported | The infra `clusters/` files and the 401 host check |
| Generic "Endpoint Capabilities" section added | Not part of the template; `check-chains.py` flags it |
