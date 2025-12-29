from backend.db import get_db_connection

def save_code_version(session_id, code, logs):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO code_versions (session_id, code, logs)
        VALUES (%s, %s, %s)
        """,
        (session_id, code, logs)
    )

    conn.commit()
    cur.close()
    conn.close()