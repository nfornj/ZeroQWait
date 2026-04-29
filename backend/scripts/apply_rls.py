
from sqlalchemy import create_engine, text
from backend.database import DATABASE_URL
import os

def apply_rls():
    engine = create_engine(DATABASE_URL)
    sql_file_path = os.path.join(os.getcwd(), 'backend/sql/enable_rls.sql')
    
    with open(sql_file_path, 'r') as f:
        sql_commands = f.read()

    # Split by semicolon to execute individually if needed, but for policies creating, a block might be better.
    # sqlalchemy execute can handle multiple statements if supported by the driver, but psycopg2 usually prefers one by one or a block.
    # However, enable_rls.sql has comments and newlines.
    
    with engine.connect() as connection:
        trans = connection.begin()
        try:
            # We can execute the whole block
            connection.execute(text(sql_commands))
            trans.commit()
            print("RLS policies applied successfully.")
        except Exception as e:
            trans.rollback()
            print(f"Error applying RLS: {e}")

if __name__ == "__main__":
    apply_rls()
