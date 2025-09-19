from rest_framework import serializers
from .models import ExpiringProduct, DamageProduct
from products.models import Product


class ExpiringProductSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    resale_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    note = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = ExpiringProduct
        fields = [
            'product',       # From frontend
            'resale_price',  # From frontend
            'quantity',      # From frontend
            'note',          # From frontend
        ]

    def validate(self, attrs):
        # Enforce strictly positive resale price
        if attrs['resale_price'] <= 0:
            raise serializers.ValidationError({"resale_price": "Resale price must be greater than 0."})
        # Enforce strictly positive quantity
        if attrs['quantity'] <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than 0."})
        # Disallow whitespace-only notes
        if not attrs['note'].strip():
            raise serializers.ValidationError({"note": "Note cannot be blank or whitespace."})
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']

        product_key = product.product_code if product.product_code else str(product.id)

        # Try to get existing ExpiringProduct or create new one
        expiring_obj, created = ExpiringProduct.objects.get_or_create(
            product_code=product_key,
            defaults={
                "staff": user,
                "product_name": product.name,
                "initial_unit_price": product.unit_price_vat_applied or 0,
                **validated_data,
            }
        )

        if not created:
            # Aggregate quantity
            expiring_obj.quantity += validated_data.get('quantity', 0)
            expiring_obj.save()

        return expiring_obj



class DamageProductSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    resale_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    quantity = serializers.IntegerField()
    note = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = DamageProduct
        fields = [
            'product',       # From frontend
            'resale_price',  # From frontend
            'quantity',      # From frontend
            'note',          # From frontend
        ]

    def validate(self, attrs):
        if attrs['resale_price'] <= 0:
            raise serializers.ValidationError({"resale_price": "Resale price must be greater than 0."})
        if attrs['quantity'] <= 0:
            raise serializers.ValidationError({"quantity": "Quantity must be greater than 0."})
        if not attrs['note'].strip():
            raise serializers.ValidationError({"note": "Note cannot be blank or whitespace."})
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        product = validated_data['product']

        product_key = product.product_code if product.product_code else str(product.id)

        # Try to get existing DamageProduct or create new one
        damage_obj, created = DamageProduct.objects.get_or_create(
            product_code=product_key,
            defaults={
                "staff": user,
                "product_name": product.name,
                "initial_unit_price": product.unit_price_vat_applied or 0,
                **validated_data,
            }
        )

        if not created:
            # Aggregate quantity
            damage_obj.quantity += validated_data.get('quantity', 0)
            # Optionally update resale_price or note if needed
            damage_obj.resale_price = validated_data.get('resale_price', damage_obj.resale_price)
            damage_obj.note = validated_data.get('note', damage_obj.note)
            damage_obj.save()

        return damage_obj




class ExpiringProductViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpiringProduct
        fields = [
            'id',
            'reference',
            'product',
            'product_name',
            'initial_unit_price',
            'resale_price',
            'quantity',
            'loss_value',
            'product_code',
            'staff_name',
            'created_date',
            'note',
            'description',
        ]


class DamageProductViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = DamageProduct
        fields = [
            'id',
            'reference',
            'product',
            'product_name',
            'initial_unit_price',
            'product_code',
            'resale_price',
            'quantity',
            'loss_value',
            'staff_name',
            'created_date',
            'note',
            'description',
        ]
