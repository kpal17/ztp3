# app/api/routers/orders.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.domain.schemas import OrderCreate, OrderOut
from app.services.order_service import OrderService

router = APIRouter(prefix="/orders", tags=["orders"])


def get_service(db: Session):
    return OrderService(db)


@router.post("/", response_model=OrderOut, status_code=201)
def create_order(
    payload: OrderCreate,
    db: Session = Depends(get_db),
):
    """
    Tworzy zamówienie z sfinalizowanego koszyka.
    Wysyła powiadomienie asynchronicznie.
    """
    svc = get_service(db)
    try:
        return svc.create_order_from_cart(payload.cart_id, payload.user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    Pobiera szczegóły zamówienia.
    """
    svc = get_service(db)
    try:
        return svc.get_order(order_id, user_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))