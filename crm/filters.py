"""Reusable django-filter filter sets for CRM GraphQL queries."""
from __future__ import annotations

import django_filters
from django.db.models import QuerySet

from .models import Customer, Order, Product


class CustomerFilter(django_filters.FilterSet):
    name_icontains = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
        label="Case-insensitive match on customer name",
    )
    email_icontains = django_filters.CharFilter(
        field_name="email",
        lookup_expr="icontains",
        label="Case-insensitive match on customer email",
    )
    created_at_gte = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )
    created_at_lte = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="lte",
    )
    phone_pattern = django_filters.CharFilter(method="filter_phone_pattern")

    class Meta:
        model = Customer
        fields = [
            "name_icontains",
            "email_icontains",
            "created_at_gte",
            "created_at_lte",
            "phone_pattern",
        ]

    def filter_phone_pattern(self, queryset: QuerySet[Customer], name: str, value: str):
        if not value:
            return queryset
        return queryset.filter(phone__startswith=value)


class ProductFilter(django_filters.FilterSet):
    name_icontains = django_filters.CharFilter(
        field_name="name",
        lookup_expr="icontains",
    )
    price_gte = django_filters.NumberFilter(
        field_name="price",
        lookup_expr="gte",
    )
    price_lte = django_filters.NumberFilter(
        field_name="price",
        lookup_expr="lte",
    )
    stock_gte = django_filters.NumberFilter(
        field_name="stock",
        lookup_expr="gte",
    )
    stock_lte = django_filters.NumberFilter(
        field_name="stock",
        lookup_expr="lte",
    )

    class Meta:
        model = Product
        fields = [
            "name_icontains",
            "price_gte",
            "price_lte",
            "stock_gte",
            "stock_lte",
        ]


class OrderFilter(django_filters.FilterSet):
    total_amount_gte = django_filters.NumberFilter(
        field_name="total_amount",
        lookup_expr="gte",
    )
    total_amount_lte = django_filters.NumberFilter(
        field_name="total_amount",
        lookup_expr="lte",
    )
    order_date_gte = django_filters.DateTimeFilter(
        field_name="order_date",
        lookup_expr="gte",
    )
    order_date_lte = django_filters.DateTimeFilter(
        field_name="order_date",
        lookup_expr="lte",
    )
    customer_name = django_filters.CharFilter(
        field_name="customer__name",
        lookup_expr="icontains",
    )
    product_name = django_filters.CharFilter(
        field_name="products__name",
        lookup_expr="icontains",
    )
    product_id = django_filters.NumberFilter(
        field_name="products__id",
        lookup_expr="exact",
    )

    class Meta:
        model = Order
        fields = [
            "total_amount_gte",
            "total_amount_lte",
            "order_date_gte",
            "order_date_lte",
            "customer_name",
            "product_name",
            "product_id",
        ]

    def filter_queryset(self, queryset: QuerySet[Order]):
        queryset = super().filter_queryset(queryset)
        return queryset.distinct()
