from modules.shops.schemas import ShopServiceCreate, ShopServiceUpdate
from routers import services as services_router


class FakeDbInterface:
    def __init__(self):
        self.created_payload = None
        self.updated_payload = None

    def create_shop_service(self, service_data):
        self.created_payload = service_data
        return {
            "id": 11,
            "created_at": None,
            **service_data,
        }

    def get_shop_services(self, shop_id, include_inactive=False):
        return [
            {
                "id": 11,
                "shop_id": shop_id,
                "name": "RMT Massage",
                "description": "Therapeutic session",
                "duration_minutes": 60,
                "cost": 100.0,
                "currency": "USD",
                "catalog_section": "popular",
                "is_active": True,
                "created_at": None,
            },
            {
                "id": 12,
                "shop_id": shop_id,
                "name": "Deep Tissue Massage",
                "description": "Targeted pressure",
                "duration_minutes": 75,
                "cost": 120.0,
                "currency": "USD",
                "catalog_section": "specialized",
                "is_active": True,
                "created_at": None,
            },
        ]

    def update_shop_service(self, shop_id, service_id, updates):
        self.updated_payload = updates
        return {
            "id": service_id,
            "shop_id": shop_id,
            "name": updates.get("name", "RMT Massage"),
            "description": updates.get("description", "Therapeutic session"),
            "duration_minutes": updates.get("duration_minutes", 60),
            "cost": updates.get("cost", 100.0),
            "currency": updates.get("currency", "USD"),
            "catalog_section": updates.get("catalog_section", "popular"),
            "is_active": updates.get("is_active", True),
            "created_at": None,
        }


class FakeRedisClient:
    def tenant_delete(self, *_args, **_kwargs):
        return None

    def set_services_cache(self, *_args, **_kwargs):
        return None


def test_service_catalog_section_flows_through_create_list_and_update(monkeypatch):
    fake_db = FakeDbInterface()
    monkeypatch.setattr(services_router, "db_interface", fake_db)
    monkeypatch.setattr(services_router, "redis_client", FakeRedisClient())
    monkeypatch.setattr(services_router, "check_shop_access", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(services_router, "sync_service_to_odoo", lambda *_args, **_kwargs: None)

    current_user = {"id": 1, "role": "shop_owner"}
    created = services_router.create_service(
        7,
        ShopServiceCreate(
            name="Acupuncture",
            description="Focused treatment",
            duration_minutes=50,
            cost=85.0,
            catalog_section="specialized",
        ),
        current_user=current_user,
    )

    assert created["catalog_section"] == "specialized"
    assert fake_db.created_payload["catalog_section"] == "specialized"

    services = services_router.list_services(7)
    assert [service["catalog_section"] for service in services] == ["popular", "specialized"]

    updated = services_router.update_service(
        7,
        11,
        ShopServiceUpdate(catalog_section="popular"),
        current_user=current_user,
    )

    assert updated["catalog_section"] == "popular"
    assert fake_db.updated_payload == {"catalog_section": "popular"}
