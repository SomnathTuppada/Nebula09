import hashlib
from backend.db import get_db_connection

def log_error(session_id, message, root_cause):
    if not session_id or not message:
        return

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO error_logs (session_id, error_message, root_cause)
        VALUES (%s, %s, %s)
        """,
        (str(session_id), message, root_cause)  # ✅ CAST TO STRING
    )

    conn.commit()
    cur.close()
    conn.close()




def update_error_pattern(message, root_cause):
    if not message:
        return  # ✅ safety guard

    signature = f"{message}|{root_cause or ''}"
    pattern_hash = hashlib.sha256(signature.encode()).hexdigest()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO error_patterns (pattern_hash, error_message, root_cause)
        VALUES (%s, %s, %s)
        ON CONFLICT (pattern_hash)
        DO UPDATE SET
            occurrence_count = error_patterns.occurrence_count + 1,
            last_seen = NOW()
        """,
        (pattern_hash, message, root_cause)
    )

    conn.commit()
    cur.close()
    conn.close()

