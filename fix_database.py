"""
fix_database.py

Ye script aapki EXISTING sqlite database ko naye Payment model ke
mutabiq theek karta hai, BINA kisi data ko delete kiye.

Kya problem hai?
-----------------
Aapki 'payments' table purane model se bani thi, jisme 'quotation_id'
column NOT NULL tha. Aapne model.py mein Payment class update kar di
(ab 'project_id' use hota hai), lekin database table khud update
nahi hoti jab tak aap migration ya manual fix na karein.

Ye script kya karega?
----------------------
1. Purani 'payments' table ka poora data padhega.
2. Naye structure (project_id based) ke mutabiq NAYI 'payments' table
   banayega.
3. Purana data (jahan project_id already maujood hai) naye table mein
   copy kar dega.
4. Purani table delete karke naye table ka naam 'payments' rakh dega.

Use kaise karein
-----------------
1. Apni Flask app ka path neeche 'from app import create_app, db' mein
   confirm kar lein (agar create_app ka naam different hai to badal dein).
2. Terminal mein project root se ye chalayein:

       python fix_database.py

3. Agar sab theek raha to "Database fixed successfully!" print hoga.

IMPORTANT: Chalane se pehle apni .db file ka backup zaroor bana lein!
"""

import shutil
import os
from datetime import datetime

from app import create_app, db  # <-- agar aapka create_app function
                                 #     kisi aur naam/jagah par hai to
                                 #     yahan path/naam badal dein


def backup_database():
    """instance folder mein jo bhi .db file mile uska backup bana dega."""
    instance_dir = os.path.join(os.getcwd(), 'instance')
    if not os.path.isdir(instance_dir):
        print("instance/ folder nahi mila, backup skip kar raha hun.")
        return

    for fname in os.listdir(instance_dir):
        if fname.endswith('.db'):
            src = os.path.join(instance_dir, fname)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            dst = os.path.join(instance_dir, f'{fname}.backup_{timestamp}')
            shutil.copy2(src, dst)
            print(f"Backup ban gaya: {dst}")


def fix_payments_table():
    app = create_app()

    with app.app_context():
        conn = db.engine.raw_connection()
        cursor = conn.cursor()

        # Check karein ke payments table maujood hai ya nahi
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payments'"
        )
        if not cursor.fetchone():
            print("'payments' table maujood nahi hai — kuch fix karne ki zarurat nahi.")
            conn.close()
            return

        # Purani table ke columns dekhein
        cursor.execute("PRAGMA table_info(payments)")
        columns = [row[1] for row in cursor.fetchall()]
        print("Purani 'payments' table ke columns:", columns)

        if 'quotation_id' not in columns:
            print("'quotation_id' column already nahi hai — database already theek hai.")
            conn.close()
            return

        if 'project_id' not in columns:
            print(
                "WARNING: 'project_id' column bhi nahi mila. "
                "Isका matlab table bilkul purani state mein hai. "
                "Ye script sirf 'quotation_id' hatane ke liye hai jab "
                "'project_id' pehle se maujood ho. Manually check kar lein."
            )
            conn.close()
            return

        print("Purani table ko naye structure mein migrate kar raha hun...")

        # 1. Naye structure ki temporary table banayein
        cursor.execute("""
            CREATE TABLE payments_new (
                id INTEGER NOT NULL PRIMARY KEY,
                project_id INTEGER NOT NULL,
                milestone_name VARCHAR(50) NOT NULL,
                amount FLOAT NOT NULL,
                payment_method VARCHAR(50),
                receipt_file VARCHAR(255),
                status VARCHAR(50),
                created_at DATETIME,
                FOREIGN KEY(project_id) REFERENCES projects (id)
            )
        """)

        # 2. Sirf wo rows copy karein jinme project_id already set hai
        #    (purani rows jinme sirf quotation_id tha aur project_id NULL
        #    hai, unhe copy nahi kiya ja sakta kyunke naya schema unhe
        #    accept nahi karega — aise records agar hain to unko manually
        #    dekhna hoga).
        cursor.execute("""
            INSERT INTO payments_new
                (id, project_id, milestone_name, amount, payment_method,
                 receipt_file, status, created_at)
            SELECT
                id, project_id, milestone_name, amount, payment_method,
                receipt_file, status, created_at
            FROM payments
            WHERE project_id IS NOT NULL
        """)

        skipped = cursor.execute(
            "SELECT COUNT(*) FROM payments WHERE project_id IS NULL"
        ).fetchone()[0]

        # 3. Purani table hata kar naye table ka naam badlein
        cursor.execute("DROP TABLE payments")
        cursor.execute("ALTER TABLE payments_new RENAME TO payments")

        conn.commit()
        conn.close()

        print("Database fixed successfully!")
        if skipped:
            print(
                f"NOTE: {skipped} purane record(s) skip ho gaye kyunke "
                "unme project_id NULL tha (sirf quotation_id set tha). "
                "Agar wo records zaroori hain to unhe manually migrate karna hoga."
            )


if __name__ == '__main__':
    backup_database()
    fix_payments_table()
