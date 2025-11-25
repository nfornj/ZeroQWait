# Tier limits configuration for Nowait freemium model

TIER_LIMITS = {
    "free": {
        "max_queue_size": 50,  # Max customers in queue at once
        "max_shops": 1,  # Max 1 shop per owner
        "max_queues_per_shop": 1,  # One active queue per shop
        "features": ["Basic queue management", "Shared database", "Email support"],
    },
    "premium": {
        "max_queue_size": 200,
        "max_shops": 5,  # Up to 5 shops
        "max_queues_per_shop": 5,
        "features": [
            "Dedicated database (isolated data)",
            "Advanced analytics",
            "Priority support (24/7)",
            "Custom branding",
            "SMS notifications",
            "Automatic backups"
        ],
    },
}

def get_tier_limit(tier: str, limit_key: str):
    """Helper function to get a specific limit for a tier"""
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"]).get(limit_key)
