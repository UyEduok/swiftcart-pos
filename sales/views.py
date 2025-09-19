from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Customer
from products.models import Product, ProductBatch, StockHistory
from .serializers import ProductSalesSerializer, CustomerBasicSerializer
from price_slash.models import ExpiringProduct, DamageProduct
from .serializers import ExpiringProductSerializer, DamagedProductSerializer
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .serializers import SaleItemSerializer, SaleSerializer
from django.db import transaction
from .models import Sale, SaleItem, Receipt
from .serializers import CustomerSerializer, CartKeySerializer, ReceiptSerializer
from django.db.models import Sum, F
from django.utils.timezone import now
from collections import defaultdict
from sales.utils import generate_receipt
from django.core.files.base import ContentFile
from rest_framework.exceptions import ValidationError
from .utils import get_cashier_sales_summary
from .serializers import CustomerSerializer
from .utils import print_pdf_file
from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal, ROUND_HALF_UP
from django.utils.timezone import localdate
from .models import Receipt


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_products(request):
    products = Product.objects.all()
    serializer = ProductSalesSerializer(products, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sales_customers(request):
    customers = Customer.objects.all()
    serializer = CustomerBasicSerializer(customers, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expiring_and_damaged_products(request):
    expiring_items = ExpiringProduct.objects.select_related('product').all()
    damaged_items = DamageProduct.objects.select_related('product').all()
    
    expiring_data = ExpiringProductSerializer(expiring_items, many=True).data
    damaged_data = DamagedProductSerializer(damaged_items, many=True).data
    user = request.user
    summary = get_cashier_sales_summary(user)
    return Response({
        'expiring_products': expiring_data,
        'damaged_products': damaged_data,
        'summary': summary
    })



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_cart(request):
    serializer = CartKeySerializer(data=request.data.get('items', []), many=True)
    serializer.is_valid(raise_exception=True)

    validated_items = []
    sub_total = 0.0
    total_vat = 0.0
    total_discount = 0.0
    grand_total = 0.0

    for item in serializer.validated_data:
        checker = item.get('checker', '')          
        sale_type = item.get('sale_type', '')      
        requested_qty = item.get('quantity', 0)

        # Parse product id from checker
        try:
            product_id_str, _ = checker.split('-')
            product_id = int(product_id_str)
        except Exception:
            validated_items.append({
                "checker": checker,
                "sale_type": sale_type,
                "quantity": 0,
                "unit_price": 0,
                "amount": 0,
                "vat_value": 0,
                "discount_value": 0,
                "message": "Invalid key format"
            })
            continue

        unit_price = 0.0
        amount = 0.0
        vat = 0.0
        discount = 0.0
        message = None
        product_instance = None

        # Retail or Bulk (Product table)
        if sale_type == "sales":
            try:
                product_instance = Product.objects.get(id=product_id)

                unit_price = float(getattr(product_instance, "unit_price", 0.0))


                discount_quantity = int(getattr(product_instance, "discount_quantity", 0))

                # Apply discount only if product has discount_quantity set and request meets/exceeds it
                if discount_quantity > 0 and requested_qty >= discount_quantity:
                    discount = float(getattr(product_instance, "discount", 0.0)) * requested_qty
                    print(f"Applied discount: {discount} for product {product_instance.id} with quantity {discount_quantity}")

                # VAT (per unit × qty)
                vat = 0.0
                if getattr(product_instance, "apply_vat", False):
                    vat = float(getattr(product_instance, "vat_value", 0.0)) * requested_qty

                # Final amount = (unit_price × qty) - discount
                amount = unit_price * requested_qty

            except Product.DoesNotExist:
                message = "Product not found"


        # Damaged (DamageProduct table)
        elif sale_type == 'damaged':
            try:
                product_instance = DamageProduct.objects.get(id=product_id)
                available_qty = getattr(product_instance, 'quantity', 0)
                if requested_qty > available_qty:
                    requested_qty = available_qty
                    message = f"Quantity adjusted to available stock ({available_qty})"
                if requested_qty == 0:
                    continue
                unit_price = float(getattr(product_instance, 'resale_price', 0.0))
                amount = unit_price * requested_qty
            except DamageProduct.DoesNotExist:
                message = "Damaged product not found"

        # Expiring (ExpiringProduct table)
        elif sale_type == 'expiring':
            try:
                product_instance = ExpiringProduct.objects.get(id=product_id)
                available_qty = getattr(product_instance, 'quantity', 0)
                if requested_qty > available_qty:
                    requested_qty = available_qty
                    message = f"Quantity adjusted to available stock ({available_qty})"
                if requested_qty == 0:
                    continue
                unit_price = float(getattr(product_instance, 'resale_price', 0.0))
                amount = unit_price * requested_qty
            except ExpiringProduct.DoesNotExist:
                message = "Expiring product not found"

        # Update totals only if product exists
        if product_instance:
            sub_total += amount
            total_vat += vat
            total_discount += discount
            grand_total = sub_total + total_vat - total_discount
        

        validated_items.append({
            "checker": checker,
            "sale_type": sale_type,
            "quantity": requested_qty,
            "unit_price": unit_price,
            "amount": amount,
            "vat_value": vat,
            "discount_value": discount,
            "message": message
        })

    return Response({
        "validated_items": validated_items,
        "totals": {
            "sub_total": sub_total,
            "total_vat": total_vat,
            "total_discount": total_discount,
            "grand_total": grand_total
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_customer(request):
    serializer = CustomerSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        customer = serializer.save()
        return Response({
            "success": True,
            "message": "Customer created successfully",
            "customer": CustomerSerializer(customer).data
        }, status=status.HTTP_201_CREATED)
    return Response({
        "success": False,
        "message": "Error creating customer",
        "errors": serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_sale(request):
    serializer = SaleSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)

    with transaction.atomic():
        # Save Sale + SaleItems via serializer
        sale = serializer.save()
        user = request.user
        items = sale.items.all()

        for item in items:
            product = Product.objects.select_for_update().get(pk=item.product_id)

            qty_to_deduct = item.quantity
            stock_flag = False  

            if product.quantity >= qty_to_deduct:
                product.quantity -= qty_to_deduct
            else:
                product.quantity = 0
                stock_flag = True
            product.save(update_fields=['quantity'])

            # Handle expiring and damaged product deduction
            if item.sale_type == "expiring":
                exp_item = ExpiringProduct.objects.select_for_update().filter(
                    id=getattr(item, 'expiring_product_id', None)
                ).first()
                if not exp_item:
                    raise ValidationError({
                        "cart": f"Product {item.product.name} no longer exists in the Expiring table. Please remove it from cart."
                    })

                if item.quantity > exp_item.quantity:
                    raise ValidationError({
                        "cart": f"Product {item.product.name} has only {exp_item.quantity} units available in the Expiring table. Reduce quantity in cart."
                    })

                # Safe to deduct
                exp_item.quantity -= item.quantity
                exp_item.save(update_fields=['quantity'])
                if exp_item and exp_item.pk is not None and exp_item.quantity == 0:
                    exp_item.delete()


            elif item.sale_type == "damaged":
                dmg_item = DamageProduct.objects.select_for_update().filter(
                    id=getattr(item, 'damage_product_id', None)
                ).first()

                if not dmg_item:
                    raise ValidationError({
                        "cart": f"Product {item.product.name} no longer exists in the Damaged table. Please remove it from cart."
                    })

                if item.quantity > dmg_item.quantity:
                    raise ValidationError({
                        "cart": f"Product {item.product.name} has only {dmg_item.quantity} units available in the Damaged table. Reduce quantity in cart."
                    })

                # Safe to deduct
                dmg_item.quantity -= item.quantity
                dmg_item.save(update_fields=['quantity'])
                if dmg_item and dmg_item.pk is not None and dmg_item.quantity == 0:
                    dmg_item.delete()



            # Deduct from batches (for retail/bulk sales)
            remaining_qty = qty_to_deduct
            batches = product.batches.filter(quantity_left__gt=0).order_by('expiry_date')
            for batch in batches:
                if remaining_qty <= 0:
                    break
                if batch.quantity_left >= remaining_qty:
                    batch.quantity_left -= remaining_qty
                    remaining_qty = 0
                    batch.save(update_fields=['quantity_left'])
                else:
                    remaining_qty -= batch.quantity_left
                    batch.quantity_left = 0
                    batch.save(update_fields=['quantity_left'])

            # Create StockHistory
            sale_note = {
                'sales': 'Sales',
                'damage': 'Damaged',
                'expiring': 'Expiring'
            }.get(item.sale_type, "Sale")

            username = user.get_full_name() or user.username or "Cashier"
            notes = f"{sale_note} sales made by {username}"
            if stock_flag:
                notes += " (Stock imbalance)"

            StockHistory.objects.create(
                product=product,
                action='Sold',
                quantity=item.quantity,
                action_by=user,
                notes=notes
            )

        discount = Decimal(request.data.get('total_discount', "0.00"))
        vat = Decimal(request.data.get('total_vat', "0.00"))

        # subtotal is amount minus discount plus vat
        # Compute items with amount
        items_list = []
        subtotal = Decimal("0.00")

        for item in items:
            amount = item.unit_price * item.quantity
            subtotal += amount
            items_list.append({
                "description": f"{item.product.description} {' (EP)' if item.sale_type == 'expiring' else ' (DM)' if item.sale_type == 'damaged' else ''}",
                "qty": item.quantity,
                "unit_price": item.unit_price,
                "amount": amount,
            })

        # Get discounts, VAT, grand total
        total_discount = Decimal(request.data.get('total_discount', "0.00"))
        total_vat = Decimal(request.data.get('total_vat', "0.00"))
        grand_total = subtotal + total_vat - total_discount

        sale_data = {
            "receipt_no": sale.id,
            "cashier_name": username,
            "datetime": sale.sale_date.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": getattr(sale.customer, "name", "N/A") if sale.customer else "N/A",
            "customer_phone": getattr(sale.customer, "phone", "N/A") if sale.customer else "N/A",
            "items": items_list,
            "subtotal": subtotal,
            "discount": total_discount,
            "vat": total_vat,
            "grand_total": grand_total,
            "reference": sale.reference,
        }


        # Convert all numeric values to Decimal safely
        for key in ['subtotal', 'discount', 'vat', 'grand_total']:
            sale_data[key] = Decimal(str(sale_data.get(key, '0.00'))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        #save to Sale safely
        sale.total_amount = sale_data['grand_total']
        sale.total_vat = sale_data['vat']
        sale.total_discount = sale_data['discount']
        sale.save(update_fields=['total_amount', 'total_vat', 'total_discount'])

        
        # Generate PDF
        pdf_buffer = generate_receipt(sale_data)

        # Make sure buffer is at the beginning
        pdf_buffer.seek(0)

        # Save Receipt
        receipt, created = Receipt.objects.get_or_create(sale=sale)
        if sale.customer:  
            receipt.customer = sale.customer  
        receipt.sales_reference = sale.reference  
        receipt.receipt_number = sale.id   
        receipt.file.save(
            f"receipt_{sale.id}.pdf",
            ContentFile(pdf_buffer.read()),
            save=False
        )
        pdf_buffer.close() 

        receipt.save()
        receipt.refresh_from_db()

        # Build URL for browser access
        receipt_url = request.build_absolute_uri(receipt.file.url)


        try:
            summary = get_cashier_sales_summary(user)
        except Exception as e:
            summary = {}
            print("Error generating summary:", e)

        return Response({
            "success": True,
            "message": "Sale created successfully",
            "sale": SaleSerializer(sale).data,
            "summary": summary,
            "receipt_url": receipt_url
        }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_todays_receipts(request):
    today = localdate()
    receipts = (
        Receipt.objects
        .filter(created_at__date=today)  
        .order_by('-created_at')[:5]
    )

    serializer = ReceiptSerializer(receipts, many=True, context={"request": request})
    return Response({"receipts": serializer.data})
