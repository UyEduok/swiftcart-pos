from rest_framework import serializers
from decimal import Decimal, InvalidOperation
from .models import Product, Category, Unit, Supplier, ProductBatch, StockHistory, ProductBatch, SupplierProductSupply
from decimal import Decimal, InvalidOperation
from django.db.models import F
from django.contrib.auth import get_user_model
import re
from django.utils import timezone
from django.db import transaction
from rest_framework import serializers



User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name']

    def get_full_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.username


class ProductSerializer(serializers.ModelSerializer):
    product_code = serializers.CharField(required=True)
    name = serializers.CharField(required=True)
    batch_number = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    description = serializers.CharField(allow_blank=True, required=False)
    unit_buying_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    markup_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)
    discount_quantity = serializers.IntegerField(required=False, default=0)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=Decimal("0.00"))
    quantity = serializers.IntegerField(required=True, min_value=1)
    min_stock_threshold = serializers.IntegerField(required=True, min_value=1)

    expiry_date = serializers.DateField(required=False, allow_null=True,)
    expiry_min_threshold_days = serializers.IntegerField(required=False, allow_null=True)

    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)
    unit = serializers.PrimaryKeyRelatedField(queryset=Unit.objects.all(), required=True)
    measurement_value = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    measurement_unit = serializers.CharField(required=False, allow_blank=True)
    supplier_id = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    apply_vat = serializers.BooleanField(required=False, default=False)
    vat_value = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    product_image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Product
        fields = [
            'product_code', 'name', 'batch_number', 'description', 'unit_buying_price', 'markup_percentage', 'unit_price',
            'discount_quantity', 'discount_percentage', 'discount', 'supplier_id',
            'quantity', 'min_stock_threshold', 'expiry_date', 'expiry_min_threshold_days', 'category', 'unit',
            'measurement_value', 'measurement_unit', 'apply_vat', 'vat_value', 'product_image',
        ]


    def validate(self, data):
        """
        Keep existing validations but require expiry fields when batch_number is provided.
        """
        buy_price = data.get('unit_buying_price')
        markup = data.get('markup_percentage')
        unit_price = data.get('unit_price')
        discount_percent = data.get('discount_percentage')
        discount = data.get('discount')
        apply_vat = data.get('apply_vat')
        vat_value = data.get('vat_value')

        batch = data.get('batch_number')
        expiry_date = data.get('expiry_date')
        expiry_threshold = data.get('expiry_min_threshold_days')
        measurement_value = data.get('measurement_value')
        measurement_unit = data.get('measurement_unit')
        supplier_id = data.get('supplier_id')
        description = data.get('description')


        # Only allow empty description if measurement_value and measurement_unit are provided
        if not description:
            if not (measurement_value and measurement_unit):
                raise serializers.ValidationError(
                    "To leave description empty, both measurement_value and measurement_unit must be provided."
                )

        # Require expiry fields if batch_number is present (not blank)
        if batch:
            if not expiry_date:
                raise serializers.ValidationError({'expiry_date': "expiry_date is required when batch_number is provided."})
            if expiry_threshold is None:
                raise serializers.ValidationError({'expiry_min_threshold_days': "expiry_min_threshold_days is required when batch_number is provided."})

        # VAT validation
        if apply_vat:
            if vat_value is None:
                raise serializers.ValidationError({'vat_value': "vat_value is required when apply_vat is True."})
            if vat_value <= 0:
                raise serializers.ValidationError({'vat_value': "vat_value must be greater than 0."})

        # Auto-correct unit_price if markup given
        if markup is not None and buy_price is not None:
            try:
                expected_unit_price = buy_price + (buy_price * (markup / Decimal('100')))
                data['unit_price'] = expected_unit_price.quantize(Decimal('0.01'))
            except (TypeError, InvalidOperation):
                pass

        # Auto-correct discount if discount_percent given
        if discount_percent is not None and unit_price is not None:
            try:
                expected_discount_amount = unit_price * (discount_percent / Decimal('100'))
                data['discount'] = expected_discount_amount.quantize(Decimal('0.01'))
            except (TypeError, InvalidOperation):
                pass

        # Validate all required decimal/number fields > 0 except markup, bulk_discount_percentage, sub_bulk_discount_percentage
        required_positive_fields = {
            'unit_buying_price': buy_price,
            'unit_price': data.get('unit_price'),
            'discount_quantity': data.get('discount_quantity'),
            'discount': data.get('discount'),
            'quantity': data.get('quantity'),
            'min_stock_threshold': data.get('min_stock_threshold'),
        }
        for field_name, value in required_positive_fields.items():
            if value is None or (isinstance(value, (int, float, Decimal)) and value <= 0):
                raise serializers.ValidationError({field_name: f"{field_name} must be greater than 0."})

        return data

    def create(self, validated_data):
        """
        Create/update Product as before, but also create/update the ProductBatch
        when a write-only 'batch_number' is supplied in the incoming data.

        Important:
        - We pop 'batch_number' before creating Product so it isn't passed to Product.objects.create
        - We use request.user from serializer context to set created_by/updated_by on the batch
        """

        # Try to fetch Supplier instance if supplier_id provided


        request = self.context.get('request') if self.context else None
        user = getattr(request, 'user', None)

        supplier_id = validated_data.pop('supplier_id', None)

        # remove batch_number from data so it does not break Product creation (Product has no batch_number field)
        batch_number = validated_data.pop('batch_number', None)

        # Use quantity_purchase for batch quantity increment
        quantity_to_add = validated_data.get('quantity', 0)

        # Keep expiry info if provided — will be stored on batch
        expiry_date = validated_data.get('expiry_date', None)
        expiry_threshold = validated_data.get('expiry_min_threshold_days', None)

        # existing product update logic (based on product_code)
        code = validated_data.get('product_code')
        product = Product.objects.filter(product_code=code).first()


        if product:
            # Add quantity_purchase instead of overwriting
            new_quantity = validated_data.pop('quantity', 0)  # remove quantity_purchase from validated_data

            # Update all other fields
            for attr, value in validated_data.items():
                setattr(product, attr, value)

            # Add new quantity to existing quantity_purchase
            product.quantity = (product.quantity or 0) + new_quantity

            product.save()
        else:
            product = Product.objects.create(**validated_data)



        # handle batch creation/update
        if batch_number:
            # ProductBatch is imported at top; if not, import here:
            # from .models import ProductBatch

            batch, created = ProductBatch.objects.get_or_create(
                product=product,
                batch_number=batch_number,
                defaults={
                    'quantity_left': quantity_to_add,
                    'expiry_date': expiry_date,
                    'expiry_min_threshold_days': expiry_threshold,
                    'created_by': user,
                }
            )

            if not created:
                # Atomic increment + set updated_by
                ProductBatch.objects.filter(pk=batch.pk).update(
                    quantity_left=F('quantity_left') + quantity_to_add,
                    updated_by=user
                )
                # refresh to reflect updated values if needed
                batch.refresh_from_db()


        return product


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'product_count']
    
    def validate_name(self, value):
        # Exclude current instance when editing
        qs = Category.objects.exclude(pk=getattr(self.instance, 'pk', None))
        if qs.filter(name__iexact=value).exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value

class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = '__all__'

class ProductViewSerializer(serializers.ModelSerializer):
    unit_price = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True
    )
    measurement_value = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True
    )
    quantity = serializers.IntegerField(read_only=True)
    unit_buying_price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True)
    markup_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True, coerce_to_string=False)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True, coerce_to_string=False)
    unit = serializers.CharField(read_only=True)
    min_stock_threshold = serializers.IntegerField(read_only=True)
    discount_quantity = serializers.IntegerField(read_only=True)
    discount = serializers.DecimalField(
        max_digits=10, decimal_places=2, coerce_to_string=False, read_only=True
    )
    vat_value = serializers.DecimalField(
        max_digits=5, decimal_places=2, coerce_to_string=False, read_only=True
    )

    class Meta:
        model = Product
        fields = [
            'id',
            'unit_price',
            'product_code',
            'name',
            'description',
            'unit',
            'measurement_value',
            'measurement_unit',
            'quantity',
            'min_stock_threshold',
            'discount_quantity',
            'discount',
            'status',
            'apply_vat',
            'vat_value',
            'product_image',
            'unit_buying_price',
            'markup_percentage',
            'unit',
            'discount_percentage',
        ]
        read_only_fields = fields 

    def get_category_name(self, obj):
        return obj.category.name if obj.category else None



class StockHistorySerializer(serializers.ModelSerializer):
    action_by = UserSerializer(read_only=True)
    product = ProductSerializer(read_only=True)

    class Meta:
        model = StockHistory
        fields = '__all__'


class StockHistoryWriteSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=StockHistory._meta.get_field('product').related_model.objects.all(),
        required=True
    )
    quantity = serializers.IntegerField(required=True)
    action = serializers.ChoiceField(choices=StockHistory.ACTION_CHOICES, required=True)
    notes = serializers.CharField(required=True)

    class Meta:
        model = StockHistory
        fields = ['product', 'quantity', 'action', 'notes']

    def validate_quantity(self, value):
        if value == 0:
            raise serializers.ValidationError("Quantity cannot be zero.")
        return value

    def create(self, validated_data):
        validated_data['action_by'] = self.context['request'].user
        return super().create(validated_data)


class SupplierProductSupplySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.CharField(source='product.unit_buying_price', read_only=True)

    class Meta:
        model = SupplierProductSupply
        fields = ["id", 'product', 'quantity_supplied', 'total_amount', 'supply_date', 'product_name', 'product_price' ]


class SupplierSerializer(serializers.ModelSerializer):
    supplies = SupplierProductSupplySerializer(many=True, read_only=True)

    class Meta:
        model = Supplier
        fields = '__all__'


    def validate_phone(self, value):
        """If phone is provided, enforce numeric pattern"""
        if value and not re.match(r'^\+?\d{7,15}$', value):
            raise serializers.ValidationError("Phone number must be between 7–15 digits and may start with '+'.")
        return value

    def validate_email(self, value):
        """If email is provided, enforce proper email format"""
        if value and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', value):
            raise serializers.ValidationError("Invalid email format.")
        return value

    def validate_account_number(self, value):
        """If account number is provided, enforce numeric only"""
        if value and not re.match(r'^\d{6,20}$', value):
            raise serializers.ValidationError("Account number must be 6–20 digits.")
        return value
    
    def validate_name(self, value):
        if value:
            value = " ".join([word.capitalize() for word in value.split()])
        return value

class ProductBatchSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    mark_sold = serializers.BooleanField(write_only=True, required=False, default=False)
    mark_expired = serializers.BooleanField(write_only=True, required=False, default=False)
    expiry_min_threshold_days = serializers.IntegerField(required=False, min_value=0)

    class Meta:
        model = ProductBatch
        fields = [
            'id', 'product', 'quantity_left', 'expiry_date', 
            'expiry_min_threshold_days', 'mark_sold', 'mark_expired', 'status',
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # If it's calculated dynamically, put logic here:
        if hasattr(instance, 'expiry_min_threshold_days'):
            rep['expiry_min_threshold_days'] = instance.expiry_min_threshold_days
        return rep

class CategoryWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("Category name cannot be empty.")
        return value


class ProductUpdateSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), source='id')
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), write_only=True, required=False, allow_null=True)
    batch = serializers.CharField(write_only=True, required=False, allow_blank=True, allow_null=True)
    expiry_date = serializers.DateField(write_only=True, required=False, allow_null=True)
    expiry_threshold = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    purchased_qty = serializers.IntegerField(write_only=True, required=True, min_value=1)

    class Meta:
        model = Product
        fields = [
            "product",
            "batch",
            "expiry_date",
            "expiry_threshold",
            "purchased_qty",
            "supplier",
        ]

    def validate(self, data):
        # Only validate trio if at least one has a real value
        trio = ["batch", "expiry_date", "expiry_threshold"]
        provided = [data.get(f) not in (None, "") for f in trio]
        
        if any(provided) and not all(provided):
            raise serializers.ValidationError(
                {"batch_fields": "If any of batch, expiry_date, or expiry_threshold is provided, all three must be provided."}
            )

        return data
    def update(self, instance, validated_data):
        request = self.context.get("request")
        user = getattr(request, "user", None)

        supplier = validated_data.pop("supplier", None)
        batch_number = validated_data.pop("batch", None)
        expiry_date = validated_data.pop("expiry_date", None)
        expiry_threshold = validated_data.pop("expiry_threshold", None)
        purchased_qty = int(validated_data.pop("purchased_qty", 0) or 0)

        with transaction.atomic():
            # 1) increment stock only
            if purchased_qty > 0:
                Product.objects.filter(pk=instance.pk).update(quantity=F("quantity") + purchased_qty)
                instance.refresh_from_db(fields=["quantity"])

            # 2) batch management
            if batch_number and expiry_date and expiry_threshold:
                batch_qs = ProductBatch.objects.select_for_update().filter(
                    product=instance, batch_number=batch_number
                )
                if batch_qs.exists():
                    batch_obj = batch_qs.first()
                    if (
                        batch_obj.expiry_date != expiry_date
                        or batch_obj.expiry_min_threshold_days != expiry_threshold
                    ):
                        raise serializers.ValidationError(
                            f"Batch '{batch_number}' exists but expiry date or threshold does not match."
                        )
                    batch_obj.quantity_left = F("quantity_left") + purchased_qty
                    batch_obj.updated_by = user
                    batch_obj.save(update_fields=["quantity_left", "updated_by", "updated_at"])
                    batch_obj.refresh_from_db(fields=["quantity_left"])
                else:
                    ProductBatch.objects.create(
                        product=instance,
                        batch_number=batch_number,
                        quantity_left=purchased_qty,
                        expiry_date=expiry_date,
                        expiry_min_threshold_days=expiry_threshold,
                        created_by=user,
                    )

            # 3) stock history
            if purchased_qty > 0:
                note = f"Stock received by {(user.get_full_name() or user.first_name or user.username) if user else 'system'}"
                StockHistory.objects.create(
                    product=instance,
                    action="Stock In",
                    quantity=purchased_qty,
                    action_by=user,
                    notes=note,
                )

            # 4) supplier tracking
            if supplier:
                supplier_product, created = SupplierProductSupply.objects.get_or_create(
                    supplier=supplier,
                    product=instance,
                    defaults={"quantity_supplied": purchased_qty}
                )
                if not created:
                    supplier_product.quantity_supplied += purchased_qty
                    supplier_product.save()

        #always return the instance
        return instance

