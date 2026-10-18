# Deploying SafeZone

One Fly app serves both halves: FastAPI mounts the built React bundle from
`Backend/static`, so the browser talks to a single origin. That is not a
shortcut — the control-room session is an `HttpOnly; SameSite=Lax` cookie, and
a frontend on `vercel.app` calling an API on `fly.dev` is cross-site, so the
browser would withhold that cookie and every protected route would answer 401.
Same origin means no CORS, no weakened cookie attributes, and nothing to
configure.

Budget 30–40 minutes the first time. **Do not do this in the hour before a
demo** — keep ngrok running until Fly is proven.

---

## 0. Before you start

Find your Supabase region: **dashboard → Project Settings → General → Region**.
Put the matching Fly region in `fly.toml` as `primary_region` (the mapping is
in the comments there).

This is the one setting that matters for speed. Every query is a round trip;
from a laptop in Karachi that is ~400ms, which is why `/api/cases` took almost
two seconds in development. Co-located with the database it is ~15ms, and the
control room loads in well under a second. **Deployment is the performance
fix** — nothing in the code was ever the problem.

---

## 1. Install and sign in

```bash
# Windows PowerShell
pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"

fly auth login
```

## 2. Create the app

From the repository root, where `fly.toml` and `Dockerfile` live:

```bash
fly apps create safezone
```

If the name is taken, pick another and change `app =` in `fly.toml` to match.

## 3. Set the secrets

**Never commit these.** `fly secrets` stores them encrypted and injects them as
environment variables at runtime; they are not baked into the image.

```bash
fly secrets set \
  SUPABASE_URL="https://xxxx.supabase.co" \
  SUPABASE_SERVICE_KEY="..." \
  WHATSAPP_TOKEN="..." \
  WHATSAPP_PHONE_ID="..." \
  WHATSAPP_VERIFY_TOKEN="..." \
  WHATSAPP_APP_SECRET="..." \
  WHATSAPP_PUBLIC_NUMBER="92..." \
  ADMIN_EMAILS="a@safezone.net,b@safezone.net" \
  ADMIN_PASSWORD_HASH="pbkdf2_sha256\$..." \
  SESSION_SECRET="..." \
  COORDINATOR_NUMBERS="92..." \
  DEMO_VOLUNTEERS='[{"name":"Volunteer A","phone":"92...","zones":[...]}]' \
  DEMO_ALLOWLIST="92...,92..." \
  EMERGENCY_FIRE="..." \
  EMERGENCY_AMBULANCE="..." \
  EMERGENCY_NGO="..." \
  GEMINI_API_KEY="..." \
  DEEPSEEK_API_KEY="..."
```

The website assistant has no key of its own: `POST /api/chat` goes through the
same `LLM_PROVIDERS` chain as extraction. There is deliberately no `VITE_`
model key either -- a `VITE_` variable is compiled into the bundle and served
to every visitor.

In **bash**, `$` inside the password hash must be escaped (`\$`) or the shell
eats it. In **PowerShell**, use single quotes around that value instead.

Then the non-secret settings:

```bash
fly secrets set \
  MOCK_MODE=0 \
  DEMO_MODE=1 \
  ALLOWLIST_ONLY=1 \
  KILL_SWITCH=0 \
  SHOW_SIMULATION_LABELS=1 \
  VOLUNTEER_MAX_CASES=10 \
  LLM_PROVIDERS="deepseek,groq,gemini"
```

`SHOW_SIMULATION_LABELS=1` matters more in production than it did locally.
Deployed, the number is reachable by anyone — and the configured emergency
numbers are a team redirect, not Rescue 1122. Without the label, a stranger in
a real emergency is told to call a number that will not answer.

`ALLOWLIST_ONLY=1` is the belt to that braces: only numbers you list get
replies at all.

## 4. Deploy

```bash
fly deploy
```

First build takes a few minutes — Node installs, the SPA builds, Python
installs. Later deploys are faster.

```bash
fly logs            # watch startup; it prints every configuration problem
fly status
```

Read those startup warnings. They are the list of settings that silently break
a demo, and they are the fastest check that the secrets landed.

## 5. Point the app at itself

```bash
fly secrets set PUBLIC_BASE_URL="https://safezone.fly.dev"
```

The **origin**, with no path. This is what builds the `/r/<token>` handoff
links sent to Rescue 1122 — paste a webhook URL here and responders get a 404
in the rain. `config.py` strips an accidental `/webhook/whatsapp` suffix, but
do not rely on that.

## 6. Check it before touching Meta

Everything except the WhatsApp path works now, while ngrok is still live:

```bash
curl -s https://safezone.fly.dev/api/whatsapp
curl -s -o /dev/null -w "%{time_total}s\n" https://safezone.fly.dev/api/zones
```

That second number is the one to care about. Under 100ms means the region is
right. Still near half a second means the app and the database are on different
continents — fix `primary_region` and redeploy.

Then in a browser: the landing page, `/login`, `/control`, `/live`,
`/volunteers`. The control room should feel instant.

## 7. Move the Meta webhook

Only now, and only once step 6 passes.

**Meta → WhatsApp → Configuration → Webhook → Edit**

- Callback URL: `https://safezone.fly.dev/webhook/whatsapp`
- Verify token: whatever `WHATSAPP_VERIFY_TOKEN` is set to
- Subscribe to the **messages** field

Meta sends a GET to verify. If it fails, the token does not match — check
`fly secrets list` (names only; values are write-only).

**Rollback is one edit.** Point the callback URL back at the ngrok domain and
you are exactly where you were. Keep the ngrok tunnel running until you have
sent a real message through Fly and watched it land in the queue.

## 8. End to end

Message the SafeZone number from a phone. You should get the automatic reply,
and the case should appear in `/control`. Then approve, `ACCEPT`, `ARRIVED`,
`DONE`, `1`.

If nothing arrives:

```bash
fly logs
```

- No request at all → Meta is still pointed at ngrok, or the webhook
  subscription did not save
- Request arrives, nothing sends → check `ALLOWLIST_ONLY` and `DEMO_ALLOWLIST`
- `window_closed` in the logs → that handset has not messaged in 24 hours; send
  `ON DUTY` from it

---

## Afterwards

- `fly secrets set SESSION_SECRET="$(new value)"` signs everyone out. That is
  how you revoke a session before it expires.
- `fly scale count 1` is enough. More machines would each hold their own
  in-process SSE subscriber set, so an event emitted on one would not reach a
  dashboard connected to another. Fixing that properly means a shared bus; one
  machine avoids the problem.
- `fly deploy` on every push is the rhythm. The build is reproducible: nothing
  from your laptop is in the image.

## Known limits of this setup

- **One machine, in-memory SSE fan-out.** Scaling horizontally would need a
  Redis or Postgres channel between instances.
- **No offline mode.** The app needs Supabase to do anything, which is a real
  gap for a disaster tool and is named in the README.
- **Secrets live in Fly only.** There is no secret manager and no rotation
  schedule; `fly secrets set` is the whole story.
