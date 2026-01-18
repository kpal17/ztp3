from pydantic import BaseModel, Field, ConfigDict
from typing import List
from decimal import Decimal
from datetime import datetime


class ItemIn(BaseModel):
    #dodawania produktu do koszyka
    product_id: int = Field(..., gt=0, description="ID produktu (musi być > 0)")
    quantity: int = Field(..., gt=0, description="Ilość produktu (musi być > 0)")


class CreateCartIn(BaseModel):
    #tworzenie koszyka
    user_id: int = Field(..., gt=0, description="ID użytkownika (musi być > 0)")


class CartItemOut(BaseModel):
    #produkt w koszyku (response)
    product_id: int
    quantity: int
    price: Decimal


class CartOut(BaseModel):
    #koszyk (response)
    cart_id: int
    user_id: int
    status: str
    items: List[CartItemOut]
    total: Decimal
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    id: int = Field(..., gt=0, description="ID użytkownika (musi być > 0)")
    name: str = Field(..., min_length=1, max_length=100, description="Imię użytkownika")


class UserRead(BaseModel):
    #schema pod uztkownika (response)
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    #tworzenie koszyka
    cart_id: int = Field(..., gt=0, description="ID koszyka (musi być > 0)")
    user_id: int = Field(..., gt=0, description="ID użytkownika (musi być > 0)")


class OrderOut(BaseModel):
    #zamowienie response
    id: int
    cart_id: int
    user_id: int
    status: str
    total: Decimal
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
