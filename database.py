import sqlite3
import datetime


def init_db():
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()

    # Create users table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            subscription_plan TEXT DEFAULT 'free',
            upload_count INTEGER DEFAULT 0,
            tag_count INTEGER DEFAULT 0,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """
    )

    # Create subscriptions table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            plan_name TEXT NOT NULL,
            start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_date TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """
    )

    # Modify files table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            file_extension TEXT,
            file_type TEXT,
            caption TEXT,
            tags TEXT,
            is_shared BOOLEAN DEFAULT 0,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """
    )
    conn.commit()
    conn.close()


def add_file(user_id, file_id, file_name, file_extension, file_type, caption, tags):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO files (user_id, file_id, file_name, file_extension, file_type, caption, tags) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            file_id,
            file_name,
            file_extension,
            file_type,
            caption,
            ",".join(tags),
        ),
    )
    conn.commit()
    conn.close()


def find_files(user_id, query):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()

    search_term = f"%{query}%"
    c.execute(
        "SELECT file_id FROM files WHERE user_id = ? AND (file_name LIKE ? OR file_extension LIKE ? OR tags LIKE ?)",
        (user_id, search_term, search_term, search_term),
    )

    files = c.fetchall()
    conn.close()
    return [file[0] for file in files]


def get_all_tags(user_id):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute("SELECT tags FROM files WHERE user_id = ?", (user_id,))
    tags_list = [row[0].split(",") for row in c.fetchall() if row[0]]
    conn.close()
    # Flatten list and get unique tags
    return sorted(list(set([tag for sublist in tags_list for tag in sublist])))


def get_recent_files(user_id, limit=10):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute(
        "SELECT file_id FROM files WHERE user_id = ? ORDER BY upload_date DESC LIMIT ?",
        (user_id, limit),
    )
    files = c.fetchall()
    conn.close()
    return [file[0] for file in files]


def delete_files(user_id, query):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    search_term = f"%{query}%"
    c.execute(
        "DELETE FROM files WHERE user_id = ? AND (file_name LIKE ? OR file_extension LIKE ? OR tags LIKE ?)",
        (user_id, search_term, search_term, search_term),
    )
    rows_deleted = c.rowcount
    conn.commit()
    conn.close()
    return rows_deleted


def get_user(user_id):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user


def add_user(user_id, username):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username),
    )
    conn.commit()
    conn.close()


def update_user_subscription(user_id, plan_name):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute(
        "UPDATE users SET subscription_plan = ? WHERE user_id = ?", (plan_name, user_id)
    )
    conn.commit()
    conn.close()


def record_upload(user_id):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute(
        "UPDATE users SET upload_count = upload_count + 1, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
        (user_id,),
    )
    conn.commit()
    conn.close()


def record_tag_usage(user_id, num_tags):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    c.execute(
        "UPDATE users SET tag_count = tag_count + ?, last_active = CURRENT_TIMESTAMP WHERE user_id = ?",
        (num_tags, user_id),
    )
    conn.commit()
    conn.close()
