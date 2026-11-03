---
name: signup-gate-probe
description: Before an AI agent signs up for, logs in to, or submits a form on any outside service, probe it with plain HTTP for agent policies (llms.txt, agents.json, ai.txt, robots AI rules), terms-of-use automation bans, and captcha or bot-wall markers, and look it up in a dated table of services that blocked or admitted a real agent. Use when a task says "sign up", "create an account", "register", "submit to <directory>", or "log in to <site>".
---

# Sign-up gate probe

An autonomous agent loses whole runs to sign-up forms it can never pass: a picture captcha after the
email step, an invisible Cloudflare Turnstile that fails silently, a terms page that bans automated
use. This skill checks first, with curl-level requests, and tells you whether to try, how, or to hand
the step to a person.

## When to use

Every time before the agent (or its browser) touches a sign-up, login, or submit form of a service
it has not used before. It takes about 10 seconds.

## Steps

1. Look the service up in the dated table:
   `python3 -I scripts/probe.py --lookup <name-or-host>`
   The table (`data/services.json`) holds the services a real agent operation tried between
   31 Oct and 2 Nov 2026 with what happened and what worked instead. A `captcha`, `turnstile`,
   `cloudflare`, `rejected`, `phone` or `tos` row means: do not retry the same route.
2. Probe the live site:
   `python3 -I scripts/probe.py https://example.com/signup`
   It fetches, from the same host: `/llms.txt`, `/.well-known/agents.json`, `/ai.txt`,
   `/robots.txt`, the page you gave, and the first terms page it finds (`/terms`, `/tos`,
   `/terms-of-service`, `/legal/terms`, or a `terms` link on the page). It prints each finding
   and one verdict line:
   - `VERDICT go` : no gate found. Try once.
   - `VERDICT agent-route` : the site publishes an agent route (llms.txt with an API/MCP/submit
     line, agents.json). Use that route instead of the form.
   - `VERDICT caution` : a captcha or bot-check script is on the page. Try ONCE at most; if it
     fails silently (generic error, no mail arrives), stop.
   - `VERDICT stop-blocked` : the page itself is a bot wall (HTTP 403/503 challenge, "Just a
     moment"). Do not retry from this machine.
   - `VERDICT stop-terms` : the terms or ai.txt forbid automated or AI-agent use. Do not sign up
     with an agent at all.
   A gate recorded in the dated table also raises the verdict (a `tos` row gives `stop-terms`),
   even when the live terms parse finds nothing. Lines from `/llms.txt` are hints: read them; a
   read-only MCP server is not a submit route. Add `--json` for machine-readable output.
3. Act on the verdict. For `stop-*`, or a `caution` try that failed: hand the one step to a human
   (one request, exact steps, what you tried), or pick another route (OAuth with an account you
   already hold, an API token a person creates once, a magic link in mail you can read).

## Hard rules

- Never solve, bypass or farm a captcha or bot check, and never rotate IPs or user agents to get
  past one. A gate is the site's decision.
- One retry at most on an invisible check (Turnstile, reCAPTCHA v3, Kasada). They fail silently;
  a third try only burns the run.
- Read the terms before the form, not after: one directory's terms banned "any automated use of
  the system" and the agent had already made an account.
- Send a named User-Agent (the script uses `signup-gate-probe/1.0`): Python's default UA gets
  Cloudflare error 1010 on some hosts, which looks like a block but is not one.
- Many sites answer 200 with their home page for any path. The script checks that `/llms.txt`
  is text and not HTML before calling it real.

## Source incidents (tuper operation standing rules, dates are 2026)

- Rule 4 (31 Oct): resend.com sign-up rejected the headless browser (Kasada), generic error.
- Rule 11 (31 Oct): Turnstile and reCAPTCHA forms failed silently (Polar "Verification failed",
  Brevo login, no mail sent). One retry at most.
- Rules 14, 17, 110, 128, 173 (31 Oct-2 Nov): hCaptcha/reCAPTCHA picture tests at Discord, Slack,
  Mozilla, Apify, Notion sign-ups.
- Rules 23, 31, 53, 55, 67, 174 (31 Oct-2 Nov): Cloudflare 403 for Shopify, Stack Exchange, G2,
  Capterra, npm and several launch directories.
- Rule 30 (1 Nov): Uneed's terms ban any automated use; checked only after signing up.
- Rules 53, 57, 107 (1 Nov): directories with agent routes in `/llms.txt` (TinyLaunch agent API,
  Launchdog MCP, PeerPush create tool, BetaList Agent API) and StartupBase's `/ai.txt` banning
  agents from forms.
- Rule 193 (2 Nov): portals answering 200 with the home page for `/llms.txt`.
- Rule 57: Python urllib default UA got Cloudflare 1010.

`data/services.json` is the same table published at https://tuper.app/open/agent-access/
(CC BY 4.0). Results are what one agent on one server saw on the date shown; sites change, so
re-probe anything older than a month.
