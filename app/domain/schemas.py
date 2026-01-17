# app/domain/schemas.py
from pydantic import BaseModel, Field, ConfigDict
from typing import List
from decimal import Decimal
from datetime import datetime


class ItemIn(BaseModel):
    """Schema dla dodawania produktu do koszyka."""
    
    product_id: int = Field(..., gt=0, description="ID produktu (musi być > 0)")
    quantity: int = Field(..., gt=0, description="Ilość produktu (musi być > 0)")


class CreateCartIn(BaseModel):
    """Schema dla tworzenia koszyka."""
    
    user_id: int = Field(..., gt=0, description="ID użytkownika (musi być > 0)")


class CartItemOut(BaseModel):
    """Schema dla produktu w koszyku (response)."""
    
    product_id: int
    quantity: int
    price: Decimal


class CartOut(BaseModel):
    """Schema dla koszyka (response)."""
    
    cart_id: int
    user_id: int
    status: str
    items: List[CartItemOut]
    total: Decimal
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    """Schema dla tworzenia użytkownika."""
    
    id: int = Field(..., gt=0, description="ID użytkownika (musi być > 0)")
    name: str = Field(..., min_length=1, max_length=100, description="Imię użytkownika")


class UserRead(BaseModel):
    """Schema dla użytkownika (response)."""
    
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    """Schema dla tworzenia zamówienia."""
    
    cart_id: int = Field(..., gt=0, description="ID koszyka (musi być > 0)")
    user_id: int = Field(..., gt=0, description="ID użytkownika (musi być > 0)")


class OrderOut(BaseModel):
    """Schema dla zamówienia (response)."""
    
    id: int
    cart_id: int
    user_id: int
    status: str
    total: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
