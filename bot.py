import re
import requests
from datetime import datetime
import time
import threading
from flask import Flask, jsonify
import os

# ==================== FLASK APP ====================
app = Flask(__name__)

# ==================== SILENT MODE ====================
import sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Suppress all output
sys.stdout = open(os.devnull, 'w')
sys.stderr = open(os.devnull, 'w')

# ==================== CONFIGURATION ====================
# Read from environment variables for Render
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "7325597357:AAGt0t9u-5GHR6VOVdXFMdzNqAsT572lPBk")
CHAT_ID = os.environ.get("CHAT_ID", "-1004290930965")  # GENESYS_SMS group

# Optional: Read credentials from env or use defaults
CREDENTIALS = [
    {"username": "CRIMSON", "password": os.environ.get("CRIMSON_PASS", "CRIMSON")},
    {"username": "FUNFAM01", "password": os.environ.get("FUNFAM01_PASS", "FUNFAM01")},
    {"username": "DURANGO", "password": os.environ.get("DURANGO_PASS", "DURANGO")},
    {"username": "GENESYS1", "password": os.environ.get("GENESYS1_PASS", "GENESYS1")},
    {"username": "TRAIL01", "password": os.environ.get("TRAIL01_PASS", "TRAIL01")},
    {"username": "TOSS199", "password": os.environ.get("TOSS199_PASS", "TOSS199")},
]

BASE_URL = "http://15.235.182.3/konekta"
LOGIN_URL = f"{BASE_URL}/sign-in"
POST_URL = f"{BASE_URL}/signin"
DATA_URL = f"{BASE_URL}/client/res/data_smscdr.php"

last_seen = {}
lock = threading.Lock()
running = True
active_sessions = {}

COUNTRY_FLAGS = {
    "Zimbabwe": "🇿🇼", "Egypt": "🇪🇬", "South Africa": "🇿🇦", "Nigeria": "🇳🇬",
    "Kenya": "🇰🇪", "Uganda": "🇺🇬", "Tanzania": "🇹🇿", "Ghana": "🇬🇭",
    "Morocco": "🇲🇦", "Algeria": "🇩🇿", "USA": "🇺🇸", "UK": "🇬🇧",
    "Canada": "🇨🇦", "Australia": "🇦🇺", "India": "🇮🇳", "Pakistan": "🇵🇰",
    "Bangladesh": "🇧🇩", "Saudi": "🇸🇦", "UAE": "🇦🇪", "Turkey": "🇹🇷",
    "Russia": "🇷🇺", "China": "🇨🇳"
}

# ==================== HELPER FUNCTIONS ====================
def mask_number(number):
    try:
        if not number or len(number) < 7:
            return number
        number_str = str(number)
        if len(number_str) <= 7:
            return number_str
        return f"{number_str[:3]}{'*' * (len(number_str) - 7)}{number_str[-4:]}"
    except:
        return number

def send_telegram_message(text, keyboard=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = keyboard
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def extract_country_and_flag(range_name):
    try:
        for country, flag in COUNTRY_FLAGS.items():
            if country.lower() in range_name.lower():
                return country, flag
        return "Unknown", "🏳️"
    except:
        return "Unknown", "🏳️"

def send_telegram_with_button(account, msg):
    try:
        country_name, flag = extract_country_and_flag(msg['range'])
        masked_num = mask_number(msg['number'])
        
        # Format with account and quoted
        formatted = f'''"<blockquote>⏰ <b>Time:</b> {msg['time']}</blockquote>
<blockquote>🌍 <b>Country:</b> {country_name} {flag}</blockquote>
<blockquote>📌 <b>Sender:</b> {msg['cli']}</blockquote>
<blockquote>☎️ <b>Number:</b> {masked_num}</blockquote>
<blockquote>🌐 <b>Range:</b> {msg['range']}</blockquote>
<blockquote>👤 <b>Account:</b> {account}</blockquote>

Panel - Konekta"'''
        
        keyboard = {"inline_keyboard": [[{"text": "👨‍💻 Developer", "url": "https://t.me/prince_ACTIVE1"}]]}
        send_telegram_message(formatted, keyboard)
    except:
        pass

def solve_captcha(html):
    try:
        match = re.search(r'What is\s+(\d+)\s*\+\s*(\d+)\s*=\s*\?', html)
        if match:
            return str(int(match.group(1)) + int(match.group(2)))
    except:
        pass
    return None

def login_account(username, password):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
    
    for attempt in range(3):
        try:
            resp = session.get(LOGIN_URL, timeout=15)
            if resp.status_code != 200:
                time.sleep(2)
                continue
            
            captcha_answer = solve_captcha(resp.text)
            if not captcha_answer:
                time.sleep(2)
                continue
            
            payload = {"username": username, "password": password, "capt": captcha_answer}
            login_resp = session.post(POST_URL, data=payload, allow_redirects=True, timeout=15)
            
            if "sign-in" not in login_resp.url:
                return session, username
        except:
            pass
        time.sleep(2)
    return None, username

def fetch_latest_messages(session):
    try:
        today = datetime.now()
        params = {
            "fdate1": today.strftime("%Y-%m-%d 00:00:00"),
            "fdate2": today.strftime("%Y-%m-%d 23:59:59"),
            "frange": "", "fnum": "", "fcli": "", "fg": "0",
            "sEcho": "1", "iDisplayStart": "0", "iDisplayLength": "10",
            "_": str(int(datetime.now().timestamp() * 1000))
        }
        
        headers = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}
        response = session.get(DATA_URL, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            messages = []
            for row in data.get("aaData", []):
                if len(row) >= 6 and row[0] and row[0] != "0":
                    try:
                        msg_time = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                        messages.append({
                            "time": row[0],
                            "range": row[1] if len(row) > 1 else "Unknown",
                            "number": row[2] if len(row) > 2 else "Unknown",
                            "cli": row[3] if len(row) > 3 else "Unknown",
                            "timestamp": msg_time
                        })
                    except:
                        pass
            messages.sort(key=lambda x: x["timestamp"], reverse=True)
            return messages
    except:
        pass
    return []

def refresh_session(username):
    cred = next((c for c in CREDENTIALS if c["username"] == username), None)
    if cred:
        session, _ = login_account(cred["username"], cred["password"])
        if session:
            with lock:
                active_sessions[username] = session
            return session
    return None

def monitor_account_live(username):
    while running:
        try:
            with lock:
                session = active_sessions.get(username)
            if not session:
                session = refresh_session(username)
                if not session:
                    time.sleep(10)
                    continue
            
            messages = fetch_latest_messages(session)
            if messages:
                latest_msg = messages[0]
                with lock:
                    last_time = last_seen.get(username)
                    if last_time is None or latest_msg["timestamp"] > last_time:
                        send_telegram_with_button(username, latest_msg)
                        last_seen[username] = latest_msg["timestamp"]
            time.sleep(1)
        except:
            time.sleep(5)

# ==================== FLASK ROUTES ====================
@app.route('/')
def home():
    return jsonify({"status": "running", "accounts": len(active_sessions)})

@app.route('/health')
def health():
    return jsonify({"status": "healthy"})

# ==================== MAIN ====================
def start_monitoring():
    global active_sessions
    
    sessions = []
    for cred in CREDENTIALS:
        session, username = login_account(cred["username"], cred["password"])
        if session:
            sessions.append((session, username))
    
    with lock:
        for session, username in sessions:
            active_sessions[username] = session
    
    # Send last messages
    for username, session in active_sessions.items():
        try:
            messages = fetch_latest_messages(session)
            if messages:
                last_msg = messages[0]
                with lock:
                    last_seen[username] = last_msg["timestamp"]
                send_telegram_with_button(username, last_msg)
        except:
            pass
    
    # Start monitoring threads
    for username in active_sessions.keys():
        threading.Thread(target=monitor_account_live, args=(username,), daemon=True).start()

if __name__ == "__main__":
    # Silent startup - send one notification
    try:
        send_telegram_message('"<b>🤖 SMS Monitor Started</b>\n\nMonitoring active..."')
    except:
        pass
    
    # Start monitoring
    threading.Thread(target=start_monitoring, daemon=True).start()
    
    # Start Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
