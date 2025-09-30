from rest_framework import serializers
from django.db.models import Sum
from django.utils.timezone import now
from calendar import monthrange
from .models import InventoryWriteOff
from django.db.models import F
from products.models import Product
from django.db.models import Q
from datetime import datetime
from sales.models import Sale, SaleItem
from price_slash.models import DamageProduct, ExpiringProduct
from datetime import datetime, timedelta


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
    previous_monthly_losses = serializers.SerializerMethodField() 
    previous_monthly_turnover = serializers.SerializerMethodField()
    all_time_losses = serializers.SerializerMethodField()


    def get_product_total_value(self, obj):
        # Base total product value
        total_value = Product.objects.aggregate(
            total=Sum(F('quantity') * (F('unit_price') + F('vat_value')))
        )['total'] or 0

        # Losses from ExpiringProduct
        expiring_loss = ExpiringProduct.objects.aggregate(
            total=Sum(F('loss_value') * F('quantity'))
        )['total'] or 0

        # Losses from DamageProduct
        damage_loss = DamageProduct.objects.aggregate(
            total=Sum(F('loss_value') * F('quantity'))
        )['total'] or 0

        # Adjusted total value
        adjusted_value = total_value - (expiring_loss + damage_loss)

        return float(adjusted_value)


    def get_total_product(self, obj):
        return int(Product.objects.count())

    def get_total_in_stock(self, obj):
        return int(Product.objects.filter(quantity__gt=0).count())


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
                "min_stock_threshold": p.min_stock_threshold,
                "unit_price": p.unit_price,
                "unit_buying_price": p.unit_buying_price,
                "description": p.description
            }
            for p in products
        ]
        

    def get_out_of_stock_products(self, obj):
        products = Product.objects.filter(quantity=0)
        return [
            {
                "id": p.id,
                "name": p.name,
                "unit_price": p.unit_price,
                "unit_buying_price": p.unit_buying_price,
                "description": p.description

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

        # Total sales amount for the month
        monthly_sales_total = Sale.objects.filter(
            sale_date__year=year,
            sale_date__month=month
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Average inventory for the month
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

        # Turnover rate
        turnover_rate = monthly_sales_total / average_inventory

        return float(round(turnover_rate, 2))

    def get_previous_monthly_turnover(self, obj):
        """
        Calculate inventory turnover rate for the previous month.
        """
        today = datetime.today()

        # Work out previous month correctly
        first_of_this_month = today.replace(day=1)
        prev_month_last_day = first_of_this_month - timedelta(days=1)
        month = prev_month_last_day.month
        year = prev_month_last_day.year

        # 1️⃣ Total sales amount for the previous month
        monthly_sales_total = Sale.objects.filter(
            sale_date__year=year,
            sale_date__month=month
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # 2️⃣ Average inventory for the previous month
        closing_inventory = Product.objects.aggregate(
            total_value=Sum(F('quantity') * F('unit_buying_price'))
        )['total_value'] or 0

        # Approximate opening inventory = closing inventory - sales total
        sold_value = monthly_sales_total
        opening_inventory = closing_inventory - sold_value

        average_inventory = max((opening_inventory + closing_inventory) / 2, 1)

        # 3️⃣ Turnover rate
        turnover_rate = monthly_sales_total / average_inventory

        return float(round(turnover_rate, 2))



    def get_monthly_losses(self, obj):
        """
        Calculate inventory losses for the current month.
        Breakdown: write-off, expiring, damaged, and total.
        """
        today = datetime.today()
        month = getattr(obj, 'month', today.month)
        year = getattr(obj, 'year', today.year)

        # 🔹 Write-off losses
        writeoff_loss = InventoryWriteOff.objects.filter(
            date__year=year,
            date__month=month
        ).aggregate(total=Sum('loss_value'))['total'] or 0

        # 🔹 Expiring product losses (price slash)
        expiring_loss = SaleItem.objects.filter(
            sale__sale_date__year=year,
            sale__sale_date__month=month,
            sale_type='expiring'
        ).aggregate(total=Sum(F('quantity') * F('cost_price') - F('amount')))['total'] or 0

        # 🔹 Damaged product losses (price slash)
        damaged_loss = SaleItem.objects.filter(
            sale__sale_date__year=year,
            sale__sale_date__month=month,
            sale_type='damaged'
        ).aggregate(total=Sum(F('quantity') * F('cost_price') - F('amount')))['total'] or 0

        total_losses = writeoff_loss + expiring_loss + damaged_loss

        return {
            "writeoff_loss": float(round(writeoff_loss, 2)),
            "expiring_loss": float(round(expiring_loss, 2)),
            "damaged_loss": float(round(damaged_loss, 2)),
            "total_loss": float(round(total_losses, 2))
        }


    def get_previous_monthly_losses(self, obj):
        """
        Calculate inventory losses for the previous month.
        Breakdown: write-off, expiring, damaged, and total.
        """
        today = datetime.today()
        # Work out previous month correctly
        first_of_this_month = today.replace(day=1)
        prev_month_last_day = first_of_this_month - timedelta(days=1)
        month = prev_month_last_day.month
        year = prev_month_last_day.year

        # 🔹 Write-off losses
        writeoff_loss = InventoryWriteOff.objects.filter(
            date__year=year,
            date__month=month
        ).aggregate(total=Sum('loss_value'))['total'] or 0

        # 🔹 Expiring product losses
        expiring_loss = SaleItem.objects.filter(
            sale__sale_date__year=year,
            sale__sale_date__month=month,
            sale_type='expiring'
        ).aggregate(total=Sum(F('quantity') * F('cost_price') - F('amount')))['total'] or 0

        # 🔹 Damaged product losses
        damaged_loss = SaleItem.objects.filter(
            sale__sale_date__year=year,
            sale__sale_date__month=month,
            sale_type='damaged'
        ).aggregate(total=Sum(F('quantity') * F('cost_price') - F('amount')))['total'] or 0

        total_losses = writeoff_loss + expiring_loss + damaged_loss

        return {
            "writeoff_loss": float(round(writeoff_loss, 2)),
            "expiring_loss": float(round(expiring_loss, 2)),
            "damaged_loss": float(round(damaged_loss, 2)),
            "total_loss": float(round(total_losses, 2))
        }

    def get_all_time_losses(self, obj=None):
        """
        Calculate all-time inventory losses.
        Breakdown: write-off, expiring, damaged, and total.
        """

        # 🔹 Write-off losses
        writeoff_loss = InventoryWriteOff.objects.aggregate(
            total=Sum('loss_value')
        )['total'] or 0

        # 🔹 Expiring product losses (price slash)
        expiring_loss = SaleItem.objects.filter(
            sale_type='expiring'
        ).aggregate(
            total=Sum(F('quantity') * F('cost_price') - F('amount'))
        )['total'] or 0

        # 🔹 Damaged product losses (price slash)
        damaged_loss = SaleItem.objects.filter(
            sale_type='damaged'
        ).aggregate(
            total=Sum(F('quantity') * F('cost_price') - F('amount'))
        )['total'] or 0

        total_losses = writeoff_loss + expiring_loss + damaged_loss

        return {"total_loss": float(round(total_losses, 2))}

        



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

