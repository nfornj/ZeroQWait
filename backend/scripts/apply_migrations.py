import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine
from models import Base

def apply_migrations():
    print("Applying database migrations...")
    Base.metadata.create_all(bind=engine)
    print("Migrations applied successfully.")

if __name__ == "__main__":
    apply_migrations()
