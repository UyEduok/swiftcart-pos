from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions, throttling
from .serializers import ProductSerializer, SupplierSerializer, CategorySerializer, UnitSerializer
from .models import Product, StockHistory, SupplierProductSupply
from django.utils import timezone
from .models import Supplier, Category, Unit
from django.db.models import Count
from .serializers import StockHistorySerializer
from .models import ProductBatch
from .serializers import ProductBatchSerializer
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle
from .serializers import StockHistoryWriteSerializer
from django.shortcuts import get_object_or_404
from .serializers import CategoryWriteSerializer
from django.utils import timezone
from inventory_writeoffs.models import InventoryWriteOff
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework import generics
from django.db.models import Q
from .serializers import ProductUpdateSerializer
from datetime import datetime, time
from rest_framework.pagination import PageNumberPagination
from rest_framework.decorators import api_view, throttle_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import UserRateThrottle  # or your SupplierThrottle
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from .models import StockHistory
from .serializers import StockHistorySerializer
from datetime import datetime
from rest_framework import generics, permissions
from .models import Product
from .serializers import ProductViewSerializer

class SupplierThrottle(UserRateThrottle):
    rate = '20/min'  #: 5 requests per minute

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_batch_list(request):
    batches = ProductBatch.objects.all()
    serializer = ProductBatchSerializer(batches, many=True)
    return Response(serializer.data)


class ProductCreateUpdateThrottle(throttling.UserRateThrottle):
    rate = '20/min'

from django.db import transaction

class ProductCreateUpdateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ProductCreateUpdateThrottle]

    def post(self, request, *args, **kwargs):
        with transaction.atomic():  # <-- atomic block starts here
            serializer = ProductSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                validated_data = serializer.validated_data
                supplier_id = validated_data.get('supplier_id', None)  # supplier id from validated data
  
                supplier = None
                if supplier_id:
                    try:
                        supplier_id_int = int(supplier_id)  # convert to int safely
                    except (ValueError, TypeError):
                        return Response({"supplier": "Invalid supplier id."}, status=status.HTTP_400_BAD_REQUEST)
                    try:
                        supplier = Supplier.objects.get(id=supplier_id)
                    except Supplier.DoesNotExist:
                        return Response({"supplier": "Supplier not found."}, status=status.HTTP_400_BAD_REQUEST)

                product_code = validated_data.get('product_code')
                product = Product.objects.filter(product_code=product_code).first()

                if product:
                    # --- UPDATE PRODUCT ---
                    for attr, value in validated_data.items():
                        setattr(product, attr, value)
                    product.updated_by = request.user
                    product.save()

                    # Create stock history for update
                    StockHistory.objects.create(
                        product=product,
                        action='Stock In', 
                        notes=request.data.get('note') or f"Stock updated on {timezone.now().strftime('%Y-%m-%d')}",
                        action_by=request.user,
                        quantity=product.quantity
                    )

                    # --- Create SupplierProductSupply if supplier exists ---
                    if supplier:
                        supply = SupplierProductSupply.objects.filter(supplier=supplier, product=product).first()
                        quantity_to_add = validated_data.get('quantity', 0)
                        unit_price = validated_data.get('unit_buying_price', 0)

                        if supply:
                            # Update existing supply: increase quantity and update price if needed
                            supply.quantity_supplied += quantity_to_add
                            supply.unit_price = unit_price  # or keep existing if you prefer
                            supply.save()
                        else:
                            # Create new supply record
                            SupplierProductSupply.objects.create(
                                supplier=supplier,
                                product=product,
                                quantity_supplied=quantity_to_add,
                                unit_price=unit_price
                            )

                    return Response({"detail": "Product updated successfully."}, status=status.HTTP_200_OK)

                else:
                    # --- CREATE PRODUCT ---
                    new_product = serializer.save(created_by=request.user)

                    # Create stock history for new stock
                    StockHistory.objects.create(
                        product=new_product,
                        action='Stock In',
                        notes=request.data.get('note') or f"Initial stock added on {timezone.now().strftime('%Y-%m-%d')}",
                        action_by=request.user,
                        quantity=new_product.quantity
                    )

                    # --- Create SupplierProductSupply if supplier exists ---
                    if supplier:
                        supply = SupplierProductSupply.objects.filter(supplier=supplier, product=new_product).first()
                        quantity_to_add = validated_data.get('quantity', 0)
                        unit_price = validated_data.get('unit_buying_price', 0)

                        if supply:
                            # Update existing supply: increase quantity and update price if needed
                            supply.quantity_supplied += quantity_to_add
                            supply.unit_price = unit_price  # or keep existing if you prefer
                            supply.save()
                        else:
                            # Create new supply record
                            SupplierProductSupply.objects.create(
                                supplier=supplier,
                                product=new_product,
                                quantity_supplied=quantity_to_add,
                                unit_price=unit_price
                            )

                    return Response({"detail": "Product created successfully."}, status=status.HTTP_201_CREATED)

            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
@throttle_classes([SupplierThrottle])
@permission_classes([IsAuthenticated])
def get_suppliers(request):
    suppliers = Supplier.objects.all()
    serializer = SupplierSerializer(suppliers, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@throttle_classes([SupplierThrottle])
@permission_classes([IsAuthenticated])
def get_categories(request):
    # Annotate each category with the count of related products
    categories = Category.objects.annotate(product_count=Count('products'))
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@throttle_classes([SupplierThrottle])
@permission_classes([IsAuthenticated])
def get_units(request):
    units = Unit.objects.all()
    serializer = UnitSerializer(units, many=True)
    return Response(serializer.data)


class ProductListView(generics.ListAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductViewSerializer
    permission_classes = [permissions.IsAuthenticated]


class ProductDetailView(generics.RetrieveAPIView):
    """
    API view to retrieve a single product by ID (read-only).
    Only authenticated users can access.
    """
    queryset = Product.objects.all()
    serializer_class = ProductViewSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(['GET'])
@throttle_classes([SupplierThrottle])
@permission_classes([IsAuthenticated])
def products_by_category(request):
    category_id = request.query_params.get('category_id')
    if not category_id:
        return Response({"error": "select a category to view it's details."}, status=400)

    products = Product.objects.filter(category_id=category_id)
    serializer = ProductSerializer(products, many=True)
    return Response(serializer.data)



@api_view(['GET'])
@throttle_classes([SupplierThrottle])
@permission_classes([IsAuthenticated])
def get_all_stock_history(request):
    stock_history = StockHistory.objects.all().order_by('-date')

    # Filters
    action = request.GET.get('action')
    product = request.GET.get('product')
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')

    if action:
        stock_history = stock_history.filter(action__iexact=action)

    if product:
        stock_history = stock_history.filter(
            Q(product__name__icontains=product) |
            Q(reference__icontains=product)
        )

    if from_date:
        try:
            from_dt = datetime.combine(datetime.strptime(from_date, "%Y-%m-%d"), time.min)
            stock_history = stock_history.filter(date__gte=from_dt)
        except ValueError:
            pass

    if to_date:
        try:
            to_dt = datetime.combine(datetime.strptime(to_date, "%Y-%m-%d"), time.max)
            stock_history = stock_history.filter(date__lte=to_dt)
        except ValueError:
            pass


    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = 100
    result_page = paginator.paginate_queryset(stock_history, request)

    serializer = StockHistorySerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)



@api_view(['GET'])
@throttle_classes([SupplierThrottle])
@permission_classes([IsAuthenticated])
def product_batch_list(request):
    batches = ProductBatch.objects.all()
    serializer = ProductBatchSerializer(batches, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_supplier(request):
    serializer = SupplierSerializer(data=request.data)
    if serializer.is_valid():
        data = serializer.validated_data

        # Check for duplicates by email, phone, or account_number
        if data.get("email") and Supplier.objects.filter(email=data["email"]).exists():
            return Response(
                {"email": ["A supplier already exists with this email."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        if data.get("phone") and Supplier.objects.filter(phone=data["phone"]).exists():
            return Response(
                {"phone": ["A supplier already exists with this phone number."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        if data.get("account_number") and Supplier.objects.filter(account_number=data["account_number"]).exists():
            return Response(
                {"account_number": ["A supplier already exists with this account number."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If no duplicates, create supplier
        supplier = Supplier.objects.create(**data)
        return Response(SupplierSerializer(supplier).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([SupplierThrottle])
def supplier_list_with_supplies(request):
    # Get all suppliers, prefetched supplies for efficiency
    suppliers = Supplier.objects.prefetch_related('supplies__product').all()

    serializer = SupplierSerializer(suppliers, many=True)
    return Response(serializer.data)



@permission_classes([IsAuthenticated])
@api_view(['GET', 'PATCH', 'DELETE'])
def product_batch_detail(request, pk):
    try:
        batch = ProductBatch.objects.get(pk=pk)
    except ProductBatch.DoesNotExist:
        return Response({'error': 'Batch not found'}, status=status.HTTP_404_NOT_FOUND)

    # GET
    if request.method == 'GET':
        serializer = ProductBatchSerializer(batch)
        return Response(serializer.data)

    # PATCH
    elif request.method == 'PATCH':
        if request.data.get('mark_sold') or request.data.get('mark_expired'):
            batch.delete()
            return Response({'message': 'Batch deleted successfully'}, status=status.HTTP_200_OK)

        serializer = ProductBatchSerializer(batch, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_200_OK)

    # DELETE
    elif request.method == 'DELETE':
        batch.delete()
        return Response({'message': 'Batch deleted successfully'}, status=status.HTTP_200_OK)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stock_history_view(request, pk):

    if request.method == 'POST':
        # Look for the product from the URL pk
        try:
            product = Product.objects.get(pk=pk)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = StockHistoryWriteSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            quantity = serializer.validated_data['quantity']
            reason = serializer.validated_data['action']
            note = serializer.validated_data.get('notes')

            # Check if reduction exceeds current stock
            if quantity < 0 and product.quantity < abs(quantity):
                return Response(
                    {"error": "Cannot reduce more than current stock."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Perform the operation atomically
            with transaction.atomic():
                # Update product quantity
                product.quantity += quantity  # negative reduces stock
                product.save()

                # Save stock history
                stock_history = serializer.save(action_by=request.user, product=product)

                # Create InventoryWriteOff if quantity is negative
                if quantity < 0:

                    reason = reason
                    if not reason:
                        reason = "Inventory Adjustment"

                    if not note:
                        note = f"{writeoff_reason} recorded on {timezone.now().strftime('%Y-%m-%d %H:%M')} by {request.user.get_full_name() or request.user.username}"

                    InventoryWriteOff.objects.create(
                        product=product,
                        quantity=abs(quantity),
                        reason=reason,
                        note=note,
                        created_by=request.user
                    )

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_category(request):
    """
    Add a new category. Only authenticated users can add.
    If category already exists (case-insensitive), return 202 with message.
    """
    name = request.data.get('name', '').strip()
    if not name:
        return Response({"name": "This field cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
    
    # Case-insensitive check
    if Category.objects.filter(name__iexact=name).exists():
        return Response({"detail": f"Category '{name}' already exists."}, status=status.HTTP_202_ACCEPTED)
    
    serializer = CategoryWriteSerializer(data={"name": name})
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_category(request, category_id):
    try:
        category = Category.objects.get(id=category_id)
        category.delete()
        return Response({"detail": "Category deleted successfully."}, status=status.HTTP_200_OK)
    except Category.DoesNotExist:
        return Response({"detail": "Category not found."}, status=status.HTTP_404_NOT_FOUND)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_category(request, pk):
    try:
        category = Category.objects.get(pk=pk)
    except Category.DoesNotExist:
        return Response({"error": "Category not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = CategorySerializer(category, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def update_stock(request, product_id, quantity_sold):
    product = Product.objects.get(id=product_id)
    product.quantity -= quantity_sold
    product.save()

    # Send WebSocket message
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "inventory_updates",  # matches consumer group_name
        {
            "type": "send_update",  # matches consumer method
            "message": f"{product.name} stock updated to {product.quantity}"
        }
    )

    return JsonResponse({"success": True, "quantity": product.quantity})


class ProductSearchAPIView(generics.ListAPIView):
    serializer_class = ProductViewSerializer
    permission_classes = [IsAuthenticated] 

    def get_queryset(self):
        query = self.request.query_params.get('q', None)
        if query:
            return Product.objects.filter(
                Q(name__icontains=query) | Q(description__icontains=query)
            )[:10]  
        return Product.objects.none()


class ProductReceiveAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Receive/update product stock and optionally batch info.
        """
        product_id = request.data.get('product')
        if not product_id:
            return Response({"error": "Product ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({"error": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ProductUpdateSerializer(
            instance=product,
            data=request.data,
            context={'request': request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response({"success": "Product updated successfully."}, status=status.HTTP_200_OK)
        else:
            print(serializer.errors) 
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_product_by_code(request, code):
    """
    Lookup a product by its product_code and return details for update form prefill.
    """
    try:
        product = Product.objects.get(product_code=code)
    except Product.DoesNotExist:
        return Response({"detail": "Product not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = ProductViewSerializer(product)
    return Response(serializer.data, status=status.HTTP_200_OK)
