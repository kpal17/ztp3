# product_service/main.py
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Product Service (dev mock)")


PRODUCTS = {
    1: {"id": 1, "name": "Keyboard", "price": 199.99},
    2: {"id": 2, "name": "Mouse", "price": 49.50},
    3: {"id": 3, "name": "Monitor", "price": 899.00},
}

@app.get("/products/{product_id}")
def get_product(product_id: int):
    product = PRODUCTS.get(product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product
