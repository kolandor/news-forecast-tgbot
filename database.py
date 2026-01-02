import sqlite3
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from config import SQLITE_PATH

logger = logging.getLogger(__name__)

def get_connection():
    return sqlite3.connect(SQLITE_PATH)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Subscribers table
    c.execute('''
    CREATE TABLE IF NOT EXISTS subscribers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE NOT NULL,
        user_id INTEGER,
        created_at TEXT,
        active INTEGER NOT NULL DEFAULT 1
    )
    ''')
    
    # Forecast Schedules table
    c.execute('''
    CREATE TABLE IF NOT EXISTS forecast_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enabled INTEGER NOT NULL DEFAULT 1,
        time_utc TEXT NOT NULL,
        countries TEXT NOT NULL,
        topics TEXT NOT NULL,
        time_horizon TEXT NOT NULL,
        depth TEXT NOT NULL,
        language TEXT NOT NULL,
        title TEXT
    )
    ''')
    
    # Schedule Runs table
    c.execute('''
    CREATE TABLE IF NOT EXISTS schedule_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        schedule_id INTEGER NOT NULL,
        run_date_utc TEXT NOT NULL,
        run_time_utc TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        status TEXT NOT NULL,
        error_text TEXT,
        response_hash TEXT,
        UNIQUE(schedule_id, run_date_utc, run_time_utc)
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

# --- Subscriber Methods ---

def add_subscriber(chat_id: int, user_id: Optional[int] = None) -> bool:
    """Returns True if new subscriber, False if already existed (reactivated)."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('SELECT id, active FROM subscribers WHERE chat_id = ?', (chat_id,))
        row = c.fetchone()
        
        if row:
            # Already exists
            if row[1] == 0:
                c.execute('UPDATE subscribers SET active = 1 WHERE id = ?', (row[0],))
                conn.commit()
                return True # Reactivated
            return False # Already active
        else:
            now = datetime.utcnow().isoformat()
            c.execute('INSERT INTO subscribers (chat_id, user_id, created_at, active) VALUES (?, ?, ?, 1)',
                      (chat_id, user_id, now))
            conn.commit()
            return True
    finally:
        conn.close()

def unsubscribe_user(chat_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE subscribers SET active = 0 WHERE chat_id = ?', (chat_id,))
    conn.commit()
    conn.close()

def deactivate_subscriber_by_id(sub_id: int):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE subscribers SET active = 0 WHERE id = ?', (sub_id,))
    conn.commit()
    conn.close()

def get_active_subscribers_chat_ids() -> List[int]:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT chat_id FROM subscribers WHERE active = 1')
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_subscriber_count() -> int:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM subscribers WHERE active = 1')
    res = c.fetchone()[0]
    conn.close()
    return res

def get_subscription_status(chat_id: int) -> bool:
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT active FROM subscribers WHERE chat_id = ?', (chat_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0] == 1:
        return True
    return False

# --- Schedule Methods ---

def get_all_schedules() -> List[Dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM forecast_schedules')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_enabled_schedules() -> List[Dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM forecast_schedules WHERE enabled = 1')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_schedule(time_utc, countries, topics, time_horizon, depth, language, title=None):
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        INSERT INTO forecast_schedules 
        (enabled, time_utc, countries, topics, time_horizon, depth, language, title)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
    ''', (time_utc, countries, topics, time_horizon, depth, language, title))
    conn.commit()
    new_id = c.lastrowid
    conn.close()
    return new_id

# --- Run History Methods ---

def should_run_schedule(schedule_id: int, date_utc: str, time_utc: str) -> bool:
    """
    Check if a successful or partial run already exists for this slot.
    Returns True if it SHOULD run (no completion record found).
    """
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        SELECT status FROM schedule_runs 
        WHERE schedule_id = ? AND run_date_utc = ? AND run_time_utc = ?
    ''', (schedule_id, date_utc, time_utc))
    row = c.fetchone()
    conn.close()
    
    if row:
        status = row[0]
        if status in ('success', 'partial'):
            return False
    return True

def start_run_record(schedule_id: int, date_utc: str, time_utc: str) -> Optional[int]:
    """
    Creates a 'running' or initial record if not exists.
    Returns record ID.
    If fails (unique constraint), probably means another process started it or it's done. 
    But since we check `should_run_schedule` first, this serves as a lock attempt.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        now = datetime.utcnow().isoformat()
        c.execute('''
            INSERT INTO schedule_runs (schedule_id, run_date_utc, run_time_utc, started_at, status)
            VALUES (?, ?, ?, ?, 'running')
        ''', (schedule_id, date_utc, time_utc, now))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        # Already exists
        return None
    finally:
        conn.close()

def update_run_result(run_id: int, status: str, error_text: str = None, response_hash: str = None):
    conn = get_connection()
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute('''
        UPDATE schedule_runs 
        SET finished_at = ?, status = ?, error_text = ?, response_hash = ?
        WHERE id = ?
    ''', (now, status, error_text, response_hash, run_id))
    conn.commit()
    conn.close()
