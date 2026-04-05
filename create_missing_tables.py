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
    
    # Create app_readyreckonerinfo table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_readyreckonerinfo (
        id bigserial PRIMARY KEY,
        district varchar(100) NOT NULL,
        taluka varchar(100) NOT NULL,
        village varchar(100) NOT NULL,
        year varchar(20) NOT NULL DEFAULT '2024-2025',
        assessment_type varchar(200) NOT NULL,
        unit varchar(50) NOT NULL,
        created_at timestamp with time zone NOT NULL,
        updated_at timestamp with time zone NOT NULL,
        user_id integer NOT NULL
    );
    """)
    
    # Create app_readyreckonerrate table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_readyreckonerrate (
        id bigserial PRIMARY KEY,
        assessment_range_min numeric(10, 2) NOT NULL,
        assessment_range_max numeric(10, 2) NOT NULL,
        rate numeric(15, 2) NOT NULL,
        rr_id bigint NOT NULL REFERENCES app_readyreckonerinfo(id) ON DELETE CASCADE
    );
    """)
    
    # Add foreign key constraint for user_id (if auth_user table exists)
    cur.execute("""
    ALTER TABLE app_readyreckonerinfo
    ADD CONSTRAINT app_readyreckonerinfo_user_id_fk 
    FOREIGN KEY (user_id) REFERENCES auth_user(id) ON DELETE CASCADE;
    """)
    
    conn.commit()
    print("Tables created successfully!")
    cur.close()
    conn.close()
except psycopg2.Error as e:
    if "already exists" in str(e):
        print(f"Table already exists: {e}")
    else:
        print(f"Error: {e}")
except Exception as e:
    print(f"Error: {e}")
