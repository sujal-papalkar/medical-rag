"""
Aggregated API v1 Router.
"""

from fastapi import APIRouter
from app.api.v1 import health, documents, patients, retrieval, prescriptions

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(patients.router)
api_router.include_router(retrieval.router)
api_router.include_router(prescriptions.router)
