from db_interface import db_interface
import random

print("Seeding Auto Shop...")

# Get owner
owner = db_interface.get_user_by_username("testowner")
if not owner:
    print("Owner not found, creating...")
    # (Assuming owner exists from previous seed, otherwise logic needed)
    exit(1)

shop_data = {
    "owner_id": owner["id"],
    "name": "Mike's Auto Repair",
    "description": "Expert diagnostics and repairs",
    "shop_type": "auto_repair",
    "address": "789 Motor Way",
    "city": "Detroit",
    "state": "Michigan",
    "zip_code": "48127",
    "country": "United States",
    "phone": "+1-313-555-0199",
    "email": "mike@autoshop.com",
    "website": "https://mikesauto.com",
    "average_service_time": 60,
    "slug": f"mikes-auto-{random.randint(100,999)}",
    "latitude": 43.6532,
    "longitude": -79.3832,
    "is_active": True
}

created_shop = db_interface.create_shop(shop_data)
print(f"Created: {created_shop['name']} (ID: {created_shop['id']})")

# Create Queue
db_interface.create_queue({
    "shop_id": created_shop["id"],
    "name": "Oil Change & Inspection",
    "is_active": True
})

print("Seed complete.")
