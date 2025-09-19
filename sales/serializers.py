from rest_framework import serializers
from products.models import Product
from .models import Customer 
from price_slash.models import ExpiringProduct, DamageProduct  
from django.db import transaction
from decimal import Decimal
from .models import Sale, SaleItem
from django.contrib.auth.models import User
from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from rest_framework import serializers
from .models import Sale, SaleItem, Product, Receipt
from price_slash.models import DamageProduct, ExpiringProduct




class ProductSalesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            'id', 
            'name', 
            'product_code', 
            'apply_vat', 
            'vat_value', 
            'unit_price', 
            'description',
            "discount",
            "discount_quantity"
        ]


class CustomerBasicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name']


class ExpiringProductSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = ExpiringProduct
        fields = ['id', 'product','product_code', 'product_name', 'initial_unit_price', 'resale_price', 'quantity', 'description']

class DamagedProductSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = DamageProduct
        fields = ['id', 'product','product_code', 'product_name', 'initial_unit_price', 'resale_price', 'quantity', 'description' ]


class CartKeySerializer(serializers.Serializer):
    checker = serializers.CharField()
    sale_type = serializers.ChoiceField(choices=['sales', 'damaged', 'expiring'])
    quantity = serializers.IntegerField(min_value=1)


class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'phone', 'email', 'address', 'status',
                  'created_by', 'updated_by', 'created_by', 'updated_by',
                  'created_at', 'updated_at', 'badge']
        read_only_fields = ['id', 'status', 'created_by', 'updated_by', 
                            'created_by', 'updated_by', 'created_at', 'updated_at', 'badge']

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['created_by'] = user
        validated_data['updated_by'] = user
        # Names will auto-populate from save() in model
        return super().create(validated_data)

    def update(self, instance, validated_data):
        instance.updated_by = self.context['request'].user
        # updated_by_name will auto-populate from save() in model
        return super().update(instance, validated_data)


class SaleItemSerializer(serializers.ModelSerializer):
    checker = serializers.CharField(write_only=True)
    sale_type = serializers.ChoiceField(choices=SaleItem._meta.get_field('sale_type').choices)
    quantity = serializers.IntegerField()
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    vat_value = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default=Decimal("0.00"))
    discount_value = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, default=Decimal("0.00"))
    amount = serializers.DecimalField(max_digits=14, decimal_places=2)
    cost_price = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)


    class Meta:
        model = SaleItem
        fields = [
            "checker",
            "sale_type",
            "quantity",
            "unit_price",
            "vat_value",
            "discount_value",
            "amount",
            "cost_price",
            "profit",
        ]

    def to_internal_value(self, data):
        # Convert numeric strings/floats to Decimals
        for key in ["unit_price", "vat_value", "discount_value", "amount"]:
            if key in data and isinstance(data[key], (float, int, str)):
                data[key] = str(
                    Decimal(str(data[key])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                )
        return super().to_internal_value(data)

    def create(self, validated_data):
        receipt_amount = validated_data.pop("raw_amount", validated_data.get("amount", Decimal("0.00")))
        checker = validated_data.pop("checker", None)
        sale_type = validated_data.get("sale_type")
        product = None

        # Extract product id
        try:
            product_id = int(checker.split("-")[0])
        except (ValueError, AttributeError, IndexError):
            raise serializers.ValidationError({"checker": "Invalid checker format"})

        # Resolve product
        temp_expiring_id = None
        temp_damage_id = None
        if sale_type == "sales":
            product = Product.objects.get(id=product_id)
        elif sale_type == "damaged":
            dmg = DamageProduct.objects.get(id=product_id)
            product = dmg.product
            temp_damage_id = dmg.id
        elif sale_type == "expiring":
            exp = ExpiringProduct.objects.get(id=product_id)
            product = exp.product
            temp_expiring_id = exp.id
        else:
            raise serializers.ValidationError({"sale_type": "Invalid sale type"})

        # Compute DB amount
       
        raw_amount = validated_data.get("amount", Decimal("0.00"))
        vat_value = validated_data.get("vat_value", Decimal("0.00"))
        discount_value = validated_data.get("discount_value", Decimal("0.00"))
        db_amount = raw_amount + vat_value - discount_value

        validated_data["product"] = product
        validated_data["amount"] = db_amount

        cost_price = product.unit_buying_price
        discount = Decimal("0.00")

        # Apply discount only if quantity meets/exceeds discount_quantity
        if validated_data["quantity"] >= product.discount_quantity and product.discount_quantity > 0:
            discount = product.discount

        validated_data["cost_price"] = cost_price
        validated_data["profit"] = (
            (validated_data["unit_price"] - cost_price - discount) * validated_data["quantity"]
        )



        # Create SaleItem
        sale_item = SaleItem.objects.create(**validated_data)

        # Attach temporary IDs for view usage (not saved to DB)
        if temp_expiring_id:
            sale_item.expiring_product_id = temp_expiring_id
        if temp_damage_id:
            sale_item.damage_product_id = temp_damage_id
        print(f"Receipt amount (from frontend/raw): {receipt_amount}")
        print(f"Amount (DB value): {db_amount}")
        return sale_item


class SaleSerializer(serializers.ModelSerializer):
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(),
        source="customer",
        required=False,
        allow_null=True
    )
    grand_total = serializers.DecimalField(max_digits=14, decimal_places=2, write_only=True)
    total_vat = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_discount = serializers.DecimalField(max_digits=14, decimal_places=2)
    items = SaleItemSerializer(many=True)
    total_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_profit = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "customer_id",
            "payment_type",
            "grand_total",
            "total_vat",
            "total_discount",
            "items",
            "total_cost", 
            "total_profit",
        ]

    def to_internal_value(self, data):
        # Convert top-level totals to Decimals
        for key in ["grand_total", "total_vat", "total_discount"]:
            if key in data and isinstance(data[key], (float, int, str)):
                data[key] = str(
                    Decimal(str(data[key])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                )
        return super().to_internal_value(data)

    def create(self, validated_data):
        request = self.context.get("request")
        user = request.user if request else None

        items_data = validated_data.pop("items", [])
        grand_total = validated_data.pop("grand_total")

        with transaction.atomic():
            # Create Sale
            sale = Sale.objects.create(
                staff=user,
                total_amount=grand_total,
                **validated_data
            )

            total_cost = Decimal("0.00")
            total_profit = Decimal("0.00")

            # Use SaleItemSerializer to ensure custom logic runs
            for item_data in items_data:
                serializer = SaleItemSerializer(data=item_data, context={"request": request})
                serializer.is_valid(raise_exception=True)
                sale_item = serializer.save(sale=sale)

                # accumulate totals
                total_cost += sale_item.cost_price * sale_item.quantity
                total_profit += sale_item.profit

            # update sale totals
            sale.total_cost = total_cost
            sale.total_profit = total_profit
            sale.save()

        return sale

class ReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.name", default=None, read_only=True)

    class Meta:
        model = Receipt
        fields = ["id", "customer_name", "created_at", "file"]










