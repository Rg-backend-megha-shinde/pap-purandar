import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

try:
    conn = psycopg2.connect(
        dbname='lmrs_new',
        user='postgres',
        password=os.environ.get('DB_PASSWORD'),
        host='127.0.0.1'
    )
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    tables = cur.fetchall()
    print('Existing tables:')
    for table in tables:
        print(f'  {table[0]}')
    conn.close()
except Exception as e:
    print(f'Error: {e}')
