import json
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
PRODUCTS_FILE = DATA_DIR / "products.json"

INITIAL_PRODUCTS = [
    {
        "id": 123,
        "name": "Mouse Gamer",
        "price": 199.9,
        "stock": 42,
    },
    {
        "id": 456,
        "name": "Teclado Mecanico",
        "price": 349.9,
        "stock": 17,
    },
]


def reset_database() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    PRODUCTS_FILE.write_text(
        json.dumps(INITIAL_PRODUCTS, indent=2),
        encoding="utf-8",
    )


def list_products() -> list[dict[str, Any]]:
    return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))


def get_product(product_id: int) -> dict[str, Any]:
    time.sleep(0.7)
    for product in list_products():
        if int(product["id"]) == product_id:
            return dict(product)
    raise KeyError(f"Product {product_id} not found")


def update_product(product_id: int, *, price: float, stock: int) -> dict[str, Any]:
    products = list_products()
    updated_product = None

    for product in products:
        if int(product["id"]) == product_id:
            product["price"] = price
            product["stock"] = stock
            updated_product = dict(product)
            break

    if updated_product is None:
        raise KeyError(f"Product {product_id} not found")

    PRODUCTS_FILE.write_text(
        json.dumps(products, indent=2),
        encoding="utf-8",
    )
    return updated_product
