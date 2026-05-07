"""Migration runner.

Usage:
    python scripts/migrate.py            # apply any unapplied migrations
    python scripts/migrate.py drop_legacy  # drop pre-refactor tables
"""
# Python imports
import os
import sys

# Local imports
from apis.utils.db_utils import make_connection

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")


def applied_migrations(cursor):
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'schema_migrations'
        )
    """)
    if not cursor.fetchone()[0]:
        return set()
    cursor.execute("SELECT filename FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}


def apply_migrations():
    files = sorted(f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql"))
    with make_connection() as conn:
        with conn.cursor() as cur:
            applied = applied_migrations(cur)
            for filename in files:
                if filename in applied:
                    print(f"skip  {filename} (already applied)")
                    continue
                path = os.path.join(MIGRATIONS_DIR, filename)
                with open(path) as f:
                    sql = f.read()
                print(f"apply {filename}")
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (%s)",
                    (filename,),
                )
            conn.commit()


def drop_legacy():
    confirm = input(
        "This will DROP common_cards, common_decks, recent_battles. "
        "Type 'drop' to confirm: "
    )
    if confirm != "drop":
        print("aborted")
        return
    with make_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS common_cards")
            cur.execute("DROP TABLE IF EXISTS common_decks")
            cur.execute("DROP TABLE IF EXISTS recent_battles")
            conn.commit()
    print("legacy tables dropped")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "drop_legacy":
        drop_legacy()
    else:
        apply_migrations()
