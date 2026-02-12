import os
import pymysql

# ⚠️ Mets ces infos soit en dur, soit via variables d'environnement
HOST = "centerbeam.proxy.rlwy.net"
PORT = 28845
USER = "root"
PASSWORD = "fALANSNDvFtxfgiIWloAyFzYhRcAwhnd"
DBNAME = "railway"

TABLE = "test_results"  # change si ta table s'appelle autrement


def column_exists(cursor, table, column):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME=%s
        """,
        (DBNAME, table, column),
    )
    return cursor.fetchone()[0] > 0


def main():
    conn = pymysql.connect(
        host=HOST,
        port=PORT,
        user=USER,
        password=PASSWORD,
        database=DBNAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.Cursor,
        autocommit=True,
    )

    try:
        with conn.cursor() as cur:
            # Vérifie que la table existe
            cur.execute("SHOW TABLES;")
            tables = [row[0] for row in cur.fetchall()]
            if TABLE not in tables:
                raise SystemExit(f"Table '{TABLE}' introuvable. Tables dispo: {tables}")

            # Ajoute wall_test_g si absent
            if not column_exists(cur, TABLE, "wall_test_g"):
                print("Ajout colonne wall_test_g...")
                cur.execute(
                    f"ALTER TABLE `{TABLE}` ADD COLUMN `wall_test_g` FLOAT NULL;"
                )
            else:
                print("Colonne wall_test_g déjà présente.")

            # Ajoute wall_test_d si absent
            if not column_exists(cur, TABLE, "wall_test_d"):
                print("Ajout colonne wall_test_d...")
                cur.execute(
                    f"ALTER TABLE `{TABLE}` ADD COLUMN `wall_test_d` FLOAT NULL;"
                )
            else:
                print("Colonne wall_test_d déjà présente.")

            # Optionnel : si tu as une ancienne colonne wall_test, copier vers G/D
            if column_exists(cur, TABLE, "wall_test"):
                print("Copie wall_test -> wall_test_g/d (si valeurs manquantes)...")
                cur.execute(
                    f"""
                    UPDATE `{TABLE}`
                    SET wall_test_g = wall_test,
                        wall_test_d = wall_test
                    WHERE wall_test IS NOT NULL
                      AND (wall_test_g IS NULL AND wall_test_d IS NULL);
                    """
                )

            print("✅ Migration terminée.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
