import sqlite3

def main():
    db_path = 'instance/resume_screening.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables in database with description:")
    for table in tables:
        print(f"Table: {table}")
        cursor.execute(f"PRAGMA table_info({table});")
        columns = cursor.fetchall()
        for col in columns:
            # col format: (cid, name, type, notnull, dflt_value, pk)
            print(f"  Column: {col[1]}, Type: {col[2]}, NotNull: {col[3]}, Default: {col[4]}, PK: {col[5]}")
        print()

    # Display content of JobPosting table
    print("Content of JobPosting table:")
    cursor.execute("SELECT * FROM job_postings;")
    rows = cursor.fetchall()
    for row in rows:
        print(row)

    conn.close()

if __name__ == "__main__":
    main()
