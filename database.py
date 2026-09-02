import sqlite3

DB_PATH = "dgca_dashboard.db"


def create_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS aviation_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            airline_name TEXT NOT NULL,
            passengers_carried INTEGER,
            yoy_growth_passengers REAL,
            plf_percent REAL,
            yoy_growth_plf REAL,
            year_period TEXT NOT NULL,
            UNIQUE(airline_name, year_period)
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database schema created:", DB_PATH)


if __name__ == "__main__":
    create_database()
