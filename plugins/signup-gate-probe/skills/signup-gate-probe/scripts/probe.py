#!/usr/bin/env python3
"""signup-gate-probe: check a site for agent policies, terms bans and bot walls before signing up.

  python3 -I probe.py https://example.com/signup [--json]
  python3 -I probe.py --lookup <name-or-host>       search data/services.json

Stdlib only. Plain GET requests with a named User-Agent; it never submits a form or solves anything.
"""
import json, os, re, ssl, sys, urllib.error, urllib.parse, urllib.request

UA = 'signup-gate-probe/1.0 (+agent pre-signup check)'
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, '..', 'data', 'services.json')
BAD = {'captcha', 'turnstile', 'cloudflare', 'phone', 'google', 'rejected', 'tos'}

MARKERS = [  # (label, regex, kind) kind: wall = page itself is a challenge; check = captcha script present
    ('Cloudflare challenge page', r'<title>\s*Just a moment\.\.\.|cf-chl-(bypass|widget|opt)|Attention Required! \| Cloudflare', 'wall'),
    ('generic bot wall', r"Client Challenge|Verifying your connection|Looks like you'?re a bot|Press (&amp;|&) Hold|px-captcha", 'wall'),
    ('Cloudflare Turnstile', r'challenges\.cloudflare\.com/turnstile|cf-turnstile', 'check'),
    ('hCaptcha', r'hcaptcha\.com|h-captcha', 'check'),
    ('reCAPTCHA', r'google\.com/recaptcha|gstatic\.com/recaptcha|g-recaptcha|recaptcha/api\.js', 'check'),
    ('Kasada', r'/ips\.js|x-kpsdk|kasada', 'check'),
    ('DataDome', r'datadome', 'check'),
    ('PerimeterX / HUMAN', r'perimeterx|_pxAppId|human-challenge', 'check'),
    ('Arkose / FunCaptcha', r'arkoselabs|funcaptcha', 'check'),
    ('AWS WAF captcha', r'awswaf|captcha\.awswaf', 'check'),
]
TERMS_BAN = re.compile(r'[^.\n]{0,120}\b(automated (means|use|access|system|scripts?)|bots?\b|robots?\b|scrap(e|ing)|crawl(er|ing)|'
                       r'non-human|artificial intelligence|AI agents?|headless)[^.\n]{0,120}', re.I)
NEG = re.compile(r'\b(not|no|never|prohibit(ed|s)?|forbid(den|s)?|ban(s|ned)?|may not|must not|shall not|without our|without prior|restrict(ed|s)?)\b', re.I)


def get(url, limit=400_000):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': '*/*'})
    try:
        with urllib.request.urlopen(req, timeout=20, context=ssl.create_default_context()) as r:
            return r.status, r.headers.get('content-type', ''), r.read(limit).decode('utf-8', 'replace'), r.geturl()
    except urllib.error.HTTPError as e:
        try:
            body = e.read(limit).decode('utf-8', 'replace')
        except Exception:
            body = ''
        return e.code, e.headers.get('content-type', '') if e.headers else '', body, url
    except Exception as e:
        return 0, '', str(e), url


def is_text_file(ct, body):
    return 'html' not in ct.lower() and not re.match(r'\s*(<!doctype|<html)', body, re.I) and body.strip() != ''


def lookup(q):
    rows = json.load(open(DATA))['services']
    q = q.lower().replace('https://', '').replace('http://', '').split('/')[0]
    q = re.sub(r'^www\.', '', q)
    key = q.split('.')[0] if '.' in q else q
    hits = [r for r in rows if key in r['service'].lower() or key in r.get('what_we_tried', '').lower()]
    return hits


def probe(url):
    u = urllib.parse.urlparse(url if '://' in url else 'https://' + url)
    base = '%s://%s' % (u.scheme, u.netloc)
    out = {'url': url, 'host': u.netloc, 'findings': [], 'verdict': 'go'}
    f = out['findings']
    level = {'go': 0, 'agent-route': 1, 'caution': 2, 'stop-blocked': 3, 'stop-terms': 4}

    def raise_to(v):
        if level[v] > level[out['verdict']]:
            out['verdict'] = v

    # 1. agent policy files
    for path in ('/llms.txt', '/.well-known/agents.json', '/ai.txt'):
        st, ct, body, _ = get(base + path, 60_000)
        if st == 200 and is_text_file(ct, body):
            line = {'check': path, 'status': st, 'bytes': len(body)}
            if path == '/ai.txt' and re.search(r'(disallow|not allowed|forbid|prohibit)[^\n]*(agent|form|account|submit)|'
                                                r'(agent|form|account|submit)[^\n]*(disallow|not allowed|forbid|prohibit)', body, re.I):
                line['note'] = 'ai.txt restricts agents: ' + re.search(r'[^\n]*(disallow|not allowed|forbid|prohibit)[^\n]*', body, re.I).group(0)[:200]
                raise_to('stop-terms')
            hits = [l.strip() for l in body.splitlines() if re.search(r'\b(mcp|api|submit|agent|create|sign ?up|register)\b', l, re.I)][:6]
            if hits and path != '/ai.txt':
                line['agent_lines'] = hits
                raise_to('agent-route')
            if path == '/.well-known/agents.json':
                raise_to('agent-route')
            f.append(line)
        else:
            f.append({'check': path, 'status': st, 'note': 'absent' if st in (404, 410) else
                      ('HTML instead of a text file (catch-all route)' if st == 200 else 'not readable')})
    # 2. robots.txt AI-agent rules
    st, ct, body, _ = get(base + '/robots.txt', 60_000)
    if st == 200 and is_text_file(ct, body):
        ai = re.findall(r'(?im)^user-agent:\s*(GPTBot|ChatGPT-User|ClaudeBot|Claude-User|anthropic-ai|PerplexityBot|Google-Extended|CCBot|OAI-SearchBot)\s*$', body)
        f.append({'check': '/robots.txt', 'status': st, 'ai_user_agents_named': sorted(set(ai))})
    # 3. the page itself
    st, ct, body, final = get(url if '://' in url else 'https://' + url)
    page = {'check': 'page', 'status': st, 'final_url': final, 'markers': []}
    for label, rx, kind in MARKERS:
        if re.search(rx, body, re.I):
            page['markers'].append(label)
            raise_to('stop-blocked' if kind == 'wall' else 'caution')
    if st in (403, 429, 503) and not page['markers']:
        page['markers'].append('HTTP %d to a plain request' % st)
        raise_to('stop-blocked' if st == 403 else 'caution')
    if st == 0:
        page['note'] = body[:200]
    f.append(page)
    # 4. terms of use
    terms_urls = []
    m = re.findall(r'href="([^"]*(?:terms|tos|legal|conditions)[^"]*)"', body, re.I)
    for h in m[:3]:
        terms_urls.append(urllib.parse.urljoin(final or base, h))
    terms_urls += [base + p for p in ('/terms', '/tos', '/terms-of-service', '/legal/terms', '/terms-of-use')]
    seen = set()
    for tu in terms_urls:
        if tu in seen:
            continue
        seen.add(tu)
        st, ct, tb, tfinal = get(tu)
        if st == 200 and len(tb) > 2000 and re.search(r'terms|conditions|agreement', tb, re.I):
            text = re.sub(r'<script.*?</script>|<style.*?</style>', ' ', tb, flags=re.S | re.I)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            clauses = [c.group(0).strip() for c in TERMS_BAN.finditer(text) if NEG.search(c.group(0))][:5]
            f.append({'check': 'terms', 'url': tfinal, 'automation_clauses': clauses})
            if any(re.search(r'automated (means|use|access|system)|non-human|AI agents?|bots?\b', c, re.I) for c in clauses):
                raise_to('caution')
                f[-1]['note'] = 'Read these clauses yourself: if they ban automated use of the service (not just scraping), treat as stop-terms.'
            break
    else:
        f.append({'check': 'terms', 'note': 'no terms page found at common paths; read it in the browser before signing up'})
    out['table'] = [{'service': r['service'], 'result': r['result'], 'date': r['date_tested'], 'note': r['what_worked_instead']}
                    for r in lookup(u.netloc)]
    known = [r['result_key'] for r in lookup(u.netloc)]
    if any(k in BAD for k in known):
        out['table_says'] = 'a known gate is recorded for this service: read the table rows before trying'
        raise_to('stop-terms' if 'tos' in known else 'caution')
    return out


def show(o):
    print('probe', o['url'])
    for x in o['findings']:
        print(' -', json.dumps(x, ensure_ascii=False)[:600])
    for r in o.get('table', []):
        print(' - table: %(service)s | %(result)s | %(date)s | %(note)s' % r)
    if o.get('table_says'):
        print(' -', o['table_says'])
    print('VERDICT', o['verdict'])


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]
    if '--lookup' in sys.argv:
        hits = lookup(a[0]) if a else []
        for r in hits:
            print('%s | %s | %s | tried: %s | %s | rules %s' % (r['service'], r['result'], r['date_tested'], r['what_we_tried'],
                                                              r['what_worked_instead'], r['rules']))
        print('%d row(s)' % len(hits))
        sys.exit(0)
    if not a:
        sys.exit(__doc__)
    o = probe(a[0])
    print(json.dumps(o, indent=1, ensure_ascii=False)) if '--json' in sys.argv else show(o)
