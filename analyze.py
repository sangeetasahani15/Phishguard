from http.server import BaseHTTPRequestHandler
import json, re

URG = ["urgent","immediately","act now","within 24 hours","expires","suspended","final notice","verify now","last warning","account locked","limited time","action required"]
CRED = ["password","otp","one-time","ssn","social security","bank account","credit card","cvv","pin number","gift card","wire transfer","bitcoin","routing number"]
PRIZE = ["you won","winner","lottery","prize","claim your","free gift","congratulations","inheritance","million"]
SHORT = ["bit.ly","tinyurl.com","t.co","goo.gl","ow.ly","is.gd","cutt.ly","rb.gy"]
TLDS = [".xyz",".top",".click",".tk",".ml",".ga",".cf",".gq",".work",".zip",".country"]
FREE = ["gmail.com","yahoo.com","outlook.com","hotmail.com","aol.com","proton.me"]
BRANDS = ["paypal","amazon","microsoft","google","apple","netflix","bank","hdfc","sbi","icici","paytm","irs","fedex","dhl"]
LOOK = ["paypa1","micros0ft","g00gle","amaz0n","arnazon","faceb00k","netfliix","app1e","rnicrosoft"]
BADEXT = [".exe",".scr",".js",".bat",".vbs",".jar",".zip",".html"]

def analyze(sender, subject, body):
    sender, subject, body = str(sender or ""), str(subject or ""), str(body or "")
    text = (subject + " " + body).lower()
    f = []
    def add(cat, msg, pts):
        f.append({"category": cat, "message": msg, "points": pts})
    def hits(words):
        return [w for w in words if w in text]
    h = hits(URG)
    if h: add("Language", "Urgency / pressure wording: " + ", ".join(h[:4]), min(25, 8*len(h)))
    h = hits(CRED)
    if h: add("Language", "Asks for sensitive information: " + ", ".join(h[:4]), min(25, 10*len(h)))
    h = hits(PRIZE)
    if h: add("Language", "Prize / lottery bait: " + ", ".join(h[:3]), 15)
    if re.search(r"\b(dear (customer|user|client|member)|valued customer)\b", text):
        add("Language", "Generic greeting instead of your name", 5)
    letters = [c for c in subject + body if c.isalpha()]
    if len(letters) > 30 and sum(c.isupper() for c in letters)/len(letters) > 0.4:
        add("Style", "Excessive ALL-CAPS text", 5)
    if (subject + body).count("!") >= 3:
        add("Style", "Excessive exclamation marks", 5)
    urls = re.findall(r"(?:https?://|www\.)[^\s<>\"')]+", body, re.I)
    for u in urls[:10]:
        ul = u.lower()
        host = re.sub(r"^(https?://)?(www\.)?", "", ul).split("/")[0].split(":")[0]
        if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", host): add("Links", "Link uses a raw IP address: " + u[:60], 20)
        elif any(host == s for s in SHORT): add("Links", "URL shortener hides destination: " + host, 12)
        elif "xn--" in host or "@" in ul.split("//",1)[-1].split("/")[0]:
            add("Links", "Deceptive link structure: " + u[:60], 15)
        elif any(host.endswith(t) for t in TLDS): add("Links", "Suspicious domain ending: " + host, 10)
        if ul.startswith("http://"): add("Links", "Unencrypted (http) link: " + u[:60], 5)
    sl = sender.lower()
    m = re.search(r"[\w.+-]+@([\w.-]+)", sl)
    dom = m.group(1) if m else ""
    if sender.strip() and not m:
        add("Sender", "Sender address is not a valid email", 10)
    if any(l in sl or l in text for l in LOOK):
        add("Sender", "Look-alike brand spelling detected (e.g. paypa1)", 25)
    name = sl.split("<")[0]
    if dom:
        for b in BRANDS:
            if b in name and b not in dom:
                add("Sender", "Display name claims '" + b + "' but domain is " + dom, 25); break
        if dom in FREE and any(b in text for b in BRANDS[:6]):
            add("Sender", "Brand mentioned but sent from free email service (" + dom + ")", 15)
        if any(dom.endswith(t) for t in TLDS):
            add("Sender", "Sender domain has suspicious ending: " + dom, 10)
    for e in BADEXT:
        if re.search(r"[\w-]+" + re.escape(e) + r"\b", text):
            add("Attachment", "Risky attachment type mentioned: " + e, 15); break
    score = min(100, sum(x["points"] for x in f))
    if score < 25: v, c = "Likely Safe", "safe"
    elif score < 50: v, c = "Suspicious", "low"
    elif score < 75: v, c = "Likely Phishing", "high"
    else: v, c = "Fraud / Phishing", "critical"
    return {"score": score, "verdict": v, "level": c, "findings": f, "engine": "python-api"}

class handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def do_OPTIONS(self):
        self._send(200, {})
    def do_GET(self):
        self._send(200, {"status": "ok"})
    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            d = json.loads(self.rfile.read(n) or b"{}")
            self._send(200, analyze(d.get("sender"), d.get("subject"), d.get("body")))
        except Exception as e:
            self._send(400, {"error": str(e)})
