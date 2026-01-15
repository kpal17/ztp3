# app/api/__init__.py
from fastapi import FastAPI
from app.api.routers import carts
from app.api.routers.health import router as health_router

def create_app():
    app = FastAPI(title="Cart Service (reorg)")
    app.include_router(health_router)
    app.include_router(carts.router)
    return app