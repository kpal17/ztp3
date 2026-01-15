# app/domain/schemas.py
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


class ItemIn(BaseModel):
    product_id: int
    quantity: int

class CreateCartIn(BaseModel):
    user_id: int


class CartItemOut(BaseModel):
    product_id: int
    quantity: int
    price: Decimal

class CartOut(BaseModel):
    cart_id: int
    user_id: int
    status: str
    items: List[CartItemOut]
    total: Decimal
    expires_at: Optional[datetime]

class UserCreate(BaseModel):
    id: int
    name: str

class UserRead(BaseModel):
    id: int
    name: str

class OrderCreate(BaseModel):
    cart_id: int
    user_id: int


class OrderOut(BaseModel):
    id: int
    cart_id: int
    user_id: int
    status: str
    total: Decimal
    created_at: datetime

    class Config:
        from_attributes = True

class Config:
    from_attributes = True