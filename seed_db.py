"""Seed script to populate the CRM database with sample data."""
from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP

import django
from django.db import transaction

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "alx_backend_graphql_crm.settings")
django.setup()

from crm.models import Customer, Order, Product  # noqa: E402


CUSTOMERS = [
    {"name": "Alice Johnson", "email": "alice@example.com", "phone": "+1234567890"},
    {"name": "Bob Smith", "email": "bob@example.com", "phone": "123-456-7890"},
    {"name": "Carol Danvers", "email": "carol@example.com", "phone": "+19876543210"},
]

PRODUCTS = [
    {"name": "Laptop", "price": Decimal("999.99"), "stock": 10},
    {"name": "Smartphone", "price": Decimal("699.00"), "stock": 25},
    {"name": "Headphones", "price": Decimal("199.50"), "stock": 50},
]


def seed():
    with transaction.atomic():
        customer_objs = []
        for payload in CUSTOMERS:
            customer, _ = Customer.objects.get_or_create(
                email=payload["email"].lower(),
                defaults={
                    "name": payload["name"],
                    "phone": payload["phone"],
                },
            )
            customer_objs.append(customer)

        product_objs = []
        for payload in PRODUCTS:
            product, _ = Product.objects.get_or_create(
                name=payload["name"],
                defaults={
                    "price": payload["price"],
                    "stock": payload["stock"],
                },
            )
            product_objs.append(product)

        if customer_objs and product_objs:
            order, _ = Order.objects.get_or_create(
                customer=customer_objs[0],
                defaults={
                    "total_amount": sum(
                        (product.price for product in product_objs[:2]), Decimal("0")
                    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
                },
            )
            order.products.set(product_objs[:2])


if __name__ == "__main__":
    seed()
    print("Database seeded with sample CRM data.")
