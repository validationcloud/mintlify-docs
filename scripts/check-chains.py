"""Check every Node API chain against templates/chain-overview.mdx and the rest of its pages.

For each chain group under "Chains" in docs.json (nodeapi/<folder>/overview.mdx is its root):
- overview: logo marker, cover, TryFree banner, and ## sections in order: Network Support,
  optional chain-specific sections, Getting Started (with a curl example), Compute Units last
- Compute Units table: every row links to an existing page with the same cost, and every page with a
  "will use N Compute Units" line is in the table (unless the section states one cost for all methods)
- navigation: every .mdx page in the chain's folders is in the chain's sidebar group
- copy-paste guard: no endpoint host of another chain and no link to another chain's pages
Run from the repo root: python3 scripts/check-chains.py
"""
import glob
import json
import os
import re
import sys

problems = []
HOST = re.compile(r'(?:https|wss)://[a-z0-9-]+\.([a-z0-9-]+)\.validationcloud\.io')
nav = json.load(open('docs.json'))['navigation']
node_api = next(t for t in nav['tabs'] if t.get('tab') == 'Node API')
chains = next(g for g in node_api['groups'] if g['group'] == 'Chains')['pages']


def nav_pages(group):
    for p in group.get('pages', []):
        if isinstance(p, str):
            if ' ' not in p:  # skip generated-page selectors such as "QUERY accountByAddress"
                yield p
        else:
            if p.get('root'):
                yield p['root']
            yield from nav_pages(p)


for group in chains:
    root = group.get('root', '')
    path = root + '.mdx'
    if not re.fullmatch(r'nodeapi/[^/]+/overview', root) or not os.path.exists(path):
        problems.append('docs.json: chain group "%s" needs "root": "nodeapi/<folder>/overview"' % group['group'])
        continue
    folder = root.split('/')[1]
    text = open(path).read()
    fail = lambda msg, p=path: problems.append('%s: %s' % (p, msg))

    # Overview structure (templates/chain-overview.mdx)
    if '<span className="chain-logo-%s" />' % folder not in text:
        fail('missing <span className="chain-logo-%s" /> logo marker' % folder)
    if 'className="page-cover"' not in text:
        fail('missing page cover image')
    if '<TryFree ' not in text:
        fail('missing <TryFree /> banner')
    if 'icon' not in group:
        problems.append('docs.json: chain group "%s" has no icon' % group['group'])
    body = re.sub(r'(?ms)^```.*?^```', '', text)  # ignore headings inside code blocks
    h2 = [h.strip() for h in re.findall(r'^## (.+)$', body, re.M)]
    if not h2 or h2[0] != 'Network Support':
        fail('first ## section must be "Network Support" (found %s)' % (h2[:1] or 'none'))
    if not h2 or h2[-1] != 'Compute Units':
        fail('last ## section must be "Compute Units" (found %s)' % (h2[-1:] or 'none'))
    started = ''
    if 'Getting Started' not in h2:
        fail('missing "## Getting Started"')
    elif h2.index('Getting Started') != len(h2) - 2:
        fail('"Getting Started" must come right before "Compute Units"')
    else:
        started = text.split('## Getting Started', 1)[1].split('## Compute Units', 1)[0]
        if 'curl ' not in started:
            fail('"Getting Started" has no curl example')
    if 'Endpoint Capabilities' in text:
        fail('"Endpoint Capabilities" is not part of the template; put WebSocket notes under Network Support')

    # Pages of this chain: everything in its sidebar group (a chain can span folders, e.g. icp + icp-1)
    in_nav = set(nav_pages(group)) | {root}
    folders = {p.split('/')[1] for p in in_nav}
    files = {f[:-4] for d in folders for f in glob.glob('nodeapi/%s/**/*.mdx' % d, recursive=True)}
    for missing in sorted(files - in_nav):
        problems.append('%s.mdx: not in the "%s" sidebar group in docs.json' % (missing, group['group']))
    for gone in sorted(p for p in in_nav if not os.path.exists(p + '.mdx')):
        problems.append('docs.json: "%s" points to a missing page' % gone)

    # Compute Units table vs the "will use N Compute Units" line on each page
    cu_section = text.split('## Compute Units', 1)[-1]
    rows = dict(re.findall(r'^\|\s*\[[^\]]+\]\((/nodeapi/[^)]+)\)\s*\|\s*([^|]+?)\s*\|', cu_section, re.M))
    for link, cu in rows.items():
        page = link.lstrip('/') + '.mdx'
        if not os.path.exists(page):
            page = link.lstrip('/') + '/index.mdx'  # a folder link opens its index page
        if not os.path.exists(page):
            fail('Compute Units row links to missing page %s' % link)
            continue
        m = re.search(r'will use `([\d,]+)`', open(page).read())
        # Only plain numbers are compared; cells such as "Mainnet: 1,000*" carry their own explanation
        if m and re.fullmatch(r'[\d,]+', cu) and m.group(1).replace(',', '') != cu.replace(',', ''):
            fail('Compute Units row for %s says %s, the page says %s' % (link, cu, m.group(1)))
    if not re.search(r'(?m)^All .*methods.*Compute Units', cu_section):
        for f in sorted(files):
            if '/' + f not in rows and f != root and re.search(r'will use `[\d,]+`', open(f + '.mdx').read()):
                fail('Compute Units table has no row for /%s' % f)

    # Copy-paste guard: hosts and links must belong to this chain
    own_hosts = set(HOST.findall(started))
    for f in sorted(files):
        page_text = open(f + '.mdx').read()
        for slug in sorted(set(HOST.findall(page_text)) - own_hosts):
            if own_hosts:
                problems.append('%s.mdx: endpoint host for "%s", but this chain uses %s' % (f, slug, sorted(own_hosts)))
        for other in sorted(set(re.findall(r'\]\(/nodeapi/([^/)#]+)', page_text)) - folders - {'about'}):
            problems.append('%s.mdx: links to another chain\'s pages (/nodeapi/%s/...)' % (f, other))

if problems:
    print('\n'.join(problems))
    sys.exit('%d problem(s); see templates/chain-overview.mdx and .claude/skills/adding-a-chain/SKILL.md' % len(problems))
print('%d chains OK' % len(chains))
