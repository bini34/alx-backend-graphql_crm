"""GraphQL schema definitions for the CRM domain."""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Sequence

import graphene
from django.core.exceptions import ValidationError
from django.db import transaction
from graphene import relay
from graphene_django import DjangoObjectType
from graphql import GraphQLError

from .filters import CustomerFilter, OrderFilter, ProductFilter
from .models import Customer, Order, Product

PHONE_REGEX = re.compile(r"^(?:\+\d{7,15}|\d{3}-\d{3}-\d{4})$")


class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer
        interfaces = (relay.Node,)
        fields = (
            "id",
            "name",
            "email",
            "phone",
            "created_at",
            "updated_at",
            "orders",
        )


class ProductType(DjangoObjectType):
    class Meta:
        model = Product
        interfaces = (relay.Node,)
        fields = (
            "id",
            "name",
            "price",
            "stock",
            "created_at",
            "updated_at",
        )


class OrderType(DjangoObjectType):
    products = graphene.List(ProductType)

    class Meta:
        model = Order
        interfaces = (relay.Node,)
        fields = (
            "id",
            "customer",
            "total_amount",
            "order_date",
            "created_at",
            "updated_at",
        )

    @staticmethod
    def resolve_products(root: Order, info):
        return root.products.all()


class CustomerConnection(relay.Connection):
    class Meta:
        node = CustomerType


class ProductConnection(relay.Connection):
    class Meta:
        node = ProductType


class OrderConnection(relay.Connection):
    class Meta:
        node = OrderType


class CustomerInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    phone = graphene.String()


class CustomerFilterInput(graphene.InputObjectType):
    name_icontains = graphene.String(name="nameIcontains")
    email_icontains = graphene.String(name="emailIcontains")
    created_at_gte = graphene.DateTime(name="createdAtGte")
    created_at_lte = graphene.DateTime(name="createdAtLte")
    phone_pattern = graphene.String(name="phonePattern")


class ProductInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    price = graphene.Decimal(required=True)
    stock = graphene.Int()


class ProductFilterInput(graphene.InputObjectType):
    name_icontains = graphene.String(name="nameIcontains")
    price_gte = graphene.Decimal(name="priceGte")
    price_lte = graphene.Decimal(name="priceLte")
    stock_gte = graphene.Int(name="stockGte")
    stock_lte = graphene.Int(name="stockLte")


class OrderInput(graphene.InputObjectType):
    customer_id = graphene.ID(required=True, name="customerId")
    product_ids = graphene.List(graphene.ID, required=True, name="productIds")
    order_date = graphene.DateTime(name="orderDate")


class OrderFilterInput(graphene.InputObjectType):
    total_amount_gte = graphene.Decimal(name="totalAmountGte")
    total_amount_lte = graphene.Decimal(name="totalAmountLte")
    order_date_gte = graphene.DateTime(name="orderDateGte")
    order_date_lte = graphene.DateTime(name="orderDateLte")
    customer_name = graphene.String(name="customerName")
    product_name = graphene.String(name="productName")
    product_id = graphene.ID(name="productId")


def _validate_phone(phone: Optional[str]) -> Optional[str]:
    if phone and not PHONE_REGEX.match(phone):
        raise ValidationError("Phone number must be +<digits> or 123-456-7890 format.")
    return phone


def _filter_queryset(queryset, filter_input, filter_mapping: Dict[str, str], filterset_cls):
    if not filter_input:
        return filterset_cls(queryset=queryset, data={}).qs
    payload: Dict[str, object] = {}
    for attr, lookup in filter_mapping.items():
        value = getattr(filter_input, attr, None)
        if value is not None:
            payload[lookup] = value
    filterset = filterset_cls(data=payload, queryset=queryset)
    if filterset.is_valid():
        return filterset.qs
    messages: List[str] = []
    for field, errors in filterset.errors.items():
        messages.extend(f"{field}: {error}" for error in errors)
    raise GraphQLError("; ".join(messages) or "Invalid filter arguments.")


def _apply_ordering(queryset, order_by: Optional[Sequence[str]]):
    if not order_by:
        return queryset
    if isinstance(order_by, str):
        order_by = [order_by]
    return queryset.order_by(*order_by)


class CreateCustomer(graphene.Mutation):
    class Arguments:
        input = CustomerInput(required=True)

    customer = graphene.Field(CustomerType)
    message = graphene.String()
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, input: CustomerInput):
        errors: List[str] = []
        name = input.name.strip()
        if not name:
            errors.append("Name is required.")
        try:
            _validate_phone(getattr(input, "phone", None))
        except ValidationError as exc:
            errors.extend(exc.messages)
        email = getattr(input, "email", "").strip().lower()
        if Customer.objects.filter(email__iexact=email).exists():
            errors.append("Email already exists.")
        if errors:
            return CreateCustomer(customer=None, message=None, errors=errors)
        customer = Customer(
            name=name,
            email=email,
            phone=(input.phone or "").strip(),
        )
        customer.save()
        return CreateCustomer(customer=customer, message="Customer created successfully.", errors=[])


class BulkCreateCustomers(graphene.Mutation):
    class Arguments:
        input = graphene.List(CustomerInput, required=True)

    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, input: Sequence[CustomerInput]):  # type: ignore[override]
        if not input:
            raise GraphQLError("Input list cannot be empty.")

        pending: List[Customer] = []
        errors: List[str] = []
        seen_emails = set()
        existing_emails = {
            email.lower()
            for email in Customer.objects.values_list("email", flat=True)
            if email
        }

        for index, payload in enumerate(input):
            row_errors: List[str] = []
            email = getattr(payload, "email", "").strip().lower()
            name = getattr(payload, "name", "").strip()
            phone = (payload.phone or "").strip() if getattr(payload, "phone", None) else ""

            if not name:
                row_errors.append("Name is required.")
            if not email:
                row_errors.append("Email is required.")
            elif email in existing_emails:
                row_errors.append("Email already exists.")
            elif email in seen_emails:
                row_errors.append("Duplicate email within request.")

            try:
                _validate_phone(phone)
            except ValidationError as exc:
                row_errors.extend(exc.messages)

            if row_errors:
                errors.append(f"Entry {index + 1}: {'; '.join(row_errors)}")
                continue

            seen_emails.add(email)
            pending.append(Customer(name=name, email=email, phone=phone))

        created: List[Customer] = []
        if pending:
            with transaction.atomic():
                created = list(Customer.objects.bulk_create(pending))

        return BulkCreateCustomers(customers=created, errors=errors)


class CreateProduct(graphene.Mutation):
    class Arguments:
        input = ProductInput(required=True)

    product = graphene.Field(ProductType)
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, input: ProductInput):
        errors: List[str] = []
        price = Decimal(input.price)
        stock = input.stock if input.stock is not None else 0
        if price <= 0:
            errors.append("Price must be positive.")
        if stock < 0:
            errors.append("Stock cannot be negative.")
        if errors:
            return CreateProduct(product=None, errors=errors)
        product = Product.objects.create(
            name=input.name.strip(),
            price=price.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            stock=stock,
        )
        return CreateProduct(product=product, errors=[])


class CreateOrder(graphene.Mutation):
    class Arguments:
        input = OrderInput(required=True)

    order = graphene.Field(OrderType)
    errors = graphene.List(graphene.String)

    @classmethod
    def mutate(cls, root, info, input: OrderInput):
        errors: List[str] = []
        try:
            customer_id = int(input.customer_id)
        except (TypeError, ValueError):
            errors.append("Invalid customer ID.")
            customer_id = None

        product_ids: List[int] = []
        for raw_id in input.product_ids or []:
            try:
                product_ids.append(int(raw_id))
            except (TypeError, ValueError):
                errors.append(f"Invalid product ID: {raw_id}")

        product_ids = list(dict.fromkeys(product_ids))

        if not product_ids:
            errors.append("At least one product must be provided.")

        customer: Optional[Customer] = None
        if customer_id is not None:
            try:
                customer = Customer.objects.get(pk=customer_id)
            except Customer.DoesNotExist:
                errors.append("Customer not found.")

        products = list(Product.objects.filter(id__in=product_ids)) if product_ids else []
        missing_product_ids = sorted(set(product_ids) - {product.id for product in products})
        if missing_product_ids:
            errors.append(
                "Invalid product ID(s): " + ", ".join(str(value) for value in missing_product_ids)
            )

        if errors:
            return CreateOrder(order=None, errors=errors)

        total_amount = sum((product.price for product in products), Decimal('0'))
        order_kwargs = {
            "customer": customer,
            "total_amount": total_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        }
        if getattr(input, "order_date", None):
            order_kwargs["order_date"] = input.order_date

        with transaction.atomic():
            order = Order.objects.create(**order_kwargs)
            order.products.set(products)
            order.refresh_from_db()

        return CreateOrder(order=order, errors=[])


class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()


class Query(graphene.ObjectType):
    hello = graphene.String(default_value="Hello, GraphQL!")
    customer = relay.Node.Field(CustomerType)
    product = relay.Node.Field(ProductType)
    order = relay.Node.Field(OrderType)
    all_customers = relay.ConnectionField(
        CustomerConnection,
        filter=CustomerFilterInput(),
        order_by=graphene.Argument(graphene.List(graphene.String), name="orderBy"),
    )
    all_products = relay.ConnectionField(
        ProductConnection,
        filter=ProductFilterInput(),
        order_by=graphene.Argument(graphene.List(graphene.String), name="orderBy"),
    )
    all_orders = relay.ConnectionField(
        OrderConnection,
        filter=OrderFilterInput(),
        order_by=graphene.Argument(graphene.List(graphene.String), name="orderBy"),
    )

    @staticmethod
    def resolve_all_customers(root, info, filter=None, order_by=None, **kwargs):
        queryset = Customer.objects.all()
        mapping = {
            "name_icontains": "name_icontains",
            "email_icontains": "email_icontains",
            "created_at_gte": "created_at_gte",
            "created_at_lte": "created_at_lte",
            "phone_pattern": "phone_pattern",
        }
        queryset = _filter_queryset(queryset, filter, mapping, CustomerFilter)
        queryset = _apply_ordering(queryset, order_by)
        return queryset

    @staticmethod
    def resolve_all_products(root, info, filter=None, order_by=None, **kwargs):
        queryset = Product.objects.all()
        mapping = {
            "name_icontains": "name_icontains",
            "price_gte": "price_gte",
            "price_lte": "price_lte",
            "stock_gte": "stock_gte",
            "stock_lte": "stock_lte",
        }
        queryset = _filter_queryset(queryset, filter, mapping, ProductFilter)
        queryset = _apply_ordering(queryset, order_by)
        return queryset

    @staticmethod
    def resolve_all_orders(root, info, filter=None, order_by=None, **kwargs):
        queryset = Order.objects.select_related("customer").prefetch_related("products")
        mapping = {
            "total_amount_gte": "total_amount_gte",
            "total_amount_lte": "total_amount_lte",
            "order_date_gte": "order_date_gte",
            "order_date_lte": "order_date_lte",
            "customer_name": "customer_name",
            "product_name": "product_name",
            "product_id": "product_id",
        }
        queryset = _filter_queryset(queryset, filter, mapping, OrderFilter)
        queryset = _apply_ordering(queryset, order_by)
        return queryset
