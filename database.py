import psycopg2
from config import DATABASE_URL

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    # In a production environment with Supabase, tables are typically created via migrations
    # or the Supabase UI. This function will primarily serve as a placeholder or for
    # initial setup if running locally against a fresh DB.
    # The SQL for table creation was already provided to the user.
    # We'll keep it minimal here, assuming tables exist.
    pass

def add_file(user_id, file_id, file_name, file_extension, file_type, telegram_file_category, caption, tags):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Insert file into files table
        cur.execute(
            """
            INSERT INTO files (user_id, file_id, file_name, file_extension, file_type, telegram_file_category, caption)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
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
            cur.execute(
                """
                INSERT INTO tags (tag_name) VALUES (%s)
                ON CONFLICT (tag_name) DO NOTHING
                """,
                (tag_name,)
            )
            cur.execute("SELECT tag_id FROM tags WHERE tag_name = %s", (tag_name,))
            tag_id = cur.fetchone()[0]
            
            # Link file and tag in file_tags table
            cur.execute(
                """
                INSERT INTO file_tags (file_id, tag_id) VALUES (%s, %s)
                ON CONFLICT (file_id, tag_id) DO NOTHING
                """,
                (file_id, tag_id)
            )

        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error adding file: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def find_files(user_id, query, limit=None, offset=0):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        search_term = f"%{query}%"
        sql_query = """
            SELECT DISTINCT f.file_id, f.file_name, f.file_type, f.telegram_file_category, f.upload_date, STRING_AGG(t.tag_name, ', ') AS tags
            FROM files f
            LEFT JOIN file_tags ft ON f.file_id = ft.file_id
            LEFT JOIN tags t ON ft.tag_id = t.tag_id
            WHERE f.user_id = %s AND (
                f.file_name ILIKE %s OR 
                f.file_extension ILIKE %s OR 
                t.tag_name ILIKE %s
            )
            GROUP BY f.file_id, f.file_name, f.file_type, f.telegram_file_category, f.upload_date
            ORDER BY f.upload_date DESC
            """
        params = [user_id, search_term, search_term, search_term]

        if limit is not None:
            sql_query += " LIMIT %s OFFSET %s"
            params.append(limit)
            params.append(offset)

        cur.execute(sql_query, tuple(params))
        files = cur.fetchall()
        return files
    except Exception as e:
        print(f"Error finding files: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def get_all_tags(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT t.tag_name
            FROM tags t
            JOIN file_tags ft ON t.tag_id = ft.tag_id
            JOIN files f ON ft.file_id = f.file_id
            WHERE f.user_id = %s
            """,
            (user_id,)
        )
        tags_list = [row[0] for row in cur.fetchall()]
        return sorted(list(set(tags_list)))
    except Exception as e:
        print(f"Error getting all tags: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def update_file_metadata(user_id, file_id, new_file_name=None, tags_to_modify=None, tag_operation=None):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        update_fields = []
        params = []

        if new_file_name is not None:
            update_fields.append("file_name = %s")
            params.append(new_file_name)
        
        if tags_to_modify is not None and tag_operation is not None:
            # Get current tags for the file
            cur.execute(
                """
                SELECT t.tag_name
                FROM tags t
                JOIN file_tags ft ON t.tag_id = ft.tag_id
                WHERE ft.file_id = %s
                """,
                (file_id,)
            )
            current_tags = set([row[0] for row in cur.fetchall()])

            updated_tags = set()
            if tag_operation == "set":
                updated_tags = set(tags_to_modify)
            elif tag_operation == "add":
                updated_tags = current_tags.union(set(tags_to_modify))
            elif tag_operation == "remove":
                updated_tags = current_tags.difference(set(tags_to_modify))
            else:
                return 0 # Invalid tag operation

            # Remove old tags not in updated_tags
            tags_to_remove = current_tags.difference(updated_tags)
            for tag_name in tags_to_remove:
                cur.execute("SELECT tag_id FROM tags WHERE tag_name = %s", (tag_name,))
                tag_id = cur.fetchone()[0]
                cur.execute("DELETE FROM file_tags WHERE file_id = %s AND tag_id = %s", (file_id, tag_id))

            # Add new tags not in current_tags
            tags_to_add = updated_tags.difference(current_tags)
            for tag_name in tags_to_add:
                cur.execute(
                    """
                    INSERT INTO tags (tag_name) VALUES (%s)
                    ON CONFLICT (tag_name) DO NOTHING
                    """,
                    (tag_name,)
                )
                cur.execute("SELECT tag_id FROM tags WHERE tag_name = %s", (tag_name,))
                tag_id = cur.fetchone()[0]
                cur.execute(
                    """
                    INSERT INTO file_tags (file_id, tag_id) VALUES (%s, %s)
                    ON CONFLICT (file_id, tag_id) DO NOTHING
                    """,
                    (file_id, tag_id)
                )

        if not update_fields and (tags_to_modify is None or tag_operation is None):
            return 0  # No fields to update

        if update_fields:
            sql = f"UPDATE files SET {', '.join(update_fields)} WHERE user_id = %s AND file_id = %s"
            params.append(user_id)
            params.append(file_id)
            cur.execute(sql, tuple(params))
            rows_updated = cur.rowcount
        else:
            rows_updated = 0 # No direct file fields updated, only tags

        conn.commit()
        return rows_updated
    except Exception as e:
        conn.rollback()
        print(f"Error updating file metadata: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def get_recent_files(user_id, limit=10, offset=0):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT DISTINCT f.file_id, f.file_name, f.file_type, f.telegram_file_category, f.upload_date, STRING_AGG(t.tag_name, ', ') AS tags
            FROM files f
            LEFT JOIN file_tags ft ON f.file_id = ft.file_id
            LEFT JOIN tags t ON ft.tag_id = t.tag_id
            WHERE f.user_id = %s
            GROUP BY f.file_id, f.file_name, f.file_type, f.telegram_file_category, f.upload_date
            ORDER BY f.upload_date DESC LIMIT %s OFFSET %s
            """,
            (user_id, limit, offset),
        )
        files = cur.fetchall()
        return files
    except Exception as e:
        print(f"Error getting recent files: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def delete_files(user_id, query):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        search_term = f"%{query}%"
        # Find file_ids to delete
        cur.execute(
            """
            SELECT DISTINCT f.file_id
            FROM files f
            LEFT JOIN file_tags ft ON f.file_id = ft.file_id
            LEFT JOIN tags t ON ft.tag_id = t.tag_id
            WHERE f.user_id = %s AND (
                f.file_name ILIKE %s OR 
                f.file_extension ILIKE %s OR 
                t.tag_name ILIKE %s
            )
            """,
            (user_id, search_term, search_term, search_term),
        )
        file_ids_to_delete = [row[0] for row in cur.fetchall()]

        rows_deleted = 0
        if file_ids_to_delete:
            # Delete from file_tags (ON DELETE CASCADE on files table will handle this if file_id is primary key)
            # However, since file_id is not the primary key of files table, we need to delete from file_tags explicitly
            # or ensure the foreign key constraint is set up correctly.
            # For now, explicit deletion from file_tags is safer.
            for file_id in file_ids_to_delete:
                cur.execute("DELETE FROM file_tags WHERE file_id = %s", (file_id,))
            
            # Delete from files
            placeholders = ', '.join(['%s' for _ in file_ids_to_delete])
            cur.execute(f"DELETE FROM files WHERE user_id = %s AND file_id IN ({placeholders})", (user_id, *file_ids_to_delete))
            rows_deleted = cur.rowcount

        conn.commit()
        return rows_deleted
    except Exception as e:
        conn.rollback()
        print(f"Error deleting files: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def get_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        return user
    except Exception as e:
        print(f"Error getting user: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def add_user(user_id, username):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO users (user_id, username) VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, username),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error adding user: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def update_user_subscription(user_id, plan_name):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET subscription_plan = %s WHERE user_id = %s", (plan_name, user_id)
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error updating user subscription: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def record_upload(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET upload_count = upload_count + 1, last_active = NOW() WHERE user_id = %s",
            (user_id,),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error recording upload: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def record_tag_usage(user_id, num_tags):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE users SET tag_count = tag_count + %s, last_active = NOW() WHERE user_id = %s",
            (num_tags, user_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error recording tag usage: {e}")
        raise
    finally:
        cur.close()
        conn.close()
