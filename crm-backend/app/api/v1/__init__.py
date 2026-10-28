from fastapi import APIRouter

from app.api.v1 import (
    accounts,
    activities,
    approvals,
    auth,
    dashboards,
    help,
    leads,
    org,
    pool,
    system,
    targets,
)

api_router = APIRouter()
api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(org.router, tags=["org"])
api_router.include_router(leads.router, tags=["leads"])
api_router.include_router(accounts.router, tags=["accounts"])
api_router.include_router(activities.router, tags=["activities"])
api_router.include_router(pool.router, tags=["pool"])
api_router.include_router(targets.router, tags=["targets"])
api_router.include_router(dashboards.router, tags=["dashboards"])
api_router.include_router(system.router, tags=["system"])
api_router.include_router(approvals.router, tags=["approvals"])
api_router.include_router(help.router, tags=["help"])
