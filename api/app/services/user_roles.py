"""Service to manage user roles, feature permissions, user creation, and private admin trades with robust offline JSON fallbacks."""

import json
import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from app.services.supabase_store import get_client
from app.symbols import normalize_symbol, display_symbol

logger = logging.getLogger(__name__)

ROLES_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_roles_cache.json")
TRADES_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "admin_trades_cache.json")

DEFAULT_PERMISSIONS = {
    "can_view_charts": True,
    "can_view_recommendations": True,
    "can_view_heatmap": True,
    "can_view_signals": True,
    "can_backtest": True,
    "can_use_portfolio": True,
}

ADMIN_EMAIL = "vikas.raiexp@gmail.com"


def _read_json_cache(filepath: str) -> Dict[str, Any]:
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_json_cache(filepath: str, data: Dict[str, Any]) -> None:
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.error(f"Failed to write cache file {filepath}: {exc}")


# ---------------------------------------------------------------------------
# User Roles & Permissions Services
# ---------------------------------------------------------------------------

def get_user_role_profile(user_id: str, email: str | None = None) -> Dict[str, Any]:
    """Retrieve role and permissions for a user, auto-creating a profile if missing."""
    client = get_client()
    
    # Check if the user is the designated admin
    is_admin = (email == ADMIN_EMAIL) or (user_id == "admin-vikas-id")
    role = "admin" if is_admin else "user"
    
    if client:
        try:
            res = client.table("user_roles").select("*").eq("user_id", user_id).maybe_single().execute()
            if res.data:
                profile = res.data
                # Auto-upgrade designated email to admin if needed
                if is_admin and profile["role"] != "admin":
                    profile["role"] = "admin"
                    client.table("user_roles").update({"role": "admin"}).eq("id", profile["id"]).execute()
                return profile
            
            # Profile doesn't exist, create it
            profile_email = email or ("vikas.raiexp@gmail.com" if is_admin else f"user-{user_id[:8]}@advisor.in")
            new_profile = {
                "user_id": user_id,
                "email": profile_email,
                "role": role,
                "permissions": DEFAULT_PERMISSIONS,
            }
            inserted = client.table("user_roles").insert(new_profile).execute()
            if inserted.data:
                return inserted.data[0]
        except Exception as exc:
            logger.error(f"Supabase roles lookup failed: {exc}")

    # Offline/local cache fallback
    cache = _read_json_cache(ROLES_CACHE_FILE)
    if "profiles" not in cache:
        cache["profiles"] = {}
        
    if user_id in cache["profiles"]:
        profile = cache["profiles"][user_id]
        if is_admin and profile["role"] != "admin":
            profile["role"] = "admin"
            _write_json_cache(ROLES_CACHE_FILE, cache)
        return profile

    # Auto register offline
    profile_email = email or ("vikas.raiexp@gmail.com" if is_admin else f"user-{user_id[:8]}@advisor.in")
    new_profile = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "email": profile_email,
        "role": role,
        "permissions": DEFAULT_PERMISSIONS,
        "created_at": datetime.utcnow().isoformat(),
    }
    if is_admin:
        new_profile["offline_password"] = "DellCompaq@123"
    cache["profiles"][user_id] = new_profile
    _write_json_cache(ROLES_CACHE_FILE, cache)
    return new_profile


def get_all_roles_profiles() -> List[Dict[str, Any]]:
    client = get_client()
    if client:
        try:
            res = client.table("user_roles").select("*").order("created_at").execute()
            return res.data
        except Exception as exc:
            logger.error(f"Supabase failed listing roles: {exc}")

    # Fallback
    cache = _read_json_cache(ROLES_CACHE_FILE)
    profiles = list(cache.get("profiles", {}).values())
    
    # Auto seed admin profile offline if missing
    admin_exists = any(p["email"] == ADMIN_EMAIL for p in profiles)
    if not admin_exists:
        admin_profile = get_user_role_profile("admin-vikas-id", ADMIN_EMAIL)
        profiles.append(admin_profile)
        
    return sorted(profiles, key=lambda x: x.get("created_at", ""))


def set_user_permissions(user_id: str, permissions: Dict[str, bool]) -> bool:
    client = get_client()
    if client:
        try:
            client.table("user_roles").update({"permissions": permissions}).eq("user_id", user_id).execute()
            return True
        except Exception as exc:
            logger.error(f"Supabase set permissions failed: {exc}")

    # Local fallback
    cache = _read_json_cache(ROLES_CACHE_FILE)
    if "profiles" in cache and user_id in cache["profiles"]:
        cache["profiles"][user_id]["permissions"] = permissions
        _write_json_cache(ROLES_CACHE_FILE, cache)
        return True
    return False


def create_user_admin(email: str, password: str) -> Dict[str, Any]:
    """Create a new user with default role and permissions, registering them in Supabase Auth if online."""
    client = get_client()
    new_user_id = str(uuid.uuid4())
    
    # Determine role
    is_admin = (email.lower() == ADMIN_EMAIL.lower())
    role = "admin" if is_admin else "user"

    if client:
        try:
            # Service role auth allows bypass email confirmation
            auth_res = client.auth.admin.create_user({
                "email": email.strip(),
                "password": password,
                "email_confirm": True
            })
            if auth_res.user:
                new_user_id = auth_res.user.id
                logger.info(f"Supabase Auth registered user {email} -> {new_user_id}")
        except Exception as exc:
            logger.error(f"Supabase Auth registration failed (user might already exist in auth): {exc}")
            # If user already exists in auth, we can still generate role record
            try:
                # Attempt to get user id if exists in auth
                # (Simple fallback mock id if can't look up, which is safe since upsert matches symbol/user)
                pass
            except Exception:
                pass

    # Create profile
    profile = {
        "user_id": new_user_id,
        "email": email.strip(),
        "role": role,
        "permissions": DEFAULT_PERMISSIONS,
    }
    
    if client:
        try:
            client.table("user_roles").upsert(profile, on_conflict="user_id").execute()
        except Exception as exc:
            logger.error(f"Supabase user role profile upsert failed: {exc}")

    # Local fallback
    cache = _read_json_cache(ROLES_CACHE_FILE)
    if "profiles" not in cache:
        cache["profiles"] = {}
        
    profile["id"] = str(uuid.uuid4())
    profile["created_at"] = datetime.utcnow().isoformat()
    # Save the plaintext password locally in offline mode to support mock logins/impersonations
    profile["offline_password"] = password
    cache["profiles"][new_user_id] = profile
    _write_json_cache(ROLES_CACHE_FILE, cache)
    
    return profile


# ---------------------------------------------------------------------------
# Admin Separate Trading Dashboard Services
# ---------------------------------------------------------------------------

def get_admin_trades() -> List[Dict[str, Any]]:
    client = get_client()
    if client:
        try:
            res = client.table("admin_trades").select("*").order("created_at", desc=True).execute()
            return res.data
        except Exception as exc:
            logger.error(f"Supabase admin trades listing failed: {exc}")

    # Local fallback
    cache = _read_json_cache(TRADES_CACHE_FILE)
    return list(cache.get("trades", {}).values())


def record_admin_trade(symbol: str, quantity: float, buy_price: float) -> bool:
    norm_sym = normalize_symbol(symbol)
    client = get_client()
    
    trade_data = {
        "symbol": norm_sym,
        "shares_quantity": quantity,
        "buy_price": buy_price,
        "trade_status": "open",
    }
    
    if client:
        try:
            # Ensure stock exists first
            profile = {"symbol": norm_sym, "display_symbol": display_symbol(norm_sym)}
            client.table("stocks").upsert(profile).execute()
            client.table("admin_trades").insert(trade_data).execute()
            return True
        except Exception as exc:
            logger.error(f"Supabase admin trade record failed: {exc}")

    # Local fallback
    cache = _read_json_cache(TRADES_CACHE_FILE)
    if "trades" not in cache:
        cache["trades"] = {}
        
    trade_id = str(uuid.uuid4())
    trade_data["id"] = trade_id
    trade_data["display_symbol"] = display_symbol(norm_sym)
    trade_data["created_at"] = datetime.utcnow().isoformat()
    cache["trades"][trade_id] = trade_data
    _write_json_cache(TRADES_CACHE_FILE, cache)
    return True


def close_admin_trade(trade_id: str, sell_price: float) -> bool:
    client = get_client()
    
    if client:
        try:
            existing = client.table("admin_trades").select("*").eq("id", trade_id).maybe_single().execute()
            if existing.data:
                qty = float(existing.data["shares_quantity"])
                buy_price = float(existing.data["buy_price"])
                pnl = round((sell_price - buy_price) * qty, 2)
                client.table("admin_trades").update({
                    "sell_price": sell_price,
                    "trade_status": "closed",
                    "profit_loss": pnl,
                }).eq("id", trade_id).execute()
                return True
        except Exception as exc:
            logger.error(f"Supabase close admin trade failed: {exc}")

    # Local fallback
    cache = _read_json_cache(TRADES_CACHE_FILE)
    if "trades" in cache and trade_id in cache["trades"]:
        trade = cache["trades"][trade_id]
        qty = float(trade["shares_quantity"])
        buy_price = float(trade["buy_price"])
        pnl = round((sell_price - buy_price) * qty, 2)
        trade["sell_price"] = sell_price
        trade["trade_status"] = "closed"
        trade["profit_loss"] = pnl
        _write_json_cache(TRADES_CACHE_FILE, cache)
        return True
    return False
