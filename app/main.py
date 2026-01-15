# app/main.py
from fastapi import FastAPI
from app.data.database import Base, engine
from app.api.routers import users, carts, orders, health
from app.utils.logging import get_logger
import uvicorn

logger = get_logger(__name__)

# IMPORT WSZYSTKICH MODELI NA POCZĄTKU (PRZED JAKIMKOLWIEK CREATE_ALL)
from app.data.models.user import UserModel
from app.data.models.cart import CartModel
from app.data.models.cart_item import CartItemModel
from app.data.models.order import OrderModel

print("=" * 80)
print("🔧 INITIALIZING DATABASE...")
print(f"📦 Models registered in Base.metadata: {list(Base.metadata.tables.keys())}")
print("=" * 80)

try:
    Base.metadata.create_all(bind=engine)
    print("✅ DATABASE TABLES CREATED SUCCESSFULLY")
    print("=" * 80)
except Exception as e:
    print(f"❌ FAILED TO CREATE TABLES: {e}")
    print("=" * 80)
    raise


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cart Service",
        version="1.0.0",
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(users.router)
    app.include_router(carts.router)
    app.include_router(orders.router)

    return app


app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)