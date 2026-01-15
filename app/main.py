# app/main.py
from fastapi import FastAPI
from app.data.database import Base, engine
from app.api.routers import users, carts, health
import uvicorn


def create_app() -> FastAPI:
    app = FastAPI(title="Cart Service", version="1.0.0")

    # Include routers
    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(carts.router)

    return app


app = create_app()

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    uvicorn.run(app, host="0.0.0.0", port=8000)
