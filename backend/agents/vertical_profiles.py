"""Shop-type adaptive prompt helpers.

Maps shop_type strings to domain-specific vocabulary, tone, and examples
so that agent responses feel natural for the business vertical.
"""

from typing import Dict


# ── Vertical Profiles ──────────────────────────────────────────────

_VERTICALS: Dict[str, Dict[str, str]] = {
    "barber": {
        "label": "Barbershop",
        "vocabulary": "clients, haircuts, fades, trims, grooming, chair",
        "tone": "casual, friendly, upbeat",
        "example_services": "classic cut, beard trim, hot towel shave, lineup",
    },
    "salon": {
        "label": "Hair Salon",
        "vocabulary": "clients, appointments, stylists, coloring, blowout, treatment",
        "tone": "warm, polished, welcoming",
        "example_services": "haircut & style, highlights, keratin treatment, balayage",
    },
    "clinic": {
        "label": "Medical Clinic",
        "vocabulary": "patients, appointments, doctors, consultations, check-up",
        "tone": "professional, reassuring, clear",
        "example_services": "general consultation, follow-up, lab work, specialist referral",
    },
    "dental": {
        "label": "Dental Practice",
        "vocabulary": "patients, appointments, dentists, hygienists, cleaning",
        "tone": "professional, calm, reassuring",
        "example_services": "dental cleaning, check-up, filling, whitening",
    },
    "auto": {
        "label": "Auto Shop",
        "vocabulary": "vehicles, jobs, mechanics, service bays, work orders",
        "tone": "straightforward, technical but approachable",
        "example_services": "oil change, tire rotation, brake inspection, diagnostics",
    },
    "spa": {
        "label": "Spa & Wellness",
        "vocabulary": "guests, bookings, therapists, treatments, wellness",
        "tone": "calm, luxurious, relaxing",
        "example_services": "Swedish massage, facial, body wrap, aromatherapy",
    },
    "restaurant": {
        "label": "Restaurant",
        "vocabulary": "guests, reservations, tables, waitlist, covers",
        "tone": "hospitable, warm, efficient",
        "example_services": "table for 2, reservation, takeout order, catering inquiry",
    },
    "fitness": {
        "label": "Fitness / Gym",
        "vocabulary": "members, sessions, trainers, classes, bookings",
        "tone": "energetic, motivating, supportive",
        "example_services": "personal training, group class, membership check-in, assessment",
    },
}

# Default for unknown verticals
_DEFAULT = {
    "label": "Service Business",
    "vocabulary": "customers, appointments, services, staff",
    "tone": "professional, helpful, concise",
    "example_services": "standard service, consultation, follow-up",
}


def get_vertical_profile(shop_type: str) -> Dict[str, str]:
    """Return the vertical profile for a given shop_type string."""
    if not shop_type:
        return _DEFAULT
    normalized = shop_type.strip().lower()
    # Try exact match first, then prefix match
    if normalized in _VERTICALS:
        return _VERTICALS[normalized]
    for key, profile in _VERTICALS.items():
        if key in normalized or normalized in key:
            return profile
    return _DEFAULT


def build_vertical_system_prompt(shop_type: str, agent_role: str = "receptionist") -> str:
    """Build a system-prompt snippet that adapts agent behaviour to the vertical.

    Args:
        shop_type: The shop's type string (e.g. "barber", "clinic").
        agent_role: Which agent is asking — affects the framing.
    """
    profile = get_vertical_profile(shop_type)
    return (
        f"This business is a {profile['label']}.\n"
        f"Use vocabulary natural to this industry: {profile['vocabulary']}.\n"
        f"Tone: {profile['tone']}.\n"
        f"Typical services include: {profile['example_services']}.\n"
        f"Adapt your language accordingly — avoid generic phrasing when domain terms exist."
    )
