"""SQLite-хранилище"""
from __future__ import annotations
import copy, json, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "community.sqlite3"

DEFAULT_SETTINGS = {
    "application_title": "Подача заявок",
    "application_intro": "Выберите тип заявки и заполните форму.",
    "application_note": "Отвечайте честно.",
    "guide_title": "{server}", "guide_intro": "Всё о сервере", "guide_activity": "Мы активно играем", "guide_important": "Соблюдайте правила",
    "guide_details": {"rules": "", "roles": "", "about": ""},
    "application_channel_id": None, "application_panel_message_id": None, "application_inbox_id": None,
    "application_log_channels": {"squad": None, "staff": None, "complaint": None},
    "application_category_id": None, "review_role_id": None, "guide_channel_id": None, "guide_message_id": None,
    "welcome_channel_id": None, "market_channel_id": None, "temp_voice_creator_id": None,
    "ticket_category_id": None, "ticket_staff_role_id": None, "ticket_log_channel_id": None,
    "reaction_roles_channel_id": None,
    "license_key": None, "is_active": False, "license_expires": None,
    "automod_words": ["хуй", "пизда", "блядь", "ебать", "сука", "fuck", "shit"],
    "staff_roles": {},
    "brand_name": "Наш сервер", # Для кастомизации
}

def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_storage() -> None:
    with _connect() as c:
        c.execute("CREATE TABLE IF NOT EXISTS guild_settings (guild_id TEXT PRIMARY KEY, settings_json TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS join_counts (guild_id TEXT, user_id TEXT, joins INTEGER DEFAULT 0, PRIMARY KEY (guild_id, user_id))")
        c.execute("CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, applicant_id TEXT, category TEXT, payload_json TEXT, status TEXT DEFAULT 'pending', channel_id TEXT, message_id TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        c.execute("CREATE TABLE IF NOT EXISTS licenses (key TEXT PRIMARY KEY, guild_id TEXT, expires_at TEXT, is_used INTEGER DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS reputation (guild_id TEXT, user_id TEXT, amount INTEGER DEFAULT 0, PRIMARY KEY(guild_id, user_id))")
        c.execute("CREATE TABLE IF NOT EXISTS economy (guild_id TEXT, user_id TEXT, balance INTEGER DEFAULT 0, last_daily TEXT, PRIMARY KEY(guild_id, user_id))")
        c.execute("CREATE TABLE IF NOT EXISTS market (id INTEGER PRIMARY KEY, guild_id TEXT, author_id TEXT, message_id TEXT, type TEXT, title TEXT, description TEXT, price TEXT, expires_at TEXT, is_active INTEGER DEFAULT 1)")
        c.execute("CREATE TABLE IF NOT EXISTS staff_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, actor_id TEXT, action TEXT, target TEXT, timestamp TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT, user_id TEXT, channel_id TEXT, status TEXT DEFAULT 'open', created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

def get_settings(guild_id: int) -> dict:
    with _connect() as c:
        row = c.execute("SELECT settings_json FROM guild_settings WHERE guild_id = ?", (str(guild_id),)).fetchone()
    s = copy.deepcopy(DEFAULT_SETTINGS)
    if row:
        try:
            saved = json.loads(row["settings_json"])
            if isinstance(saved, dict):
                s.update(saved)
                for k in ["guide_details", "application_log_channels", "automod_words", "staff_roles"]:
                    if k in saved and isinstance(saved[k], (dict, list)): s[k] = saved[k]
        except: pass
    return s

def save_settings(guild_id: int, settings: dict) -> None:
    with _connect() as c:
        c.execute("INSERT INTO guild_settings(guild_id, settings_json) VALUES(?, ?) ON CONFLICT(guild_id) DO UPDATE SET settings_json=excluded.settings_json", (str(guild_id), json.dumps(settings, ensure_ascii=False)))

def create_application(guild_id: int, applicant_id: int, category: str, payload: dict) -> int:
    with _connect() as c:
        cur = c.execute("INSERT INTO applications(guild_id, applicant_id, category, payload_json) VALUES(?, ?, ?, ?)", (str(guild_id), str(applicant_id), category, json.dumps(payload, ensure_ascii=False)))
        return int(cur.lastrowid)

def set_application_message(app_id: int, ch_id: int, msg_id: int) -> None:
    with _connect() as c: c.execute("UPDATE applications SET channel_id=?, message_id=? WHERE id=?", (str(ch_id), str(msg_id), app_id))

def get_application(app_id: int) -> dict | None:
    with _connect() as c: row = c.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not row: return None
    r = dict(row)
    try: r["payload"] = json.loads(r.pop("payload_json"))
    except: r["payload"] = {}
    return r

def list_pending_applications() -> list[dict]:
    with _connect() as c: rows = c.execute("SELECT id, guild_id, applicant_id, category, channel_id, message_id FROM applications WHERE status='pending' AND message_id IS NOT NULL").fetchall()
    return [dict(r) for r in rows]

def update_application_status(app_id: int, status: str) -> None:
    with _connect() as c: c.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))

def record_join(guild_id: int, user_id: int) -> int:
    with _connect() as c:
        c.execute("INSERT INTO join_counts(guild_id, user_id, joins) VALUES(?, ?, 1) ON CONFLICT(guild_id, user_id) DO UPDATE SET joins=joins+1", (str(guild_id), str(user_id)))
        row = c.execute("SELECT joins FROM join_counts WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id))).fetchone()
    return int(row[0]) if row else 1

def log_staff_action(guild_id: int, actor_id: int, action: str, target: str):
    from datetime import datetime
    with _connect() as c: c.execute("INSERT INTO staff_logs (guild_id, actor_id, action, target, timestamp) VALUES (?, ?, ?, ?, ?)", (str(guild_id), str(actor_id), action, target, datetime.utcnow().isoformat()))

def get_balance(guild_id: int, user_id: int) -> int:
    with _connect() as c:
        row = c.execute("SELECT balance FROM economy WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id))).fetchone()
    return int(row[0]) if row else 0

def add_balance(guild_id: int, user_id: int, amount: int):
    with _connect() as c:
        c.execute("INSERT INTO economy (guild_id, user_id, balance) VALUES (?, ?, ?) ON CONFLICT(guild_id, user_id) DO UPDATE SET balance = balance + ?", (str(guild_id), str(user_id), amount, amount))

def get_rep(guild_id: int, user_id: int) -> int:
    with _connect() as c:
        row = c.execute("SELECT amount FROM reputation WHERE guild_id=? AND user_id=?", (str(guild_id), str(user_id))).fetchone()
    return int(row[0]) if row else 0

def add_rep(guild_id: int, user_id: int, amount: int = 1):
    with _connect() as c:
        c.execute("INSERT INTO reputation (guild_id, user_id, amount) VALUES (?, ?, ?) ON CONFLICT(guild_id, user_id) DO UPDATE SET amount = amount + ?", (str(guild_id), str(user_id), amount, amount))

def count_applications(guild_id: int, category: str) -> int:
    with _connect() as c:
        row = c.execute("SELECT COUNT(*) FROM applications WHERE guild_id=? AND category=? AND status='pending'", (str(guild_id), category)).fetchone()
    return row[0] if row else 0