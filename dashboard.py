import os
from flask import Flask, render_template, Response
from apscheduler.schedulers.background import BackgroundScheduler
import requests, time
from datetime import datetime, timedelta

# === Flask App ===
app = Flask(__name__)

# === Credentials (env or fallback) ===
USERNAME = os.getenv("EMIL_USERNAME", "frank+livehealthcheck@occ.eu")
PASSWORD = os.getenv("EMIL_PASSWORD", "Healthcheck!OCC2025")

# === API Endpoints ===
AUTH_URL    = "https://apiv2.emil.de/authservice/v1/login"
REFRESH_URL = "https://apiv2.emil.de/authservice/v1/refresh-token"
HEALTH_URLS = {
    "authservice":      "https://apiv2.emil.de/authservice/health",
    "accountservice":   "https://apiv2.emil.de/accountservice/health",
    "billingservice":   "https://apiv2.emil.de/billingservice/health",
    "customerservice":  "https://apiv2.emil.de/customerservice/health",
    "claims":           "https://apiv2.emil.de/v1/claims/health",
    "documentservice":  "https://apiv2.emil.de/documentservice/health",
    "insuranceservice": "https://apiv2.emil.de/insuranceservice/health",
    "paymentservice":   "https://apiv2.emil.de/paymentservice/health",
    "processmanager":   "https://apiv2.emil.de/processmanager/health",
    "translationsvc":   "https://apiv2.emil.de/translationservice/health",
    "partnerservice":   "https://apiv2.emil.de/partnerservice/health",
    "policyadmin":      "https://apiv2.emil.de/policy-administration-service/health",
    "numbergenerator":  "https://apiv2.emil.de/numbergenerator/health",
}

# === Global State ===
token = None
statuses = {}

# === Authentication ===
def authenticate():
    """Holt den initialen Token."""
    global token
    resp = requests.post(
        AUTH_URL,
        json={"username": USERNAME, "password": PASSWORD},
        timeout=5
    )
    resp.raise_for_status()
    token = resp.json().get("accessToken")
    print("[AUTH] Token erhalten")

def refresh_token():
    """Erneuert den Token alle 10 Minuten."""
    global token
    try:
        resp = requests.post(
            REFRESH_URL,
            json={"username": USERNAME},
            timeout=5
        )
        if resp.status_code == 200:
            token = resp.json().get("accessToken")
            print("[REFRESH] Token erneuert")
        else:
            print(f"[REFRESH] Warnung: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[REFRESH] Ausnahme: {e}")

# === Status Updates ===
def update_statuses():
    """Fragt alle Health-Endpoints ab (alle 30 Sekunden)."""
    global statuses
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    new = {}
    for name, url in HEALTH_URLS.items():
        try:
            r = requests.get(url, headers=headers, timeout=5)
            code = r.status_code
            if code == 200:
                color = "green"
            elif code == 503:
                color = "yellow"
            else:
                color = "red"
        except requests.RequestException:
            color = "yellow"
        new[name] = color
    statuses = new
    print(time.strftime("%Y-%m-%d %H:%M:%S"), statuses)

# === Scheduler Setup ===
sched = BackgroundScheduler()
# Einmalig sofort initial authentifizieren
sched.add_job(authenticate, "date", run_date=datetime.now() + timedelta(seconds=1))
# Token-Erneuerung alle 10 Minuten
sched.add_job(refresh_token, "interval", minutes=10)
# Healthchecks alle 30 Sekunden
sched.add_job(update_statuses, "interval", seconds=30)
sched.start()

# Direkt einmal ausführen, damit unter Gunicorn initial Daten da sind
authenticate()
update_statuses()

# === Flask Routes ===
@app.route("/")
def index():
    return render_template("index.html", statuses=statuses)

def build_prtg_xml(status_dict):
    """Erstellt das PRTG-XML mit <result>-Einträgen."""
    mapping = {"green": 0, "yellow": 1, "red": 2}
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<prtg>"]
    for name, color in status_dict.items():
        val = mapping.get(color, 2)
        lines.extend([
            "  <result>",
            f"    <channel>{name}</channel>",
            f"    <value>{val}</value>",
            "    <unit>Custom</unit>",
            "  </result>",
        ])
    lines.append("<text>All services checked</text>")
    lines.append("</prtg>")
    return "\n".join(lines)

@app.route("/api/status.xml")
def status_xml():
    xml = build_prtg_xml(statuses)
    return Response(xml, mimetype="application/xml")

# === Main Entry Point ===
if __name__ == "__main__":
    # Nur beim direkten Start: Flask-Devserver
    app.run(host="0.0.0.0", port=5000, debug=False)
