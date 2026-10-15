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
