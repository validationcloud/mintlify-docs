# GitBook migration

The site content was generated from the GitBook Git Sync exports in `validationcloud/docs`:

| Mintlify folder | Source branch (`validationcloud/docs`) | Export folder |
| --------------- | -------------------------------------- | ------------- |
| `v1/`           | `migration`                            | `v1/`         |
| `staking/`      | `migration-staking`                    | `staking/`    |
| `mavrik/`       | `migration-mavrik`                     | `mavrik/`     |
| `agents/`       | `main` (added in PR #71)               | `agents/`     |

URLs match the GitBook site (`docs.validationcloud.io/v1/...`, `/staking/...`, `/mavrik/...`): all 1,652 migrated page URLs return 200 on GitBook.

## Redirects

The GitBook sites have no site-level redirects (checked with the GitBook API). GitBook does serve automatic redirects, and `docs.json` reproduces them as 63 rules covering 158 URLs, each verified against the live site:

- **Page moves:** 108 Node API redirects come from page renames in the `validationcloud/docs` history and from file paths that differ from the published URL (for example `xrpl/` and `robinhood/`). 17 Staking redirects come from the GitBook change-request revisions.
- **Section URLs:** 33 section URLs (for example `/v1/aptos` or `/staking/solana`) redirect to their first page.
- **Extras:** `/v1/about/admin-api-keys/models` redirects to the Admin API overview, and the 2023-era `/v1/execution-api/*` paths redirect to `/v1/ethereum/execution-api/*`.

The rules live in `migration/docs.base.json` and are copied into `docs.json` when the converter runs.

## Re-run the conversion

Re-run this if GitBook content changes before cutover. It overwrites the generated folders and `docs.json`.

```bash
EXPORT=$(mktemp -d)
cd ~/git/docs && git fetch origin
git archive origin/migration v1 | tar -x -C "$EXPORT"
git archive origin/migration-staking staking | tar -x -C "$EXPORT"
git archive origin/migration-mavrik mavrik | tar -x -C "$EXPORT"
git archive origin/main agents | tar -x -C "$EXPORT"

cd ~/git/mintlify-docs
rm -rf v1 staking mavrik agents snippets
python3 -I migration/convert.py "$EXPORT" . migration/docs.base.json
npx mint validate && npx mint broken-links
```

Edit `migration/docs.base.json` (not `docs.json`) for site settings until the migration is final.

## What the converter does

- `README.md` becomes `index.mdx`; the first `# Heading` becomes the `title`, and the `SUMMARY.md` label becomes `sidebarTitle` when it differs.
- `SUMMARY.md` becomes one navigation tab per section, with nested items as groups that have a `root` page.
- Hints become callouts, tabs become `Tabs`, and tabs holding only code blocks become `CodeGroup`.
- `{% openapi %}` and `{% swagger %}` blocks become `openapi:` frontmatter. Only referenced specs are copied, converted to JSON and patched where GitBook tolerated invalid schemas.
- The GitBook org-level specs, which are not in the export, are added by hand:
  - Admin API: from `node-api/docs/adminapi/swagger.json`, with the server set to `https://api.validationcloud.io/admin/v1`.
  - Staking API: from the `staking swagger 9th april 2025 2.yaml` asset, which matches the live endpoints.
- GitBook page covers (`cover:` frontmatter) become an `<img className="page-cover">` banner at the top of the page, styled in `style.css` to GitBook's 1990×480 frame. Mintlify has no cover field, so the banner sits below the page title instead of above it.
- `<details>` becomes `Accordion`, `<figure>` becomes an image or a `Frame` with a caption, and `<mark style>` becomes a styled `span`.
- Relative `.md` links, absolute `docs.validationcloud.io` links and `app.gitbook.com` editor links become site-relative paths.
