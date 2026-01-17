# app/data/seed.py
from app.data.database import SessionLocal
from app.data.models import Cart, CartItem
import uuid
from datetime import datetime, timezone, timedelta
from app.utils.settings import CART_TTL_SECONDS

def seed():
    db = SessionLocal()
    try:
        # not forcing: only seed if empty
        if db.query(Cart).first():
            return
        c = Cart(id=uuid.uuid4(), user_id=uuid.uuid4(), status="ACTIVE", version=1, expires_at=datetime.now(timezone.utc) + timedelta(seconds=CART_TTL_SECONDS))
        db.add(c)
        db.commit()
    finally:
        db.close()
