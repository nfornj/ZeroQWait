"""
Registration Agent — Interactive step-by-step registration state machine.

Manages a multi-step registration flow via Redis-backed session state.
Each step returns a form schema that the frontend renders inline in the chat.
Validation is performed server-side at each step before advancing.

Steps (shop_owner flow):
  account_type → email → username → password → shop_name → shop_type → shop_address → confirm → done

Steps (customer flow):
  account_type → email → username → password → confirm → done
"""

import os
import re
import json
import logging
import secrets
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

from redis_client import redis_client
from database import SessionLocal
from shared.auth_utils import get_password_hash

logger = logging.getLogger("registration_agent")

# --- Step Definitions ---

SHOP_OWNER_STEPS = [
    "account_type", "email", "username", "password",
    "shop_name", "shop_type", "shop_address", "confirm"
]
CUSTOMER_STEPS = [
    "account_type", "email", "username", "password", "confirm"
]

SHOP_TYPE_OPTIONS = [
    "Barber Shop", "Hair Salon", "Nail Salon", "Spa & Wellness",
    "Lawn Care", "Landscaping", "Music Lessons",
    "Medical Clinic", "Dental Office", "Veterinary Clinic",
    "Auto Repair", "Tire Shop", "Restaurant / Café",
    "Government Office", "Bank / Finance", "Pharmacy", "Other"
]

# Form schema for each step — drives frontend rendering
STEP_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "account_type": {
        "message": "Are you registering as a **shop owner** or a **customer**?",
        "fields": [{
            "name": "account_type",
            "type": "choice",
            "label": "Account Type",
            "options": [
                {"value": "shop_owner", "label": "Shop Owner", "icon": "store", "description": "List your business and manage queues"},
                {"value": "customer", "label": "Customer", "icon": "person", "description": "Join queues and track wait times"}
            ],
            "required": True
        }]
    },
    "email": {
        "message": "What's your **email address**? We'll use this for your account.",
        "fields": [{
            "name": "email",
            "type": "email",
            "label": "Email Address",
            "placeholder": "you@example.com",
            "required": True,
            "validate_async": "/api/agent/registration/validate/email"
        }]
    },
    "username": {
        "message": "Choose a **username** for your account.",
        "fields": [{
            "name": "username",
            "type": "text",
            "label": "Username",
            "placeholder": "cooluser42",
            "required": True,
            "min_length": 3,
            "max_length": 30,
            "validate_async": "/api/agent/registration/validate/username"
        }]
    },
    "password": {
        "message": "Create a **password** (at least 8 characters).",
        "fields": [{
            "name": "password",
            "type": "password",
            "label": "Password",
            "placeholder": "••••••••",
            "required": True,
            "min_length": 8,
            "show_strength": True
        }]
    },
    "shop_name": {
        "message": "What's the **name** of your shop?",
        "fields": [{
            "name": "shop_name",
            "type": "text",
            "label": "Shop Name",
            "placeholder": "e.g. TutuBaba Spa",
            "required": True,
            "min_length": 2,
            "max_length": 100,
            "validate_async": "/api/agent/registration/validate/shop_name"
        }]
    },
    "shop_type": {
        "message": "What **type of business** is it?",
        "fields": [{
            "name": "shop_type",
            "type": "chip_select",
            "label": "Shop Type",
            "options": [{"value": t, "label": t} for t in SHOP_TYPE_OPTIONS],
            "required": True,
            "allow_custom": True,
            "custom_placeholder": "Other type..."
        }]
    },
    "shop_address": {
        "message": "Enter your shop's **address**.",
        "fields": [
            {"name": "address", "type": "text", "label": "Street Address", "placeholder": "123 Main St", "required": True},
            {"name": "city", "type": "text", "label": "City", "placeholder": "Toronto", "required": True},
            {"name": "state", "type": "text", "label": "State / Province", "placeholder": "ON", "required": True},
            {"name": "zip_code", "type": "text", "label": "ZIP / Postal Code", "placeholder": "M5V 2T6", "required": True},
            {"name": "phone", "type": "tel", "label": "Phone Number", "placeholder": "(416) 555-0123", "required": True},
        ]
    },
    "confirm": {
        "message": "Please review your details and **confirm** to complete registration.",
        "fields": [{
            "name": "confirm",
            "type": "confirm",
            "label": "Confirm Registration"
        }]
    }
}

# AI prompt per step (spoken by TTS)
STEP_PROMPTS: Dict[str, str] = {
    "account_type": "Let's get you registered! Are you a shop owner or a customer?",
    "email": "Great! What's your email address?",
    "username": "Now choose a username for your account.",
    "password": "Create a password. Make it at least 8 characters.",
    "shop_name": "What's the name of your shop?",
    "shop_type": "What type of business is it?",
    "shop_address": "Enter your shop's address and phone number.",
    "confirm": "Here's a summary of your details. Confirm to complete registration.",
}


class RegistrationAgent:
    """
    Redis-backed registration state machine.
    
    Session state stored at key: reg:{session_id}
    State shape: {
        "step": "email",
        "account_type": "shop_owner",
        "data": { "email": "...", "username": "...", ... },
        "started_at": "2026-02-26T...",
        "completed": false
    }
    """

    REDIS_PREFIX = "reg:"
    SESSION_TTL = 1800  # 30 minutes

    # --- Session Management ---

    def _key(self, session_id: str) -> str:
        return f"{self.REDIS_PREFIX}{session_id}"

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        data = redis_client.get(self._key(session_id))
        return data if isinstance(data, dict) else None

    def _save_session(self, session_id: str, state: Dict[str, Any]):
        redis_client.set(self._key(session_id), state, ttl=self.SESSION_TTL)

    def _clear_session(self, session_id: str):
        redis_client.delete(self._key(session_id))

    # --- Public API ---

    def start(self, session_id: str, account_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Start a new registration flow. Returns the first form_step event payload.
        If account_type is already known, skip to the email step.
        """
        state = {
            "step": "account_type",
            "account_type": account_type,
            "data": {},
            "started_at": datetime.utcnow().isoformat(),
            "completed": False
        }

        # If account_type is pre-selected, skip step 1
        if account_type in ("shop_owner", "customer"):
            state["step"] = "email"
            state["data"]["account_type"] = account_type

        self._save_session(session_id, state)
        return self._build_form_event(state)

    def process_step(self, session_id: str, field_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a submitted form step. Validate, store, and advance.
        Returns the next form_step event, or a done/error event.
        """
        state = self.get_session(session_id)
        if not state:
            return {"type": "form_error", "message": "Registration session expired. Please start again."}

        current_step = state["step"]

        # Validate the submitted data
        errors = self._validate_step(current_step, field_data, state)
        if errors:
            # Return the same step with errors
            event = self._build_form_event(state)
            event["errors"] = errors
            return event

        # Store validated data
        state["data"].update(field_data)

        # Handle special step logic
        if current_step == "account_type":
            state["account_type"] = field_data.get("account_type", "customer")

        # Advance to next step
        steps = SHOP_OWNER_STEPS if state["account_type"] == "shop_owner" else CUSTOMER_STEPS
        current_idx = steps.index(current_step) if current_step in steps else 0
        
        if current_step == "confirm":
            # Final step — create the account
            return self._finalize_registration(session_id, state)

        next_step = steps[current_idx + 1] if current_idx + 1 < len(steps) else "confirm"
        state["step"] = next_step
        self._save_session(session_id, state)
        return self._build_form_event(state)

    # --- Validation ---

    def _validate_step(self, step: str, data: Dict[str, Any], state: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Validate a step's data. Returns {field: error_message} or None."""
        errors = {}

        if step == "account_type":
            if data.get("account_type") not in ("shop_owner", "customer"):
                errors["account_type"] = "Please select shop owner or customer."

        elif step == "email":
            email = (data.get("email") or "").strip().lower()
            if not email or not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
                errors["email"] = "Please enter a valid email address."
            elif self._check_email_taken(email):
                errors["email"] = "This email is already registered. Try signing in instead."

        elif step == "username":
            username = (data.get("username") or "").strip()
            if len(username) < 3:
                errors["username"] = "Username must be at least 3 characters."
            elif len(username) > 30:
                errors["username"] = "Username must be 30 characters or less."
            elif not re.match(r'^[a-zA-Z0-9_]+$', username):
                errors["username"] = "Username can only contain letters, numbers, and underscores."
            elif self._check_username_taken(username):
                errors["username"] = "This username is already taken."

        elif step == "password":
            password = data.get("password") or ""
            if len(password) < 8:
                errors["password"] = "Password must be at least 8 characters."

        elif step == "shop_name":
            name = (data.get("shop_name") or "").strip()
            if len(name) < 2:
                errors["shop_name"] = "Shop name must be at least 2 characters."
            elif self._check_shop_name_taken(name):
                errors["shop_name"] = "A shop with this name already exists."

        elif step == "shop_type":
            if not data.get("shop_type"):
                errors["shop_type"] = "Please select a business type."

        elif step == "shop_address":
            for field in ["address", "city", "state", "zip_code", "phone"]:
                if not (data.get(field) or "").strip():
                    errors[field] = f"{field.replace('_', ' ').title()} is required."

        elif step == "confirm":
            pass  # No validation needed for confirm

        return errors if errors else None

    # --- Database Checks ---

    def _check_email_taken(self, email: str) -> bool:
        try:
            db = SessionLocal()
            try:
                from modules.auth.models import User
                return db.query(User).filter(User.email == email.lower()).first() is not None
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Email check failed: {e}")
            return False

    def _check_username_taken(self, username: str) -> bool:
        try:
            db = SessionLocal()
            try:
                from modules.auth.models import User
                return db.query(User).filter(User.username == username.lower()).first() is not None
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Username check failed: {e}")
            return False

    def _check_shop_name_taken(self, name: str) -> bool:
        try:
            db = SessionLocal()
            try:
                from modules.shops.models import Shop
                slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
                return db.query(Shop).filter(Shop.slug.like(f"{slug}%")).first() is not None
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Shop name check failed: {e}")
            return False

    # --- Async Validation (called by API endpoint for real-time checks) ---

    def validate_field(self, field: str, value: str) -> Dict[str, Any]:
        """Validate a single field in real-time. Returns {available: bool, message: str}."""
        value = value.strip()

        if field == "email":
            if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', value):
                return {"available": False, "message": "Invalid email format"}
            taken = self._check_email_taken(value.lower())
            return {"available": not taken, "message": "Already registered" if taken else "Available"}

        elif field == "username":
            if len(value) < 3:
                return {"available": False, "message": "Too short (min 3)"}
            if not re.match(r'^[a-zA-Z0-9_]+$', value):
                return {"available": False, "message": "Letters, numbers, underscores only"}
            taken = self._check_username_taken(value.lower())
            return {"available": not taken, "message": "Taken" if taken else "Available"}

        elif field == "shop_name":
            if len(value) < 2:
                return {"available": False, "message": "Too short (min 2)"}
            taken = self._check_shop_name_taken(value)
            return {"available": not taken, "message": "Name taken" if taken else "Available"}

        return {"available": True, "message": "OK"}

    # --- Event Builders ---

    def _build_form_event(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Build a form_step SSE event payload from current state."""
        step = state["step"]
        schema = STEP_SCHEMAS.get(step, {})
        steps = SHOP_OWNER_STEPS if state.get("account_type") == "shop_owner" else CUSTOMER_STEPS
        
        # For confirm step, include collected summary
        summary = None
        if step == "confirm":
            summary = {k: v for k, v in state["data"].items() if k != "password"}

        current_idx = steps.index(step) if step in steps else 0
        progress = int((current_idx / len(steps)) * 100)

        return {
            "type": "form_step",
            "step": step,
            "message": schema.get("message", ""),
            "prompt": STEP_PROMPTS.get(step, ""),
            "fields": schema.get("fields", []),
            "progress": progress,
            "step_number": current_idx + 1,
            "total_steps": len(steps),
            "summary": summary
        }

    # --- Finalize Registration ---

    def _finalize_registration(self, session_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create user (and shop if owner) in the database."""
        data = state["data"]
        account_type = state.get("account_type", "customer")

        db = SessionLocal()
        try:
            from modules.auth.models import User, UserRole
            
            # 1. Create User
            hashed_pw = get_password_hash(data["password"])
            new_user = User(
                username=data["username"].lower(),
                email=data["email"].lower(),
                hashed_password=hashed_pw,
                role=UserRole(account_type),
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(new_user)
            db.flush()  # Get the user ID

            shop_data = None
            # 2. Create Shop (if shop_owner)
            if account_type == "shop_owner" and data.get("shop_name"):
                from modules.shops.models import Shop
                from modules.registry import ModuleRegistry, modules_for_vertical, normalize_vertical
                import random
                
                slug = re.sub(r'[^a-z0-9]+', '-', data["shop_name"].lower()).strip('-')
                slug = f"{slug}-{random.randint(100, 999)}"
                vertical = normalize_vertical(data.get("vertical") or data.get("shop_type"))
                
                new_shop = Shop(
                    owner_id=new_user.id,
                    name=data["shop_name"],
                    shop_type=data.get("shop_type", "Other"),
                    vertical=vertical,
                    address=data.get("address", ""),
                    city=data.get("city", ""),
                    state=data.get("state", ""),
                    zip_code=data.get("zip_code", ""),
                    country=data.get("country", "United States"),
                    phone=data.get("phone", ""),
                    slug=slug,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(new_shop)
                db.flush()

                # 3. Create default queue
                try:
                    from modules.queues.models import Queue
                    default_queue = Queue(
                        shop_id=new_shop.id,
                        name="Main Queue",
                        is_active=True,
                        created_at=datetime.utcnow()
                    )
                    db.add(default_queue)
                except Exception as e:
                    logger.warning(f"Default queue creation failed: {e}")

                try:
                    from tenant_manager import ensure_shop_schema

                    ensure_shop_schema(db, new_shop.id)
                    ModuleRegistry().activate_modules_for_tenant(
                        str(new_shop.id),
                        modules_for_vertical(vertical),
                        db,
                    )
                    logger.info("Tenant schema and modules provisioned for shop %s (%s)", new_shop.id, vertical)
                except Exception as e:
                    logger.error("Tenant module provisioning failed for shop %s: %s", new_shop.id, e, exc_info=True)
                    raise

                shop_data = {"name": data["shop_name"], "slug": slug, "type": data.get("shop_type")}

            db.commit()

            # Clear registration session
            self._clear_session(session_id)

            logger.info(f"Registration complete | user={data['username']} | type={account_type}")

            return {
                "type": "form_done",
                "success": True,
                "message": f"Welcome aboard, {data['username']}! Your account is ready.",
                "account_type": account_type,
                "username": data["username"],
                "email": data["email"],
                "shop": shop_data
            }

        except Exception as e:
            logger.error(f"Registration failed: {e}", exc_info=True)
            try:
                db.rollback()
            except Exception:
                pass

            return {
                "type": "form_done",
                "success": False,
                "message": f"Registration failed: {str(e)}. Please try again."
            }
        finally:
            db.close()


# Singleton
registration_agent = RegistrationAgent()
