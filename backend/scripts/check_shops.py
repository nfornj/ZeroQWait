from db_interface import db_interface

print("Checking database for shops...")
shops = db_interface.search_shops()
print(f"Found {len(shops)} shops.")
for s in shops:
    print(f"- {s['name']} ({s['city']})")

if len(shops) == 0:
    print("Database is empty. Seeding needed.")
