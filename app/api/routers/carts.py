#app/appi/routers/carts.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.data.database import get_db
from app.domain.schemas import (
    CreateCartIn,
    ItemIn,
    CartOut,
)
from app.services.cart_service import CartService
from app.services.product_client import ProductClient
from app.services.lock_service import LockService

router = APIRouter(prefix="/carts", tags=["carts"])


def get_service(db: Session):
    return CartService(
        db=db,
        product_client=ProductClient(),
        lock_service=LockService(),
    )


@router.post("/", response_model=CartOut)
def create_cart(payload: CreateCartIn, db: Session = Depends(get_db)):
    svc = get_service(db)
    return svc.create_cart(payload.user_id)


@router.get("/{cart_id}", response_model=CartOut)
def get_cart(
    cart_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    svc = get_service(db)
    cart = svc.get_cart(cart_id, user_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Koszyk nie znaleziony")
    return cart


@router.post("/{cart_id}/items", response_model=CartOut)
def add_item(
    cart_id: int,
    payload: ItemIn,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    svc = get_service(db)
    try:
        return svc.add_product(
            user_id=user_id,
            cart_id=cart_id,
            product_id=payload.product_id,
            quantity=payload.quantity,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{cart_id}/items/{product_id}", response_model=CartOut)
def remove_item(
    cart_id: int,
    product_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    svc = get_service(db)
    try:
        return svc.remove_product(user_id, cart_id, product_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{cart_id}/finalize", response_model=CartOut)
def finalize_cart(
    cart_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    svc = get_service(db)
    try:
        return svc.finalize_cart(user_id, cart_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
