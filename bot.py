import time
import sqlite3
import requests
import hashlib
import os
from datetime import datetime

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")          # Render ENV
CHAT_IDS = os.getenv("CHAT_IDS", "").split(",")

CHECK_DELAY = 15  # seconds
DB_FILE = "shein.db"

MEN_API_URL = (
    "https://www.sheinindia.in/api/category/sverse-5939-37961"
    "?fields=SITE&currentPage=0&pageSize=45&format=json"
    "&query=%3Anewest%3Agenderfilter%3AMen"
    "&sort=9&gridColumns=2&facets=genderfilter%3AMen"
)

API_URLS = [
    {"name": "Men", "url": MEN_API_URL}
]

# ============================================


class SheinMonitor:
    def __init__(self):
        if not BOT_TOKEN or not CHAT_IDS:
            raise Exception("❌ BOT_TOKEN or CHAT_IDS missing")

        self.session = requests.Session()
        self.setup_db()
        self.send_test_message()
        print("🤖 SHEIN Bot started (Render Ready)")

    def setup_db(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT,
                category TEXT,
                name TEXT,
                url TEXT,
                PRIMARY KEY (id, category)
            )
        """)
        self.conn.commit()

    def is_new(self, pid, category):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT 1 FROM products WHERE id=? AND category=?",
            (pid, category)
        )
        return cur.fetchone() is None

    def save(self, pid, name, url, category):
        cur = self.conn.cursor()
        cur.execute(
            "INSERT OR IGNORE INTO products VALUES (?,?,?,?)",
            (pid, category, name, url)
        )
        self.conn.commit()

    def send_telegram(self, message):
        api = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        for chat_id in CHAT_IDS:
            if not chat_id:
                continue
            requests.post(api, data={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            })

    def send_test_message(self):
        msg = (
            "<b>🧪 SHEIN Bot Live!</b>\n"
            f"⏰ {datetime.now().strftime('%H:%M:%S')}"
        )
        self.send_telegram(msg)

    def fetch_products(self, url):
        try:
            r = self.session.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            data = r.json()
            return data.get("products", [])
        except Exception as e:
            print("❌ Fetch error:", e)
            return []

    def run(self):
        first_run = True

        while True:
            for cat in API_URLS:
                category = cat["name"]
                products = self.fetch_products(cat["url"])
                new_items = []

                for p in products:
                    pid = str(
                        p.get("id") or
                        hashlib.md5(p.get("url", "").encode()).hexdigest()
                    )
                    name = p.get("name", "Unknown")
                    url = "https://www.sheinindia.in" + p.get("url", "")

                    if self.is_new(pid, category):
                        self.save(pid, name, url, category)
                        new_items.append((pid, name, url))

                if first_run and new_items:
                    msg = f"<b>🚨 INITIAL PRODUCTS ({category})</b>\n\n"
                  
