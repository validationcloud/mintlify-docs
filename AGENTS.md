> For Mintlify product knowledge (components, configuration, writing standards),
> install the Mintlify skill: `npx skills add https://mintlify.com/docs`

# Documentation project instructions

## About this project

- This is the Validation Cloud documentation site, built on [Mintlify](https://mintlify.com) and served at `docs.validationcloud.io`
- Pages are MDX files with YAML frontmatter
- Configuration lives in `docs.json`
- Run `mint dev` to preview locally
- Run `mint validate` and `mint broken-links` before committing

## Structure

Each top-level folder is one navigation tab, and its path is part of the public URL:

- `nodeapi/`: Node API (`/nodeapi/...`), one folder per chain, plus `about/`. The former `/v1/...` URLs redirect here.
- `staking/`: Staking API (`/staking/...`)
- `mavrik/`: Mavrik (`/mavrik/...`)
- `agents/`: MCP server and CLI (`/agents/...`)
- `snippets/`: shared reusable content
- `<section>/assets/`: images, and `<section>/openapi/`: OpenAPI specs (JSON)

Keep existing page paths stable. If you move a page, add a redirect in `docs.json`. API paths in the content, such as `/v1/api/...` or `https://…validationcloud.io/v1/<KEY>`, are product URLs, not docs paths, so do not rename them.

The content was migrated from GitBook. See `migration/README.md`.

## Chain logos

Chain logos come from the `fractal-ui` sprite (`~/git/frontend/packages/fractal-ui/src/assets/sprite.svg`). They appear in 3 places:

- **Sidebar:** the `icon` on each chain group in `docs.json`.
- **Node API home:** the "Supported chains" card grid in `nodeapi/index.mdx`.
- **Each chain's overview:** a `<span className="chain-logo-<folder>" />` marker at the top of the page. It puts the logo before the page title through the generated `chain-logos.css`.

To add a chain or a network, follow `.claude/skills/adding-a-chain/SKILL.md`: it covers the facts to gather, every file to touch, and the checks.

Do not edit `chain-logos.css` by hand.

## Chain overview pages

Every `nodeapi/<folder>/overview.mdx` follows `templates/chain-overview.mdx`, in this order:

1. Logo marker, cover image and the `<TryFree />` banner.
2. A short intro: what the chain is, its native token, block explorer and the chain's own developer docs.
3. `## Network Support`: the networks table (archive, HTTPS, WSS) and any notes, such as the WebSocket `ping` rule.
4. Optional chain-specific `##` sections, such as Stellar RPC v2 or ICRC tokens.
5. `## Getting Started`: one `curl` request per network, copied from a cheap method page of the same chain (`eth_blockNumber` for EVM chains), plus a `wscat` example when the chain supports WebSockets.
6. `## Compute Units`: the method cost table, always last.

Don't add generic sections such as "Endpoint Capabilities". `python3 scripts/check-chains.py` runs in CI. It checks the section order, that the Compute Units table matches the method pages, that every chain page is in the sidebar, and that no page carries another chain's endpoint host or links.

## Terminology

{/* Add product-specific terms and preferred usage */}
{/* Example: Use "workspace" not "project", "member" not "user" */}

## Style preferences

{/* Add any project-specific style rules below */}

- Use active voice and second person ("you")
- Keep sentences concise — one idea per sentence
- Use sentence case for headings
- Bold for UI elements: Click **Settings**
- Code formatting for file names, commands, paths, and code references

## Content boundaries

{/* Define what should and shouldn't be documented */}
{/* Example: Don't document internal admin features */}
