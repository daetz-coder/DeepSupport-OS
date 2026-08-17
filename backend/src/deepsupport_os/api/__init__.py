from fastapi import APIRouter

from deepsupport_os.api.eval import router as eval_router
from deepsupport_os.api.meta import router as meta_router
from deepsupport_os.api.tasks import router as tasks_router
from deepsupport_os.api.timeline import router as timeline_router

api_router = APIRouter(prefix="/api")
api_router.include_router(tasks_router)
api_router.include_router(meta_router)
api_router.include_router(eval_router)
api_router.include_router(timeline_router)
