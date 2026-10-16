"""Check every Node API chain overview against the template in templates/chain-overview.mdx.

Each nodeapi/<folder>/overview.mdx must have the chain logo marker, a cover, the TryFree banner, and these
## sections in order: Network Support, optional chain-specific sections, Getting Started (with a curl example),
Compute Units last. Run from the repo root: python3 scripts/check-chain-overviews.py
"""
import glob
import re
import sys

problems = []
for path in sorted(glob.glob('nodeapi/*/overview.mdx')):
    folder = path.split('/')[1]
    text = open(path).read()
    fail = lambda msg: problems.append('%s: %s' % (path, msg))

    if '<span className="chain-logo-%s" />' % folder not in text:
        fail('missing <span className="chain-logo-%s" /> logo marker' % folder)
    if 'className="page-cover"' not in text:
        fail('missing page cover image')
    if '<TryFree ' not in text:
        fail('missing <TryFree /> banner')

    body = re.sub(r'(?ms)^```.*?^```', '', text)  # ignore headings inside code blocks
    h2 = [h.strip() for h in re.findall(r'^## (.+)$', body, re.M)]
    if not h2 or h2[0] != 'Network Support':
        fail('first ## section must be "Network Support" (found %s)' % (h2[:1] or 'none'))
    if not h2 or h2[-1] != 'Compute Units':
        fail('last ## section must be "Compute Units" (found %s)' % (h2[-1:] or 'none'))
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

if problems:
    print('\n'.join(problems))
    sys.exit('%d chain overview problem(s); see templates/chain-overview.mdx' % len(problems))
print('chain overviews OK')
