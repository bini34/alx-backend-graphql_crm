from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
	"""Shared timestamp fields for auditability."""

	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		abstract = True


class Customer(TimeStampedModel):
	name = models.CharField(max_length=255)
	email = models.EmailField(unique=True)
	phone = models.CharField(max_length=32, blank=True)

	class Meta:
		ordering = ['name']

	def __str__(self) -> str:
		return f"{self.name} ({self.email})"


class Product(TimeStampedModel):
	name = models.CharField(max_length=255)
	price = models.DecimalField(
		max_digits=10,
		decimal_places=2,
		validators=[MinValueValidator(Decimal('0.01'))],
	)
	stock = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ['name']

	def __str__(self) -> str:
		return f"{self.name}"


class Order(TimeStampedModel):
	customer = models.ForeignKey(
		Customer,
		on_delete=models.CASCADE,
		related_name='orders',
	)
	products = models.ManyToManyField(Product, related_name='orders')
	total_amount = models.DecimalField(
		max_digits=12,
		decimal_places=2,
		validators=[MinValueValidator(Decimal('0.00'))],
	)
	order_date = models.DateTimeField(default=timezone.now)

	class Meta:
		ordering = ['-order_date']

	def __str__(self) -> str:
		return f"Order #{self.pk}"
