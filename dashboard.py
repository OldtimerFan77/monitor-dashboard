import os
from flask import Flask, render_template, jsonify
from flask import Response
import requests
from datetime import datetime

app = Flask(__name__)

# === API URLs ===
AUTH_URL    = "https://apiv2.emil.de/authservice/v1/login"
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

# Credentials via Env-Variablen
USERNAME = os.environ["USERNAME"]
PASSWORD = os.environ["PASSWORD"]

def get_token():
    r = requests.post(AUTH_URL,
                      json={"username": USERNAME, "password": PASSWORD},
                      timeout=10)
    r.raise_for_status()
    return r.json()["accessToken"]

def check_services(token):
    hdr = {"Authorization": f"Bearer {token}"}
    out = {}
    for name, url in HEALTH_URLS.items():
        try:
            r = requests.get(url, headers=hdr, timeout=5)
            code = r.status_code
            out[name] = "green" if code==200 else "yellow" if code==503 else "red"
        except:
            out[name] = "yellow"
    return out

@app.route("/")
def index():
    token    = get_token()
    statuses = check_services(token)
    ts       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return render_template("index.html", statuses=statuses, ts=ts)

# JSON-Endpoint für PRTG
@app.route("/api/status")
def api_status():
    token    = get_token()
    statuses = check_services(token)
    return jsonify(statuses)
def build_prtg_xml(statuses: dict) -> str:
    mapping = {'green': 0, 'yellow': 1, 'red': 2}
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<prtg>']
    for name, color in statuses.items():
        val = mapping.get(color, 2)
        xml_lines += [
            '  <result>',
            f'    <channel>{name}</channel>',
            f'    <value>{val}</value>',
            '    <unit>Custom</unit>',
            '  </result>',
        ]
    xml_lines.append('<text>All services checked</text>')
    xml_lines.append('</prtg>')
    return "\n".join(xml_lines)

@app.route('/api/status.xml')
def status_xml():
    global statuses
    xml = build_prtg_xml(statuses)
    return Response(xml, mimetype='application/xml')

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
