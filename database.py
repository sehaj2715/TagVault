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

    # Create files table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            file_extension TEXT,
            file_type TEXT,
            telegram_file_category TEXT,
            caption TEXT,
            is_shared BOOLEAN DEFAULT 0,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    """
    )

    # Create tags table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT NOT NULL UNIQUE
        )
    """
    )

    # Create file_tags junction table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS file_tags (
            file_id TEXT NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (file_id, tag_id),
            FOREIGN KEY (file_id) REFERENCES files (file_id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags (tag_id) ON DELETE CASCADE
        )
    """
    )
    conn.commit()
    conn.close()


def add_file(user_id, file_id, file_name, file_extension, file_type, telegram_file_category, caption, tags):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    
    # Insert file into files table
    c.execute(
        "INSERT INTO files (user_id, file_id, file_name, file_extension, file_type, telegram_file_category, caption) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user_id,
            file_id,
            file_name,
            file_extension,
            file_type,
            telegram_file_category,
            caption,
        ),
    )
    
    # Handle tags
    for tag_name in tags:
        # Insert tag into tags table if it doesn't exist, and get its ID
        c.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (tag_name,))
        c.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag_name,))
        tag_id = c.fetchone()[0]
        
        # Link file and tag in file_tags table
        c.execute("INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)", (file_id, tag_id))

    conn.commit()
    conn.close()


def find_files(user_id, query, limit=None, offset=0):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()

    search_term = f"%{query}%"
    sql_query = """
        SELECT DISTINCT f.file_id, f.file_name, f.file_type, f.telegram_file_category, GROUP_CONCAT(t.tag_name) AS tags
        FROM files f
        LEFT JOIN file_tags ft ON f.file_id = ft.file_id
        LEFT JOIN tags t ON ft.tag_id = t.tag_id
        WHERE f.user_id = ? AND (
            f.file_name LIKE ? OR 
            f.file_extension LIKE ? OR 
            t.tag_name LIKE ?
        )
        GROUP BY f.file_id, f.file_name, f.file_type, f.telegram_file_category
        ORDER BY f.upload_date DESC
        """
    params = [user_id, search_term, search_term, search_term]

    if limit is not None:
        sql_query += " LIMIT ? OFFSET ?"
        params.append(limit)
        params.append(offset)

    c.execute(sql_query, tuple(params))

    files = c.fetchall()
    conn.close()
    return files


def get_all_tags(user_id):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    # Modified to select tags from the new tags table, linked via file_tags
    c.execute(
        """
        SELECT DISTINCT t.tag_name
        FROM tags t
        JOIN file_tags ft ON t.tag_id = ft.tag_id
        JOIN files f ON ft.file_id = f.file_id
        WHERE f.user_id = ?
        """,
        (user_id,)
    )
    tags_list = [row[0] for row in c.fetchall()]
    conn.close()
    return sorted(list(set(tags_list)))


def update_file_metadata(user_id, file_id, new_file_name=None, tags_to_modify=None, tag_operation=None):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    update_fields = []
    params = []

    if new_file_name is not None:
        update_fields.append("file_name = ?")
        params.append(new_file_name)
    
    if tags_to_modify is not None and tag_operation is not None:
        # Get current tags for the file
        c.execute(
            """
            SELECT t.tag_name
            FROM tags t
            JOIN file_tags ft ON t.tag_id = ft.tag_id
            WHERE ft.file_id = ?
            """,
            (file_id,)
        )
        current_tags = set([row[0] for row in c.fetchall()])

        updated_tags = set()
        if tag_operation == "set":
            updated_tags = set(tags_to_modify)
        elif tag_operation == "add":
            updated_tags = current_tags.union(set(tags_to_modify))
        elif tag_operation == "remove":
            updated_tags = current_tags.difference(set(tags_to_modify))
        else:
            conn.close()
            return 0 # Invalid tag operation

        # Remove old tags not in updated_tags
        tags_to_remove = current_tags.difference(updated_tags)
        for tag_name in tags_to_remove:
            c.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag_name,))
            tag_id = c.fetchone()[0]
            c.execute("DELETE FROM file_tags WHERE file_id = ? AND tag_id = ?", (file_id, tag_id))

        # Add new tags not in current_tags
        tags_to_add = updated_tags.difference(current_tags)
        for tag_name in tags_to_add:
            c.execute("INSERT OR IGNORE INTO tags (tag_name) VALUES (?)", (tag_name,))
            c.execute("SELECT tag_id FROM tags WHERE tag_name = ?", (tag_name,))
            tag_id = c.fetchone()[0]
            c.execute("INSERT INTO file_tags (file_id, tag_id) VALUES (?, ?)", (file_id, tag_id))

    if not update_fields and (tags_to_modify is None or tag_operation is None): # Only return 0 if no actual updates were requested
        conn.close()
        return 0  # No fields to update

    sql = f"UPDATE files SET {", ".join(update_fields)} WHERE user_id = ? AND file_id = ?"
    params.append(user_id)
    params.append(file_id)

    c.execute(sql, tuple(params))
    rows_updated = c.rowcount
    conn.commit()
    conn.close()
    return rows_updated


def get_recent_files(user_id, limit=10, offset=0):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    # Modified to join with file_tags and tags tables
    c.execute(
        """
        SELECT DISTINCT f.file_id, f.file_name, f.file_type, f.telegram_file_category, GROUP_CONCAT(t.tag_name) AS tags
        FROM files f
        LEFT JOIN file_tags ft ON f.file_id = ft.file_id
        LEFT JOIN tags t ON ft.tag_id = t.tag_id
        WHERE f.user_id = ?
        GROUP BY f.file_id, f.file_name, f.file_type, f.telegram_file_category
        ORDER BY f.upload_date DESC LIMIT ? OFFSET ?
        """,
        (user_id, limit, offset),
    )
    files = c.fetchall()
    conn.close()
    return files


def delete_files(user_id, query):
    conn = sqlite3.connect("backup.db")
    c = conn.cursor()
    search_term = f"%{query}%"
    # Need to delete from file_tags first due to foreign key constraints
    # Find file_ids to delete
    c.execute(
        """
        SELECT DISTINCT f.file_id
        FROM files f
        LEFT JOIN file_tags ft ON f.file_id = ft.file_id
        LEFT JOIN tags t ON ft.tag_id = t.tag_id
        WHERE f.user_id = ? AND (
            f.file_name LIKE ? OR 
            f.file_extension LIKE ? OR 
            t.tag_name LIKE ?
        )
        """,
        (user_id, search_term, search_term, search_term),
    )
    file_ids_to_delete = [row[0] for row in c.fetchall()]

    rows_deleted = 0
    if file_ids_to_delete:
        # Delete from file_tags
        for file_id in file_ids_to_delete:
            c.execute("DELETE FROM file_tags WHERE file_id = ?", (file_id,))
        
        # Delete from files
        placeholders = ', '.join(['?' for _ in file_ids_to_delete])
        c.execute(f"DELETE FROM files WHERE user_id = ? AND file_id IN ({placeholders})", (user_id, *file_ids_to_delete))
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