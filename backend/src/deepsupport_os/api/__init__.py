from fastapi import APIRouter

from deepsupport_os.api.tasks import router as tasks_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tasks_router)
