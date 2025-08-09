import logging
import psycopg2
from psycopg2 import pool, extras
from config import DATABASE_URL

db_pool = None
logger = logging.getLogger(__name__)

def init_db():
    global db_pool
    if db_pool is None:
        try:
            db_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL
            )
            logger.info("Database connection pool initialized.")
        except Exception as e:
            logger.exception("Error initializing connection pool")
            db_pool = None

def get_db_connection():
    global db_pool
    if db_pool is None:
        # Try to initialize on-demand; if still unavailable, return None
        init_db()
        if db_pool is None:
            return None
    try:
        return db_pool.getconn()
    except Exception:
        logger.exception("Failed to get DB connection from pool")
        return None

def put_db_connection(conn):
    if db_pool is not None and conn is not None:
        try:
            db_pool.putconn(conn)
        except Exception:
            logger.exception("Failed to return DB connection to pool")
    # No raise; be resilient

def add_file(user_id, file_id, file_name, file_extension, file_type, telegram_file_category, caption, tags):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("add_file skipped: DB unavailable")
            return
        cur = conn.cursor()
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
        
        tag_data = []
        file_tag_data = []
        for tag_name in tags:
            cur.execute(
                """
                INSERT INTO tags (tag_name) VALUES (%s)
                ON CONFLICT (tag_name) DO NOTHING
                RETURNING tag_id
                """,
                (tag_name,)
            )
            tag_id = cur.fetchone()
            if tag_id:
                tag_id = tag_id[0]
            else:
                cur.execute("SELECT tag_id FROM tags WHERE tag_name = %s", (tag_name,))
                tag_id = cur.fetchone()[0]
            file_tag_data.append((file_id, tag_id))

        if file_tag_data:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO file_tags (file_id, tag_id) VALUES %s
                ON CONFLICT (file_id, tag_id) DO NOTHING
                """,
                file_tag_data
            )

        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Error adding file")
        # swallow
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def find_files(user_id, query, limit=None, offset=0):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("find_files: DB unavailable")
            return []
        cur = conn.cursor()
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
    except Exception:
        logger.exception("Error finding files")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def get_all_tags(user_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("get_all_tags: DB unavailable")
            return []
        cur = conn.cursor()
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
    except Exception:
        logger.exception("Error getting all tags")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def update_file_metadata(user_id, file_id, new_file_name=None, tags_to_modify=None, tag_operation=None):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("update_file_metadata: DB unavailable")
            return 0
        cur = conn.cursor()
        update_fields = []
        params = []

        if new_file_name is not None:
            update_fields.append("file_name = %s")
            params.append(new_file_name)
        
        if tags_to_modify is not None and tag_operation is not None:
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
                return 0

            tags_to_remove = current_tags.difference(updated_tags)
            if tags_to_remove:
                cur.execute("SELECT tag_id FROM tags WHERE tag_name IN %s", (tuple(tags_to_remove),))
                tag_ids_to_remove = [row[0] for row in cur.fetchall()]
                if tag_ids_to_remove:
                    psycopg2.extras.execute_values(
                        cur,
                        "DELETE FROM file_tags WHERE file_id = %s AND tag_id = %s",
                        [(file_id, tag_id) for tag_id in tag_ids_to_remove]
                    )

            tags_to_add = updated_tags.difference(current_tags)
            if tags_to_add:
                psycopg2.extras.execute_values(
                    cur,
                    "INSERT INTO tags (tag_name) VALUES %s ON CONFLICT (tag_name) DO NOTHING RETURNING tag_id, tag_name",
                    [(tag_name,) for tag_name in tags_to_add]
                )
                cur.execute("SELECT tag_id, tag_name FROM tags WHERE tag_name IN %s", (tuple(tags_to_add),))
                tag_id_map = {row[1]: row[0] for row in cur.fetchall()}

                file_tag_data = []
                for tag_name in tags_to_add:
                    if tag_name in tag_id_map:
                        file_tag_data.append((file_id, tag_id_map[tag_name]))
                
                if file_tag_data:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO file_tags (file_id, tag_id) VALUES %s
                        ON CONFLICT (file_id, tag_id) DO NOTHING
                        """,
                        file_tag_data
                    )

        if not update_fields and (tags_to_modify is None or tag_operation is None):
            return 0

        if update_fields:
            sql = f"UPDATE files SET {', '.join(update_fields)} WHERE user_id = %s AND file_id = %s"
            params.append(user_id)
            params.append(file_id)
            cur.execute(sql, tuple(params))
            rows_updated = cur.rowcount
        else:
            rows_updated = 0

        new_tag_count = _get_user_unique_tag_count(user_id)
        cur.execute("UPDATE users SET tag_count = %s WHERE user_id = %s", (new_tag_count, user_id))

        conn.commit()
        return rows_updated
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Error updating file metadata")
        return 0
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def get_recent_files(user_id, limit=10, offset=0):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("get_recent_files: DB unavailable")
            return []
        cur = conn.cursor()
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
    except Exception:
        logger.exception("Error getting recent files")
        return []
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def delete_files(user_id, query):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("delete_files: DB unavailable")
            return 0
        cur = conn.cursor()
        search_term = f"%{query}%"
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
            cur.execute("DELETE FROM file_tags WHERE file_id IN %s", (tuple(file_ids_to_delete),))
            
            cur.execute("DELETE FROM files WHERE user_id = %s AND file_id IN %s", (user_id, tuple(file_ids_to_delete)))
            rows_deleted = cur.rowcount

        new_file_count = _get_user_file_count(user_id)
        cur.execute("UPDATE users SET upload_count = %s WHERE user_id = %s", (new_file_count, user_id))
        
        new_tag_count = _get_user_unique_tag_count(user_id)
        cur.execute("UPDATE users SET tag_count = %s WHERE user_id = %s", (new_tag_count, user_id))

        conn.commit()
        return rows_deleted
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Error deleting files")
        return 0
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def get_user(user_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("get_user: DB unavailable")
            return None
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        return user
    except Exception:
        logger.exception("Error getting user")
        return None
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def add_user(user_id, username):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("add_user skipped: DB unavailable")
            return
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO users (user_id, username) VALUES (%s, %s)
            ON CONFLICT (user_id) DO NOTHING
            """,
            (user_id, username),
        )
        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Error adding user")
        # swallow
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def update_user_subscription(user_id, plan_name):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("update_user_subscription skipped: DB unavailable")
            return
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET subscription_plan = %s WHERE user_id = %s", (plan_name, user_id)
        )
        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Error updating user subscription")
        # swallow
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def record_upload(user_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("record_upload skipped: DB unavailable")
            return
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET upload_count = upload_count + 1, last_active = NOW() WHERE user_id = %s",
            (user_id,),
        )
        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Error recording upload")
        # swallow
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)


def record_tag_usage(user_id, num_tags):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        if conn is None:
            logger.error("record_tag_usage skipped: DB unavailable")
            return
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET tag_count = tag_count + %s, last_active = NOW() WHERE user_id = %s",
            (num_tags, user_id),
        )
        conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("Error recording tag usage")
        # swallow
    finally:
        if cur:
            cur.close()
        if conn:
            put_db_connection(conn)

def _get_user_file_count(user_id):
    conn = get_db_connection()
    if conn is None:
        logger.error("_get_user_file_count: DB unavailable")
        return 0
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM files WHERE user_id = %s", (user_id,))
        count = cur.fetchone()[0]
        return count
    except Exception:
        logger.exception("Error getting user file count")
        return 0
    finally:
        try:
            cur.close()
        except Exception:
            pass
        put_db_connection(conn)

def _get_user_unique_tag_count(user_id):
    conn = get_db_connection()
    if conn is None:
        logger.error("_get_user_unique_tag_count: DB unavailable")
        return 0
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT COUNT(DISTINCT t.tag_id)
            FROM tags t
            JOIN file_tags ft ON t.tag_id = ft.tag_id
            JOIN files f ON ft.file_id = f.file_id
            WHERE f.user_id = %s
            """,
            (user_id,)
        )
        count = cur.fetchone()[0]
        return count
    except Exception:
        logger.exception("Error getting user unique tag count")
        return 0
    finally:
        try:
            cur.close()
        except Exception:
            pass
        put_db_connection(conn)
