from datetime import datetime, timezone

from fastapi import HTTPException, Request, Depends

import server as S

db, api, get_current_user = S.db, S.api_router, S.get_current_user


def platform_admin(user: dict):
    if user["uid"] != S.PLATFORM["id"]:
        raise HTTPException(status_code=403, detail="Doar administratorul principal al platformei poate activa sau dezactiva module")


@api.get("/platform/modules")
async def modules_list(user: dict = Depends(get_current_user)):
    platform_admin(user)
    pm = await db.platform_modules.find_one({"id": "main"}, {"_id": 0}) or {}
    off = set(pm.get("disabled", []))
    return {"modules": [{"key": k, "label": v, "enabled": k not in off} for k, v in S.ALL_FEATURES.items()],
            "updated_at": pm.get("updated_at"), "updated_by": pm.get("updated_by")}


@api.put("/platform/modules")
async def modules_save(request: Request, user: dict = Depends(get_current_user)):
    platform_admin(user)
    b = await request.json()
    off = b.get("disabled")
    if not isinstance(off, list) or any(k not in S.ALL_FEATURES for k in off):
        raise HTTPException(status_code=400, detail="Listă de module invalidă")
    off = sorted(set(off))
    await db.platform_modules.update_one({"id": "main"}, {"$set": {"id": "main", "disabled": off, "updated_at": datetime.now(timezone.utc).isoformat(),
                                                                   "updated_by": user.get("email")}}, upsert=True)
    await S.audit(user, "module platformă", "platform", "modules", [f"dezactivate: {', '.join(off) or '—'}"])
    return {"disabled": off}
