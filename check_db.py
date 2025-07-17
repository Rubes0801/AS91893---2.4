import sqlite3

def check_db():
    try:
        conn = sqlite3.connect('NZ_Wildlife.db')
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("SELECT * FROM sqlite_master WHERE type='table' AND name='species'")
        table_info = cursor.fetchone()
        print("Table structure:", table_info)
        
        # Get sample data
        cursor.execute("SELECT * FROM species LIMIT 1")
        columns = [description[0] for description in cursor.description]
        print("\nColumns:", columns)
        
        row = cursor.fetchone()
        print("\nSample row:", row)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    check_db()
