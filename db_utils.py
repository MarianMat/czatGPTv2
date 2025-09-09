import sqlite3
from datetime import datetime
from pathlib import Path

DB_FILE = Path("conversations.db")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Tabela rozmów
    c.execute("""
    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        personality TEXT,
        model TEXT,
        memory_mode TEXT,
        session_cost_usd REAL DEFAULT 0,
        language TEXT,
        first_prompt TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    # Tabela wiadomości
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER,
        role TEXT,
        content TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(conversation_id) REFERENCES conversations(id)
    )
    """)
    conn.commit()
    return conn

def create_conversation(name, personality, model, memory_mode, language):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO conversations (name, personality, model, memory_mode, language)
        VALUES (?, ?, ?, ?, ?)
    """, (name, personality, model, memory_mode, language))
    conn.commit()
    return c.lastrowid  # conversation_id

def list_conversations():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, name FROM conversations ORDER BY id DESC")
    return c.fetchall()

def get_conversation(convo_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM conversations WHERE id=?", (convo_id,))
    return c.fetchone()

def save_message(convo_id, role, content):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
              (convo_id, role, content))
    conn.commit()
    return c.lastrowid

def get_messages(convo_id, limit=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    query = "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY timestamp"
    if limit:
        query += f" LIMIT {limit}"
    c.execute(query, (convo_id,))
    return [{"role": r, "content": c} for r, c in c.fetchall()]
