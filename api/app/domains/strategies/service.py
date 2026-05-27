from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domains.strategies.models import validate_strategy_definition
from app.services.supabase_store import get_client

CACHE_PATH = Path(__file__).resolve().parents[2] / "strategies_cache.json"


def validate_definition(definition: dict[str, Any]) -> dict[str, Any]:
    return validate_strategy_definition(definition).model_dump()


def list_strategies(user_id: str) -> list[dict[str, Any]]:
    client = get_client()
    if client:
        try:
            strategies = (
                client.table("strategies")
                .select("*")
                .eq("owner_user_id", user_id)
                .order("updated_at", desc=True)
                .execute()
                .data
            )
            if not strategies:
                return []
            versions = _fetch_versions_for_strategy_ids(client, [row["id"] for row in strategies])
            by_id = {version["id"]: version for version in versions}
            return [{**row, "current_version": by_id.get(row.get("current_version_id"))} for row in strategies]
        except Exception as exc:
            if not _can_use_local_fallback(exc):
                raise

    store = _read_cache()
    strategies = [
        _with_current_version(strategy, store)
        for strategy in store["strategies"]
        if strategy["owner_user_id"] == user_id
    ]
    return sorted(strategies, key=lambda row: row.get("updated_at") or "", reverse=True)


def get_strategy(strategy_id: str, user_id: str) -> dict[str, Any]:
    client = get_client()
    if client:
        try:
            result = (
                client.table("strategies")
                .select("*")
                .eq("id", strategy_id)
                .eq("owner_user_id", user_id)
                .limit(1)
                .execute()
            )
            if not result.data:
                raise ValueError("Strategy not found")
            row = result.data[0]
            row["versions"] = _fetch_versions_for_strategy_ids(client, [strategy_id])
            return row
        except ValueError:
            raise
        except Exception as exc:
            if not _can_use_local_fallback(exc):
                raise

    store = _read_cache()
    strategy = next(
        (
            item
            for item in store["strategies"]
            if item["id"] == strategy_id and item["owner_user_id"] == user_id
        ),
        None,
    )
    if not strategy:
        raise ValueError("Strategy not found")
    versions = [v for v in store["strategy_versions"] if v["strategy_id"] == strategy_id]
    return {**strategy, "versions": sorted(versions, key=lambda item: item["version_number"])}


def create_strategy(payload: dict[str, Any]) -> dict[str, Any]:
    validation = validate_definition(payload["definition"])
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))

    checksum = _checksum(payload["definition"])
    now = _now()
    client = get_client()
    if client:
        try:
            strategy_res = (
                client.table("strategies")
                .insert(
                    {
                        "owner_user_id": payload["user_id"],
                        "name": payload["name"],
                        "description": payload.get("description"),
                        "visibility": payload.get("visibility", "private"),
                        "status": payload.get("status", "draft"),
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                .execute()
            )
            strategy = strategy_res.data[0]
            version = _insert_version(
                client=client,
                strategy_id=strategy["id"],
                user_id=payload["user_id"],
                version_number=1,
                definition=payload["definition"],
                checksum=checksum,
                validation=validation,
                notes="Initial version",
            )
            (
                client.table("strategies")
                .update({"current_version_id": version["id"], "updated_at": now})
                .eq("id", strategy["id"])
                .execute()
            )
            strategy["current_version"] = version
            return strategy
        except Exception as exc:
            if not _can_use_local_fallback(exc):
                raise

    store = _read_cache()
    strategy = {
        "id": str(uuid4()),
        "owner_user_id": payload["user_id"],
        "name": payload["name"],
        "description": payload.get("description"),
        "visibility": payload.get("visibility", "private"),
        "status": payload.get("status", "draft"),
        "current_version_id": None,
        "created_at": now,
        "updated_at": now,
    }
    version = _cache_version(strategy["id"], payload["user_id"], 1, payload["definition"], checksum, validation, "Initial version")
    strategy["current_version_id"] = version["id"]
    store["strategies"].append(strategy)
    store["strategy_versions"].append(version)
    _write_cache(store)
    return {**strategy, "current_version": version}


def add_strategy_version(strategy_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    validation = validate_definition(payload["definition"])
    if not validation["valid"]:
        raise ValueError("; ".join(validation["errors"]))

    now = _now()
    checksum = _checksum(payload["definition"])
    client = get_client()
    if client:
        try:
            strategy = get_strategy(strategy_id, payload["user_id"])
            latest = max((v.get("version_number") or 0 for v in strategy.get("versions") or []), default=0)
            version = _insert_version(
                client=client,
                strategy_id=strategy_id,
                user_id=payload["user_id"],
                version_number=latest + 1,
                definition=payload["definition"],
                checksum=checksum,
                validation=validation,
                notes=payload.get("notes"),
            )
            (
                client.table("strategies")
                .update({"current_version_id": version["id"], "updated_at": now})
                .eq("id", strategy_id)
                .eq("owner_user_id", payload["user_id"])
                .execute()
            )
            return version
        except ValueError:
            raise
        except Exception as exc:
            if not _can_use_local_fallback(exc):
                raise

    store = _read_cache()
    strategy = next(
        (
            item
            for item in store["strategies"]
            if item["id"] == strategy_id and item["owner_user_id"] == payload["user_id"]
        ),
        None,
    )
    if not strategy:
        raise ValueError("Strategy not found")
    latest = max(
        (v["version_number"] for v in store["strategy_versions"] if v["strategy_id"] == strategy_id),
        default=0,
    )
    version = _cache_version(strategy_id, payload["user_id"], latest + 1, payload["definition"], checksum, validation, payload.get("notes"))
    store["strategy_versions"].append(version)
    strategy["current_version_id"] = version["id"]
    strategy["updated_at"] = now
    _write_cache(store)
    return version


def clone_strategy(strategy_id: str, user_id: str, name: str | None = None) -> dict[str, Any]:
    source = get_strategy(strategy_id, user_id)
    versions = source.get("versions") or []
    current = next((v for v in versions if v["id"] == source.get("current_version_id")), None) or versions[-1]
    return create_strategy(
        {
            "user_id": user_id,
            "name": name or f"{source['name']} Copy",
            "description": source.get("description"),
            "visibility": "private",
            "status": "draft",
            "definition": current["definition"],
        }
    )


def _insert_version(
    *,
    client: Any,
    strategy_id: str,
    user_id: str,
    version_number: int,
    definition: dict[str, Any],
    checksum: str,
    validation: dict[str, Any],
    notes: str | None,
) -> dict[str, Any]:
    result = (
        client.table("strategy_versions")
        .insert(
            {
                "strategy_id": strategy_id,
                "version_number": version_number,
                "version_label": f"v{version_number}",
                "definition": definition,
                "checksum": checksum,
                "validation_status": "valid" if validation["valid"] else "invalid",
                "validation_errors": validation.get("errors") or [],
                "validation_warnings": validation.get("warnings") or [],
                "notes": notes,
                "created_by_user_id": user_id,
            }
        )
        .execute()
    )
    return result.data[0]


def _fetch_versions_for_strategy_ids(client: Any, strategy_ids: list[str]) -> list[dict[str, Any]]:
    if not strategy_ids:
        return []
    result = (
        client.table("strategy_versions")
        .select("*")
        .in_("strategy_id", strategy_ids)
        .order("version_number")
        .execute()
    )
    return result.data or []


def _cache_version(
    strategy_id: str,
    user_id: str,
    version_number: int,
    definition: dict[str, Any],
    checksum: str,
    validation: dict[str, Any],
    notes: str | None,
) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "strategy_id": strategy_id,
        "version_number": version_number,
        "version_label": f"v{version_number}",
        "definition": definition,
        "checksum": checksum,
        "validation_status": "valid" if validation["valid"] else "invalid",
        "validation_errors": validation.get("errors") or [],
        "validation_warnings": validation.get("warnings") or [],
        "notes": notes,
        "created_by_user_id": user_id,
        "created_at": _now(),
    }


def _with_current_version(strategy: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    current = next(
        (v for v in store["strategy_versions"] if v["id"] == strategy.get("current_version_id")),
        None,
    )
    return {**strategy, "current_version": current}


def _checksum(definition: dict[str, Any]) -> str:
    body = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _read_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {"strategies": [], "strategy_versions": []}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"strategies": [], "strategy_versions": []}


def _write_cache(data: dict[str, Any]) -> None:
    CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.utcnow().isoformat()


def _can_use_local_fallback(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "relation",
            "schema cache",
            "could not find",
            "nodename nor servname",
            "failed to connect",
            "temporary failure",
            "network",
        )
    )
