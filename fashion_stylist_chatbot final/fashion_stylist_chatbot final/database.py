"""SQLite persistence for profiles, chat history, and recommendations."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from config import DATABASE_DIR, DATABASE_PATH


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connection():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password_hash TEXT,
            display_name TEXT NOT NULL DEFAULT 'You',
            session_token TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            preferences_json TEXT NOT NULL DEFAULT '{}',
            remember_enabled INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL DEFAULT 'New chat',
            profile_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            outfit_id TEXT,
            recommendation_text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        """)
        # Safe migration for existing databases
        cursor = conn.execute("PRAGMA table_info(users)")
        columns = [col["name"] for col in cursor.fetchall()]
        if "email" not in columns:
            if "username" in columns:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
                conn.execute("UPDATE users SET email = username WHERE email IS NULL")
            else:
                conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        if "password_hash" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        if "display_name" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT 'You'")
        if "session_token" not in columns:
            conn.execute("ALTER TABLE users ADD COLUMN session_token TEXT")
        cursor = conn.execute("PRAGMA table_info(conversations)")
        conversation_columns = [col["name"] for col in cursor.fetchall()]
        if "profile_json" not in conversation_columns:
            conn.execute("ALTER TABLE conversations ADD COLUMN profile_json TEXT NOT NULL DEFAULT '{}'")


def get_user_by_email(email):
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id):
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_username(username):
    """Backwards compatibility helper."""
    return get_user_by_email(username)


def set_user_session_token(user_id, token_hash):
    with connection() as conn:
        conn.execute("UPDATE users SET session_token = ? WHERE id = ?", (token_hash, user_id))


def get_user_by_session_token(token_hash):
    with connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE session_token = ?", (token_hash,)).fetchone()
    return dict(row) if row else None


def create_user_with_credentials(email, password_hash, display_name="You"):
    now = utc_now()
    with connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, display_name, created_at) VALUES (?, ?, ?, ?)",
            (email, password_hash, display_name, now)
        )
        user_id = cur.lastrowid
        if user_id is None:
            raise RuntimeError("Failed to create user")
        conn.execute(
            "INSERT INTO user_preferences (user_id, preferences_json, remember_enabled, updated_at) VALUES (?, '{}', 1, ?)",
            (user_id, now)
        )
        return int(user_id)


def update_user_password(email, password_hash):
    with connection() as conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (password_hash, email))


def get_default_user_id():
    init_db()
    with connection() as conn:
        row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        return int(row["id"]) if row else None


def get_preferences(user_id):
    import json
    with connection() as conn:
        row = conn.execute("SELECT preferences_json, remember_enabled FROM user_preferences WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        return {}, True
    try:
        prefs = json.loads(row["preferences_json"])
    except (TypeError, json.JSONDecodeError):
        prefs = {}
    return prefs, bool(row["remember_enabled"])


def save_preferences(user_id, preferences, remember_enabled=True):
    import json
    with connection() as conn:
        conn.execute("""INSERT INTO user_preferences(user_id, preferences_json, remember_enabled, updated_at)
            VALUES (?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET
            preferences_json=excluded.preferences_json, remember_enabled=excluded.remember_enabled,
            updated_at=excluded.updated_at""",
            (user_id, json.dumps(preferences, ensure_ascii=False), int(remember_enabled), utc_now()))


def create_conversation(user_id, title="New chat"):
    now = utc_now()
    with connection() as conn:
        cur = conn.execute("INSERT INTO conversations(user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                           (user_id, title, now, now))
        lastrowid = cur.lastrowid
        if lastrowid is None:
            raise RuntimeError("Failed to create conversation")
        return int(lastrowid)


def list_conversations(user_id):
    with connection() as conn:
        rows = conn.execute("SELECT c.id, c.title, c.created_at, c.updated_at FROM conversations c WHERE c.user_id=? AND EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=c.id) ORDER BY c.updated_at DESC", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def get_conversation(conversation_id, user_id):
    with connection() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id)).fetchone()
    return dict(row) if row else None


def get_conversation_profile(conversation_id):
    import json
    with connection() as conn:
        row = conn.execute("SELECT profile_json FROM conversations WHERE id=?", (conversation_id,)).fetchone()
    if row is None:
        return {}
    try:
        profile = json.loads(row["profile_json"])
    except (TypeError, json.JSONDecodeError):
        return {}
    return profile if isinstance(profile, dict) else {}


def save_conversation_profile(conversation_id, profile):
    import json
    with connection() as conn:
        conn.execute(
            "UPDATE conversations SET profile_json=? WHERE id=?",
            (json.dumps(profile, ensure_ascii=False), conversation_id),
        )


def update_conversation_title(conversation_id, title):
    clean_title = " ".join((title or "").split()).strip(" .!?\t\n")
    clean_title = clean_title[:52].rstrip() or "Fashion chat"
    with connection() as conn:
        conn.execute("UPDATE conversations SET title=?, updated_at=? WHERE id=? AND title='New chat'",
                     (clean_title, utc_now(), conversation_id))


def add_message(conversation_id, role, message):
    now = utc_now()
    with connection() as conn:
        conn.execute("INSERT INTO messages(conversation_id, role, message, created_at) VALUES (?, ?, ?, ?)",
                     (conversation_id, role, message, now))
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (now, conversation_id))


def get_messages(conversation_id):
    with connection() as conn:
        rows = conn.execute("SELECT role, message, created_at FROM messages WHERE conversation_id=? ORDER BY id", (conversation_id,)).fetchall()
    return [dict(row) for row in rows]


def add_recommendation(conversation_id, outfit_id, recommendation_text):
    with connection() as conn:
        conn.execute("INSERT INTO recommendations(conversation_id, outfit_id, recommendation_text, created_at) VALUES (?, ?, ?, ?)",
                     (conversation_id, outfit_id, recommendation_text, utc_now()))


def delete_conversation(conversation_id, user_id):
    with connection() as conn:
        conn.execute("DELETE FROM conversations WHERE id=? AND user_id=?", (conversation_id, user_id))


def delete_all_conversations(user_id):
    with connection() as conn:
        conn.execute("DELETE FROM conversations WHERE user_id=?", (user_id,))