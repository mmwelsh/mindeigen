#!/usr/bin/env python3
"""
MindEigen waitlist endpoint
POST /waitlist  { "email": "user@example.com" }
Stores to waitlist.json + sends admin notification + welcome email to user
"""
import json, os, re, sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from pathlib import Path

# Load env
env_path = Path("/home/mike/.openclaw/.env")
for line in env_path.read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
NOTIFY_EMAIL     = "mmwelsh@gmail.com"
FROM_EMAIL       = "hello@mindeigen.com"
FROM_NAME        = "MindEigen"
WAITLIST_FILE    = Path(__file__).parent / "waitlist.json"
PORT             = 5001

WELCOME_HTML = """\
<!DOCTYPE html>
<html><head><meta charset="UTF-8"/>
<style>
  body{background:#07080f;color:#e8eaf2;font-family:'Helvetica Neue',Arial,sans-serif;margin:0;padding:0}
  .wrap{max-width:560px;margin:0 auto;padding:40px 32px}
  .logo{font-family:monospace;font-size:1.2rem;color:#5b8dee;margin-bottom:32px;letter-spacing:-0.02em}
  .logo span{color:#e8eaf2}
  h1{font-size:1.6rem;font-weight:700;margin-bottom:12px;letter-spacing:-0.03em}
  h1 em{font-style:normal;color:#5b8dee}
  p{color:#9ca3af;line-height:1.7;margin-bottom:16px;font-size:.95rem}
  .eq{font-family:monospace;color:#e0b84a;font-size:1rem;padding:16px 20px;
      background:#0e1018;border-left:3px solid #5b8dee;border-radius:4px;margin:24px 0}
  .section{border-top:1px solid #1e2235;padding-top:24px;margin-top:24px}
  .section h3{font-size:1rem;font-weight:600;margin-bottom:8px;color:#e8eaf2}
  ul{color:#9ca3af;font-size:.9rem;line-height:1.8;padding-left:20px}
  .tag{display:inline-block;font-family:monospace;font-size:.72rem;color:#a78bfa;
       background:rgba(167,139,250,.12);padding:2px 8px;border-radius:4px;margin-top:4px}
  .footer{margin-top:40px;padding-top:20px;border-top:1px solid #1e2235;
          font-size:.78rem;color:#6b7280;text-align:center}
  a{color:#5b8dee;text-decoration:none}
</style></head>
<body><div class="wrap">
  <div class="logo">mind<span>eigen</span></div>
  <h1>You're on the list.<br/>Your <em>eigenvalue</em> awaits.</h1>
  <p>We received your request for early access to MindEigen. You're among a small group of early adopters
  who will be the first to deploy a personal AI agent that thinks, evolves, and heals — on your behalf.</p>
  <div class="eq">A·mind = λ·mind &nbsp;→&nbsp; find λ, amplify it. ∞</div>

  <div class="section" style="background:rgba(167,139,250,.06);border:1px dashed #a78bfa;border-radius:10px;padding:20px 24px;text-align:center;margin:24px 0">
    <div style="font-size:.75rem;letter-spacing:1.5px;text-transform:uppercase;color:#a78bfa;margin-bottom:8px">Your early-adopter code</div>
    <div style="font-family:monospace;font-size:28px;font-weight:700;color:#e8eaf2;letter-spacing:3px">EIGEN50</div>
    <div style="font-size:.8rem;color:#6b7280;margin-top:6px">50% off at launch · no expiry</div>
  </div>

  <div class="section">
    <h3>What happens next</h3>
    <ul>
      <li>We're onboarding early users in small cohorts</li>
      <li>You'll receive a personal invite with setup instructions</li>
      <li>Your agent will be provisioned and ready to deploy</li>
      <li>Early adopters get priority access + 50% off with code EIGEN50</li>
    </ul>
  </div>

  <div class="section">
    <h3>What you're getting</h3>
    <p>MindEigen deploys a cloud-based AI agent that operates on your behalf — continuously learning,
    self-improving, and recovering from errors without human intervention. When your agent discovers
    a better capability, it contributes it back to the network. Everyone benefits.</p>
    <span class="tag">// self-monitoring</span>&nbsp;
    <span class="tag">// self-healing</span>&nbsp;
    <span class="tag">// recursive improvement</span>&nbsp;
    <span class="tag">// community intelligence</span>
  </div>

  <div class="section">
    <h3>What makes a great MindEigen user</h3>
    <ul>
      <li>You think of AI as a partner, not a search box</li>
      <li>You value compounding returns over instant gratification</li>
      <li>You're comfortable delegating real decisions to a trusted system</li>
      <li>You want to contribute to — and benefit from — collective intelligence</li>
    </ul>
  </div>

  <div class="footer">
    <p>Questions? Reply to this email or write to <a href="mailto:hello@mindeigen.com">hello@mindeigen.com</a></p>
    <p style="margin-top:8px">© 2026 MindEigen &nbsp;·&nbsp; <a href="https://mindeigen.com">mindeigen.com</a></p>
    <p style="font-family:monospace;font-size:.68rem;color:#2a2f45;margin-top:8px">A·mind = λ·mind</p>
  </div>
</div></body></html>
"""

WELCOME_TEXT = """\
You're on the MindEigen waitlist. Your eigenvalue awaits.

We received your request for early access. You're among a small group of early adopters
who will be the first to deploy a personal AI agent that thinks, evolves, and heals — on your behalf.

A·mind = λ·mind → find λ, amplify it. ∞

WHAT HAPPENS NEXT
- We're onboarding early users in small cohorts
- You'll receive a personal invite with setup instructions
- Your agent will be provisioned and ready to deploy
- Early adopters get priority access to the community skill graph

Questions? hello@mindeigen.com
© 2026 MindEigen — https://mindeigen.com
"""

def load_waitlist():
    if WAITLIST_FILE.exists():
        return json.loads(WAITLIST_FILE.read_text())
    return []

def save_email(email):
    wl = load_waitlist()
    if email in [e["email"] for e in wl]:
        return False, "already_registered"
    wl.append({"email": email, "ts": datetime.now(timezone.utc).isoformat()})
    WAITLIST_FILE.write_text(json.dumps(wl, indent=2))
    return True, "ok"

def sendgrid_send(payload):
    import urllib.request
    req = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {SENDGRID_API_KEY}",
                 "Content-Type": "application/json"},
        method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print(f"SendGrid error: {e}", file=sys.stderr)
        return False

def send_emails_async(email):
    """Fire-and-forget: send both notification + welcome in background thread."""
    import threading
    def _send():
        send_admin_notification(email)
        send_welcome_email(email)
    t = threading.Thread(target=_send, daemon=True)
    t.start()

def send_admin_notification(email):
    count = len(load_waitlist())
    return sendgrid_send({
        "personalizations": [{"to": [{"email": NOTIFY_EMAIL}]}],
        "from": {"email": FROM_EMAIL, "name": FROM_NAME},
        "subject": f"🧠 New waitlist signup #{count}: {email}",
        "content": [{"type": "text/plain",
                     "value": f"New signup: {email}\nTotal on list: {count}\nTime: {datetime.now(timezone.utc).isoformat()}"}]
    })

def send_welcome_email(email):
    return sendgrid_send({
        "personalizations": [{"to": [{"email": email}]}],
        "from": {"email": FROM_EMAIL, "name": FROM_NAME},
        "reply_to": {"email": FROM_EMAIL, "name": FROM_NAME},
        "subject": "You're on the MindEigen waitlist — your eigenvalue awaits 🧠",
        "content": [
            {"type": "text/plain", "value": WELCOME_TEXT},
            {"type": "text/html",  "value": WELCOME_HTML},
        ]
    })

def validate_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {fmt % args}")

    def send_json(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        if self.path != "/waitlist":
            self.send_json(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode()
        try:
            data = json.loads(raw)
        except Exception:
            data = {k: v[0] for k, v in parse_qs(raw).items()}
        email = data.get("email", "").strip().lower()
        if not validate_email(email):
            self.send_json(400, {"status": "error", "message": "Invalid email"})
            return
        ok, reason = save_email(email)
        if not ok:
            self.send_json(200, {"status": "duplicate", "message": "Already on the list!"})
            return
        send_emails_async(email)  # non-blocking — respond immediately
        self.send_json(200, {"status": "ok", "message": "You're on the list!"})

    def do_GET(self):
        if self.path == "/waitlist/count":
            count = len(load_waitlist())
            self.send_json(200, {"count": count})
        elif self.path == "/waitlist/list" and self.headers.get("X-Token") == os.environ.get("OPENCLAW_GATEWAY_TOKEN",""):
            self.send_json(200, {"entries": load_waitlist()})
        else:
            self.send_json(403, {"error": "forbidden"})

if __name__ == "__main__":
    print(f"🧠 MindEigen waitlist server on 127.0.0.1:{PORT}")
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
