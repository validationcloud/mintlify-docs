"""GitBook Git Sync export -> Mintlify MDX converter for Validation Cloud docs.

Usage: python3 -I convert.py EXPORT_DIR OUT_DIR BASE_DOCS_JSON
EXPORT_DIR holds one folder per GitBook section (v1, staking, mavrik, agents), each with SUMMARY.md.
Writes MDX pages, assets, OpenAPI specs and snippets into OUT_DIR, plus OUT_DIR/docs.json
(BASE_DOCS_JSON with generated tab navigation) and a report of unresolved links on stdout.
The admin API spec is read from $NODE_API (default ~/git/node-api). See migration/README.md.
"""
import html
import json
import os
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

EXPORT, OUT = sys.argv[1], sys.argv[2]
SECTIONS = [('v1', 'Node API'), ('staking', 'Staking'), ('mavrik', 'Mavrik'), ('agents', 'Agents')]
SITE = 'https://docs.validationcloud.io'
HINTS = {'info': 'Info', 'warning': 'Warning', 'danger': 'Danger', 'success': 'Check', 'tip': 'Tip'}
# ponytail: single include in the whole export, named by hand.
SNIPPET_NAMES = {'sequencediagram-autonumb... (1).md': ('solana-staking-sequence-diagram', 'SolanaStakingSequenceDiagram')}
HTML_TAGS = ('a abbr b blockquote br caption code col colgroup dd del details div dl dt em figcaption figure '
             'h1 h2 h3 h4 h5 h6 hr i img kbd li mark ol p pre s small span strong sub summary sup table tbody '
             'td tfoot th thead tr u ul').split()
COMPONENTS = list(HINTS.values()) + ['Note', 'Tabs', 'Tab', 'CodeGroup', 'Accordion', 'Frame'] + [v[1] for v in SNIPPET_NAMES.values()]
KNOWN_TAG = re.compile(r'</?(?:%s)(?=[\s/>])[^<>]*>' % '|'.join(HTML_TAGS + COMPONENTS))
FENCE = re.compile(r'^(\s*)(`{3,}|~{3,})(.*)$')
DIRECTIVE = re.compile(r'\{%\s*(\w[\w-]*)(.*?)%\}')

STAKING_OPS = '/v1/api/ethereum/{network}/'
# GitBook org-level OpenAPI specs (not in the export): spec name -> (section, source file, dest name, pages)
ORG_SPECS = {
    'validation-cloud-admin-api': ('v1', os.path.expanduser(os.environ.get('NODE_API', '~/git/node-api')) + '/docs/adminapi/swagger.json', 'admin-api.json', [
        ('account', 'Account information', 'GET', '/account'),
        ('chains', 'Supported chains', 'GET', '/chains'),
        ('compute-unit-costs', 'Compute-unit cost list', 'GET', '/compute-unit-costs'),
        ('endpoints', 'List endpoints', 'GET', '/endpoints'),
        ('create-endpoint', 'Create an endpoint', 'POST', '/endpoints'),
        ('get-endpoint', 'Get an endpoint', 'GET', '/endpoints/{id}'),
        ('delete-endpoint', 'Delete an endpoint', 'DELETE', '/endpoints/{id}'),
        ('usage', 'Team-wide compute-unit usage', 'GET', '/usage'),
        ('endpoint-usage', 'Per-endpoint compute-unit usage', 'GET', '/endpoints/{id}/usage'),
        ('health', 'Liveness and authentication check', 'GET', '/health'),
    ]),
    'validation-cloud-staking-api-25april2025': ('staking', os.path.join(EXPORT, 'staking/.gitbook/assets/staking swagger 9th april 2025 2.yaml'), 'staking-api.yaml', [
        ('authentication', 'Authentication', 'POST', '/oauth/token'),
        ('get-validators', 'Get Validators', 'GET', STAKING_OPS + 'validators'),
        ('stake-transaction', 'Stake Transaction', 'POST', STAKING_OPS + 'stake_transaction'),
        ('broadcast-transaction', 'Broadcast Transaction', 'POST', STAKING_OPS + 'broadcast_transaction'),
        ('exit-validators', 'Exit Validators', 'POST', STAKING_OPS + 'exit_validators'),
        ('presigned-exit-request', 'Presigned Exit Request', 'POST', STAKING_OPS + 'presigned_exit_request'),
    ]),
}
ADMIN_SERVER = 'https://api.validationcloud.io/admin/v1'

report = {'unresolved': [], 'broken': [], 'openapi': []}
assets_used = {}  # (section, src_abs) -> dest rel path


def slug(name):
    base, ext = os.path.splitext(name)
    s = re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-') or 'file'
    return s + ext.lower()


def attrs(s):
    return dict(re.findall(r'([\w-]+)="([^"]*)"', s))


# ---------- page map ----------
pages = {}  # (section, src_rel) -> dict(dest, url)
for sec, _ in SECTIONS:
    root = os.path.join(EXPORT, sec)
    for d, _, fs in os.walk(root):
        if '/.gitbook' in d:
            continue
        for f in fs:
            if not f.endswith('.md') or (f == 'SUMMARY.md' and d == root):
                continue
            rel = os.path.relpath(os.path.join(d, f), root)
            stem = rel[:-3]
            if f == 'README.md':
                stem = os.path.dirname(rel)
                dest = os.path.join(sec, stem, 'index.mdx')
                url = '/' + '/'.join(p for p in (sec, stem) if p)
            else:
                dest = os.path.join(sec, stem + '.mdx')
                url = '/%s/%s' % (sec, stem)
            pages[(sec, rel)] = {'dest': dest, 'url': url}


def copy_asset(sec, src_abs, subdir='assets'):
    key = (sec, src_abs)
    if key not in assets_used:
        dest = os.path.join(sec, subdir, slug(os.path.basename(src_abs)))
        os.makedirs(os.path.dirname(os.path.join(OUT, dest)), exist_ok=True)
        shutil.copyfile(src_abs, os.path.join(OUT, dest))
        if subdir == 'openapi':
            fix_spec(os.path.join(OUT, dest))
            dest = os.path.splitext(dest)[0] + '.json'
        assets_used[key] = dest
    return '/' + assets_used[key]


def fix_spec(path):
    """Patch spec defects GitBook tolerated but Mintlify's validator rejects. Writes JSON."""
    if path.endswith('.json'):
        d = json.load(open(path))
    else:
        d = json.loads(subprocess.run(['npx', '-y', 'js-yaml@4.1.0', path], capture_output=True, check=True, text=True).stdout)
        os.remove(path)

    def walk(o, key=None):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k.endswith('"'):  # icrc: `type": string`
                    o[k.rstrip('"')] = o.pop(k)
                    k = k.rstrip('"')
                if k == 'properties' and isinstance(v, dict):  # icrc: property misindented under its sibling
                    for p in list(v.values()):
                        if isinstance(p, dict) and isinstance(p.get('parameters'), dict) and 'type' in p['parameters']:
                            v['parameters'] = p.pop('parameters')
                if k in ('allOf', 'oneOf', 'anyOf') and isinstance(v, list):
                    o[k] = v = [x for x in v if x not in ({'required': False}, {'nullable': True})]
                if k == 'tags' and isinstance(v, str):
                    o[k] = [v]
                if k == 'type' and isinstance(v, str):
                    o[k] = v.strip(' ,')
                if k == 'required' and isinstance(v, str):
                    o[k] = [s.strip() for s in v.split(',')]
                walk(v, k)
            if 'in' in o and 'name' in o and 'schema' not in o and 'content' not in o:
                o['schema'] = {'type': 'string'}
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(d)
    json.dump(d, open(os.path.splitext(path)[0] + '.json', 'w'), indent=2)


def resolve(href, sec, src_rel):
    """Map a GitBook link target to a Mintlify URL. Returns None for broken references."""
    href = href.strip()
    if href.startswith('<') and href.endswith('>'):
        href = href[1:-1]
    m = re.match(r'https?://docs\.validationcloud\.io/(v1|staking|mavrik|agents)(/[^#?]*)?([#?].*)?$', href)
    if m:  # ponytail: GitBook site redirect /v1/xrpl -> /v1/xrp-ledger-xrpl, the only one linked internally
        path = (m.group(2) or '').rstrip('/').replace('/xrpl/', '/xrp-ledger-xrpl/', 1) if m.group(1) == 'v1' else (m.group(2) or '').rstrip('/')
        return '/' + m.group(1) + path + (m.group(3) or '')
    m = re.match(r'https://app\.gitbook\.com/o/[^/]+/s/F3uvE671dWWOTAu9svnI/(?:~/changes/\d+/)?([^#?]*)', href)
    if m:  # links into the GitBook editor; point at the same-named sibling page, else the same path
        name = m.group(1).rstrip('/').split('/')[-1].replace('copy-of-', '')
        for cand in (os.path.join(os.path.dirname(src_rel), name + '.md'), m.group(1).rstrip('/') + '.md'):
            if (sec, os.path.normpath(cand)) in pages:
                return pages[(sec, os.path.normpath(cand))]['url']
        report['unresolved'].append((sec, src_rel, href))
        return href
    if re.match(r'^(https?:|mailto:|#|/)', href):
        return href
    if 'broken-reference' in href:
        report['broken'].append((sec, src_rel))
        return None
    path, _, anchor = href.partition('#')
    path = re.sub(r'\\(.)', r'\1', unquote(path))
    target = os.path.normpath(os.path.join(os.path.dirname(src_rel), path))
    abs_target = os.path.join(EXPORT, sec, target)
    if '.gitbook/assets/' in target + '/' and os.path.isfile(abs_target):
        return copy_asset(sec, abs_target)
    for cand in (target, os.path.join(target, 'README.md')):
        if (sec, cand) in pages:
            return pages[(sec, cand)]['url'] + ('#' + anchor if anchor else '')
    report['unresolved'].append((sec, src_rel, href))
    return href


# ---------- SUMMARY -> navigation ----------
labels = {}  # (sec, rel) -> sidebar label
openapi_parents = {}  # (sec, rel) -> spec name from builtin:openapi blocks


def clean_inline(s):
    s = re.sub(r'<a [^>]*></a>', '', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\\(.)', r'\1', s).replace('**', '')
    return html.unescape(s).strip()


def parse_summary(sec):
    groups, cur = [], None
    stack = []  # (indent, node)
    lines = open(os.path.join(EXPORT, sec, 'SUMMARY.md')).read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        h = re.match(r'^##\s+(.*)', line)
        if h:
            cur = {'group': clean_inline(h.group(1)), 'pages': []}
            groups.append(cur)
            stack = []
        item = re.match(r'^(\s*)\* \[(.*?)\]\((.*?)\)\s*$', line)
        yml = re.match(r'^(\s*)\* ```yaml', line)
        if item or yml:
            if cur is None:
                cur = {'group': dict(SECTIONS)[sec], 'pages': []}
                groups.append(cur)
            indent = len((item or yml).group(1))
            while stack and stack[-1][0] >= indent:
                stack.pop()
            parent = stack[-1][1] if stack else None
            if yml:
                block = []
                i += 1
                while not lines[i].strip().startswith('```'):
                    block.append(lines[i])
                    i += 1
                spec = re.search(r'spec:[ \t]*(\S+)','\n'.join(block)).group(1)
                openapi_parents[parent['rel']] = spec
                parent['extra'] = write_org_spec(spec, pages[parent['rel']]['dest'])
            else:
                rel = os.path.normpath(unquote(item.group(3).split(' ')[0]))
                labels[(sec, rel)] = clean_inline(item.group(2))
                node = {'rel': (sec, rel), 'children': []}
                (parent['children'] if parent else cur['pages']).append(node)
                stack.append((indent, node))
        i += 1
    return groups


def write_org_spec(name, parent_dest):
    """Copy an org-level spec and write one MDX page per endpoint next to the parent page."""
    sec, src, dest_name, ops = ORG_SPECS[name]
    spec_rel = os.path.join(sec, 'openapi', dest_name)
    os.makedirs(os.path.join(OUT, sec, 'openapi'), exist_ok=True)
    if dest_name.endswith('.json'):
        d = json.load(open(src))
        d['servers'] = [{'url': ADMIN_SERVER}]
        json.dump(d, open(os.path.join(OUT, spec_rel), 'w'), indent=2)
    else:
        shutil.copyfile(src, os.path.join(OUT, spec_rel))
    refs = []
    for page_slug, title, method, path in ops:
        dest = os.path.join(os.path.dirname(parent_dest), page_slug + '.mdx')
        os.makedirs(os.path.dirname(os.path.join(OUT, dest)), exist_ok=True)
        open(os.path.join(OUT, dest), 'w').write('---\ntitle: %s\nopenapi: %s\n---\n' % (
            json.dumps(title), json.dumps('/%s %s %s' % (spec_rel, method, path))))
        refs.append(dest[:-4])
    return refs


def nav_entry(node, label):
    ref = pages[node['rel']]['dest'][:-4]
    kids = [nav_entry(c, labels[c['rel']]) for c in node['children']]
    kids += node.get('extra', [])
    if not kids:
        return ref
    return {'group': label, 'root': ref, 'pages': kids}


# ---------- page conversion ----------
def split_frontmatter(text):
    fm = {}
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    if not m:
        return fm, text
    lines = m.group(1).splitlines()
    for j, l in enumerate(lines):
        k = re.match(r'^(description|icon|cover):\s*(.*)$', l)
        if not k:
            continue
        val = k.group(2).strip()
        if val in ('>-', '>', '|', '|-'):
            buf = []
            for nl in lines[j + 1:]:
                if not nl.startswith(' '):
                    break
                buf.append(nl.strip())
            val = ' '.join(buf)
        fm[k.group(1)] = val.strip('"\'')
    return fm, text[m.end():]


def directives_pass(text, sec, ctx):
    """Line pass: GitBook {% %} directives -> MDX components; tracks fences."""
    out, stack, fence, code_meta = [], [], None, None
    raw = text.splitlines()
    lines = []
    for l in raw:  # put each directive on its own line (outside fences)
        f = FENCE.match(l)
        if fence is None and f:
            fence = f.group(2)
        elif fence and l.strip().startswith(fence[0] * len(fence)) and not l.strip().strip(fence[0]):
            fence = None
        elif fence is None and DIRECTIVE.search(l):
            parts = re.split(r'(\{%.*?%\})', l)
            lines += [p for p in parts if p.strip()]
            continue
        lines.append(l)
    fence = None
    skip = False
    for l in lines:
        f = FENCE.match(l)
        if fence is None and f and not skip:
            fence = f.group(2)
            if code_meta:
                l = f.group(1) + f.group(2) + (f.group(3).strip() or 'text') + ' ' + code_meta
                code_meta = None
            out.append(l)
            continue
        if fence:
            out.append(l)
            if l.strip().startswith(fence[0] * len(fence)) and not l.strip().strip(fence[0]):
                fence = None
            continue
        d = DIRECTIVE.fullmatch(l.strip())
        if not d:
            if not skip:
                out.append(l)
            continue
        name, a = d.group(1), attrs(d.group(2))
        if name in ('openapi', 'swagger'):
            ctx['openapi'] = a
            skip = True
        elif name in ('endopenapi', 'endswagger'):
            skip = False
        elif name == 'hint':
            tag = HINTS.get(a.get('style', 'info'), 'Info')
            stack.append(tag)
            out += ['', '<%s>' % tag, '']
        elif name == 'endhint':
            out += ['', '</%s>' % stack.pop(), '']
        elif name == 'tabs':
            out += ['', '<Tabs>']
        elif name == 'tab':
            out += ['<Tab title="%s">' % html.escape(a.get('title', ''), quote=True), '']
        elif name == 'endtab':
            out += ['', '</Tab>']
        elif name == 'endtabs':
            out += ['</Tabs>', '']
        elif name == 'code':
            meta = []
            if a.get('title'):
                meta.append('title="%s"' % a['title'])
            if a.get('lineNumbers') == 'true':
                meta.append('lines')
            if a.get('overflow') == 'wrap':
                meta.append('wrap')
            code_meta = ' '.join(meta) or None
        elif name == 'endcode':
            pass
        elif name == 'include':
            src = re.search(r'"([^"]+)"', d.group(2)).group(1)
            fname = os.path.basename(src)
            snip, comp = SNIPPET_NAMES.get(fname, (slug(fname)[:-3], 'Snippet'))
            ctx['imports'].add('import %s from "/snippets/%s.mdx";' % (comp, snip))
            ctx['snippets'].add((sec, os.path.normpath(os.path.join(os.path.dirname(ctx['rel']), src)), snip))
            out += ['', '<%s />' % comp, '']
        else:
            report['unresolved'].append((sec, ctx['rel'], 'directive:' + name))
    return '\n'.join(out)


def code_group(m):
    """Tabs whose every tab is a single code block -> CodeGroup with tab titles as code titles."""
    tabs = re.findall(r'<Tab title="([^"]*)">\n(.*?)\n</Tab>', m.group(1), re.S)
    blocks = []
    for title, body in tabs:
        b = re.fullmatch(r'\s*(`{3,})([^\n]*)\n(.*?\n)?\1\s*', body, re.S)
        if not b or '<Tab' in body:
            return m.group(0)
        info = b.group(2).strip().split(' ', 1)
        lang, meta = (info[0] or 'text'), (info[1] if len(info) > 1 else '')
        meta = re.sub(r'title="[^"]*"\s*', '', meta)
        head = ' '.join(x for x in (lang, 'title="%s"' % title, meta.strip()) if x)
        blocks.append('%s%s\n%s%s' % (b.group(1), head, (b.group(3) or '').rstrip('\n') + '\n', b.group(1)))
    if len(blocks) != len(re.findall(r'<Tab title=', m.group(1))):
        return m.group(0)
    return '<CodeGroup>\n\n' + '\n\n'.join(blocks) + '\n\n</CodeGroup>'


def segments(text):
    """Yield (is_code, chunk) splitting on fenced code blocks."""
    buf, fence, code = [], None, False
    for l in text.split('\n'):
        f = FENCE.match(l)
        if fence is None and f:
            if buf:
                yield False, '\n'.join(buf)
            buf, fence = [l], f.group(2)
            continue
        buf.append(l)
        if fence and l.strip().startswith(fence[0] * len(fence)) and not l.strip().strip(fence[0]):
            yield True, '\n'.join(buf)
            buf, fence = [], None
    if buf:
        yield fence is not None, '\n'.join(buf)


def on_prose(text, fn):
    return '\n'.join(c if code else fn(c) for code, c in segments(text))


def pre_to_fence(t):
    def rep(m):
        lang = re.search(r'lang(?:uage)?-([\w+-]+)', m.group(1) + m.group(2))
        body = html.unescape(re.sub(r'<[^>]+>', '', m.group(3))).rstrip('\n')
        return '\n```%s\n%s\n```\n' % (lang.group(1) if lang else 'text', body)
    t = re.sub(r'<pre([^>]*)><code([^>]*)>(.*?)</code></pre>', rep, t, flags=re.S)
    # inline <code> -> backticks (contents often hold JSON braces)
    def inline(m):
        body = html.unescape(re.sub(r'<[^>]+>', '', m.group(1)))
        tick = '``' if '`' in body else '`'
        return '%s%s%s' % (tick, body, tick)
    return re.sub(r'<code>(.*?)</code>', inline, t, flags=re.S)


def style_obj(s):
    pairs = []
    for decl in s.split(';'):
        if ':' in decl:
            k, v = decl.split(':', 1)
            k = re.sub(r'-(\w)', lambda m: m.group(1).upper(), k.strip())
            pairs.append('%s: %s' % (k, json.dumps(v.strip())))
    return '{{' + ', '.join(pairs) + '}}'


def rewrite_links(t, sec, rel):
    def md(m):
        bang, label, target = m.group(1), m.group(2), m.group(3) or m.group(4)
        new = resolve(target, sec, rel)
        if new is None:
            return label
        if re.fullmatch(r'[\w\\.-]+\.md', label):  # GitBook page mention: label is the file name
            tgt = os.path.normpath(os.path.join(os.path.dirname(rel), re.sub(r'\\(.)', r'\1', unquote(target.split('#')[0]))))
            label = labels.get((sec, tgt), label)
        return '%s[%s](%s)' % (bang, label, new.replace(' ', '%20'))
    t = re.sub(r'(!?)\[((?:[^\[\]]|\[[^\]]*\])*)\]\((?:<([^>]+)>|([^)\s]+))(?:\s+"[^"]*")?\)', md, t)

    def attr(m):
        new = resolve(html.unescape(m.group(3)), sec, rel)
        return '%s%s="%s"' % (m.group(1), m.group(2), (new or '#').replace(' ', '%20'))
    return re.sub(r'(<(?:a|img)\b[^>]*?\s)(href|src)="([^"]*)"', attr, t)


def html_pass(t):
    t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
    t = re.sub(r'<a href="#[^"]*" id="[^"]*"></a>', '', t)

    def acc(m):
        title = clean_inline(m.group(1)).replace('"', '&quot;')
        return '<Accordion title="%s">' % title
    t = re.sub(r'<details>\s*<summary>(.*?)</summary>', acc, t, flags=re.S)
    t = t.replace('</details>', '</Accordion>')

    def fig(m):
        img = m.group(1)
        src = re.search(r'src="([^"]*)"', img)
        alt = re.search(r'alt="([^"]*)"', img)
        cap = clean_inline(m.group(2) or '')
        md = '![%s](%s)' % ((alt.group(1) if alt else ''), src.group(1) if src else '')
        if cap:
            return '<Frame caption="%s">\n  %s\n</Frame>' % (cap.replace('"', '&quot;'), md)
        return md
    t = re.sub(r'<figure>\s*(<img[^>]*>)\s*(?:<figcaption>(.*?)</figcaption>)?\s*</figure>', fig, t, flags=re.S)
    # GitBook uses <mark style="color:..."> for coloured text, not highlights
    t = re.sub(r'<mark\b([^>]*)>', r'<span\1>', t).replace('</mark>', '</span>')
    t = re.sub(r'(<\w+[^>]*?)\sstyle="([^"]*)"', lambda m: '%s style=%s' % (m.group(1), style_obj(m.group(2))), t)
    t = re.sub(r'(<\w+[^>]*?)\sclass="', r'\1 className="', t)
    t = re.sub(r'<(br|img|col|hr)\b([^>]*?)\s*/?>', r'<\1\2 />', t)
    return t


def escape_text(t):
    """Escape MDX-special characters in prose, leaving known tags and inline code alone."""
    out = []
    for part in re.split(r'(`+[^`\n]*?`+)', t):
        if part.startswith('`'):
            out.append(part)
            continue
        pos = 0
        for m in KNOWN_TAG.finditer(part):
            out.append(_esc(part[pos:m.start()]))
            out.append(m.group(0))
            pos = m.end()
        out.append(_esc(part[pos:]))
    return ''.join(out)


def _esc(s):
    s = re.sub(r'(?<!\\)([{}])', r'\\\1', s)
    return s.replace('\\<', '<').replace('<', '&lt;')


def convert_page(sec, rel):
    src = os.path.join(EXPORT, sec, rel)
    fm, body = split_frontmatter(open(src).read())
    title = None
    h1 = re.match(r'\s*#\s+(.+?)\s*\n', body)
    if h1:
        title = clean_inline(h1.group(1))
        body = body[h1.end():]
    label = labels.get((sec, rel))
    title = title or label or os.path.basename(os.path.dirname(rel) or sec)
    ctx = {'openapi': None, 'imports': set(), 'snippets': set(), 'rel': rel}
    body = directives_pass(body, sec, ctx)
    body = on_prose(body, pre_to_fence)
    body = re.sub(r'<Tabs>\n(.*?)\n</Tabs>', code_group, body, flags=re.S)
    body = on_prose(body, lambda t: rewrite_links(t, sec, rel))
    body = on_prose(body, html_pass)
    body = on_prose(body, escape_text)
    body = re.sub(r'\n{3,}', '\n\n', body).strip() + '\n'

    head = ['---', 'title: %s' % json.dumps(title)]
    if label and label != title:
        head.append('sidebarTitle: %s' % json.dumps(label))
    if fm.get('description'):
        head.append('description: %s' % json.dumps(fm['description']))
    if fm.get('icon'):
        head.append('icon: %s' % json.dumps(fm['icon']))
    if ctx['openapi']:
        a = ctx['openapi']
        spec_abs = os.path.normpath(os.path.join(EXPORT, sec, os.path.dirname(rel), a['src']))
        spec = copy_asset(sec, spec_abs, 'openapi')
        head.append('openapi: %s' % json.dumps('%s %s %s' % (spec, a['method'].upper(), a['path'])))
        report['openapi'].append((spec, a['method'].upper(), a['path'], pages[(sec, rel)]['dest']))
    head.append('---')
    if fm.get('cover'):  # GitBook page cover -> full-width banner, styled by .page-cover in style.css
        cover_abs = os.path.normpath(os.path.join(EXPORT, sec, os.path.dirname(rel), fm['cover']))
        body = '<img className="page-cover" src="%s" alt="" noZoom />\n\n%s' % (copy_asset(sec, cover_abs), body)
    imports = '\n'.join(sorted(ctx['imports']))
    out = '\n'.join(head) + '\n\n' + (imports + '\n\n' if imports else '') + body
    dest = os.path.join(OUT, pages[(sec, rel)]['dest'])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, 'w').write(out)
    return ctx['snippets']


def write_snippet(sec, src_rel, name):
    _, body = split_frontmatter(open(os.path.join(EXPORT, sec, src_rel)).read())
    body = on_prose(body, escape_text)
    os.makedirs(os.path.join(OUT, 'snippets'), exist_ok=True)
    open(os.path.join(OUT, 'snippets', name + '.mdx'), 'w').write(body.strip() + '\n')


tabs = []
for sec, tab in SECTIONS:
    groups = parse_summary(sec)
    snippets = set()
    for (s, rel) in [k for k in pages if k[0] == sec]:
        snippets |= convert_page(s, rel)
    for s, src_rel, name in snippets:
        write_snippet(s, src_rel, name)
    out_groups = []
    for g in groups:
        out_groups.append({'group': g['group'], 'pages': [nav_entry(n, labels[n['rel']]) for n in g['pages']]})
    tabs.append({'tab': tab, 'groups': out_groups})

base = json.load(open(sys.argv[3]))
base['navigation'] = {'tabs': tabs}
json.dump(base, open(os.path.join(OUT, 'docs.json'), 'w'), indent=2)
open(os.path.join(OUT, 'docs.json'), 'a').write('\n')
print('pages:', len(pages), 'assets:', len(assets_used))
print('openapi pages:', len(report['openapi']))
print('broken-reference links:', len(report['broken']), sorted(set(report['broken']))[:20])
print('unresolved:', len(report['unresolved']))
for u in report['unresolved'][:60]:
    print('  ', u)
