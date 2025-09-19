from rest_framework import serializers
from django.db.models import Sum
from django.utils.timezone import now
from calendar import monthrange
from .models import InventoryWriteOff
from django.db.models import F
from products.models import Product
from django.db.models import Q
from datetime import datetime
from sales.models import Sale
from price_slash.models import DamageProduct, ExpiringProduct

class InventoryWriteOffSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    created_by_name = serializers.CharField(read_only=True)

    total_loss = serializers.FloatField(read_only=True)
    monthly_loss = serializers.FloatField(read_only=True)

    class Meta:
        model = InventoryWriteOff
        fields = [
            'id',
            'reference',
            'product',
            'product_name',
            'quantity',
            'reason',
            'reason_display',
            'unit_price',
            'loss_value',
            'note',
            'date',
            'created_by',
            'created_by_name',
            'total_loss',
            'monthly_loss',
        ]
        read_only_fields = ['reference', 'unit_price', 'loss_value', 'created_by', 'created_by_name', 'total_loss', 'monthly_loss']

    def to_representation(self, instance):
        # Compute totals once
        rep = super().to_representation(instance)
        qs = InventoryWriteOff.objects.all()

        rep['total_loss'] = qs.aggregate(total=Sum('loss_value'))['total'] or 0

        today = now()
        first_day = today.replace(day=1)
        last_day = today.replace(day=monthrange(today.year, today.month)[1])
        rep['monthly_loss'] = qs.filter(date__range=(first_day, last_day)).aggregate(total=Sum('loss_value'))['total'] or 0

        return rep



class ProductSerializerCal(serializers.Serializer):
    product_total_value = serializers.SerializerMethodField()
    total_product = serializers.SerializerMethodField()
    total_in_stock = serializers.SerializerMethodField()
    low_stock_products = serializers.SerializerMethodField()
    out_of_stock_products = serializers.SerializerMethodField()
    monthly_turnover = serializers.SerializerMethodField()
    monthly_losses = serializers.SerializerMethodField()


    def get_product_total_value(self, obj):
        total_value = Product.objects.aggregate(
            total=Sum(F('quantity') *  (F('unit_price') + F('vat_value')))
        )['total']
        return total_value or 0

    def get_total_product(self, obj):
        return Product.objects.count()

    def get_total_in_stock(self, obj):
        return Product.objects.filter(quantity__gt=0).count()

    def get_low_stock_products(self, obj):
        products = Product.objects.filter(
            quantity__lte=F('min_stock_threshold'),
            quantity__gt=0  # exclude products with 0 stock
        )
        return [
            {
                "id": p.id,
                "name": p.name,
                "quantity": p.quantity,
                "min_stock_threshold": p.min_stock_threshold
            }
            for p in products
        ]

    def get_out_of_stock_products(self, obj):
        products = Product.objects.filter(quantity=0)
        return [
            {
                "id": p.id,
                "name": p.name,
                "quantity": p.quantity
            }
            for p in products
        ]


    def get_monthly_turnover(self, obj):
        """
        Calculate inventory turnover rate for the month.
        """
        # Use current month if no specific month provided in obj`   `
        today = datetime.today()
        month = getattr(obj, 'month', today.month)
        year = getattr(obj, 'year', today.year)

        # 1️⃣ Total sales amount for the month
        monthly_sales_total = Sale.objects.filter(
            sale_date__year=year,
            sale_date__month=month
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # 2️⃣ Average inventory for the month
        # Closing inventory = sum of (quantity * unit_buying_price)
        closing_inventory = Product.objects.aggregate(
            total_value=Sum(F('quantity') * F('unit_buying_price'))
        )['total_value'] or 0

        # Opening inventory approximation:
        # Use total sales value directly
        sold_value = monthly_sales_total

        opening_inventory = closing_inventory - sold_value

        # Avoid negative or zero average inventory
        average_inventory = max((opening_inventory + closing_inventory) / 2, 1)

        # 3️⃣ Turnover rate
        turnover_rate = monthly_sales_total / average_inventory

        return round(turnover_rate, 2)


    def get_monthly_losses(self, obj):
        """
        Calculate total inventory losses for a specific month.
        Returns total and breakdown per category.
        """
        today = datetime.today()
        month = getattr(obj, 'month', today.month)
        year = getattr(obj, 'year', today.year)

        # InventoryWriteOff losses (uses 'date')
        writeoff_loss = InventoryWriteOff.objects.filter(
            date__year=year,
            date__month=month
        ).aggregate(total=Sum('loss_value'))['total'] or 0

        # ExpiringProduct losses (uses 'created_date')
        expiring_loss = ExpiringProduct.objects.filter(
            created_date__year=year,
            created_date__month=month
        ).aggregate(total=Sum('loss_value'))['total'] or 0

        # DamageProduct losses (uses 'created_date')
        damage_loss = DamageProduct.objects.filter(
            created_date__year=year,
            created_date__month=month
        ).aggregate(total=Sum('loss_value'))['total'] or 0

        # Total losses
        total_losses = writeoff_loss + expiring_loss + damage_loss
        return round(total_losses, 2)





class WriteOffSerializerCal(serializers.Serializer):
    damaged_products = serializers.SerializerMethodField()
    expired_products = serializers.SerializerMethodField()

    def _get_month_range(self):
        start_of_month = now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_of_month.month == 12:
            end_of_month = start_of_month.replace(year=start_of_month.year + 1, month=1)
        else:
            end_of_month = start_of_month.replace(month=start_of_month.month + 1)
        return start_of_month, end_of_month

    def get_damaged_products(self, obj):
        start_of_month, end_of_month = self._get_month_range()
        damaged_items = InventoryWriteOff.objects.filter(
            reason__iexact="damaged",
            date__gte=start_of_month,
            date__lt=end_of_month
        )
        return [
            {
                "product": item.product.name,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "loss_value": item.loss_value,
                "note": item.note,
                "date": item.date,
                "created_by_name": item.created_by_name
            }
            for item in damaged_items
        ]

    def get_expired_products(self, obj):
        start_of_month, end_of_month = self._get_month_range()
        expired_items = InventoryWriteOff.objects.filter(
            reason__iexact="expired",
            date__gte=start_of_month,
            date__lt=end_of_month
        )
        return [
            {
                "product": item.product.name,
                "description": item.description,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "loss_value": item.loss_value,
                "note": item.note,
                "date": item.date,
                "created_by_name": item.created_by_name
            }
            for item in expired_items
        ]

