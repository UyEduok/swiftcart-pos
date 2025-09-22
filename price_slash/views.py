from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from products.models import Product
from .models import ExpiringProduct, DamageProduct
from .serializers import ExpiringProductSerializer, DamageProductSerializer
from .serializers import ExpiringProductViewSerializer, DamageProductViewSerializer
from sales.utils import get_cashier_sales_summary
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import ExpiringProduct, DamageProduct
from .serializers import ExpiringProductViewSerializer, DamageProductViewSerializer




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def slash_expiring_product(request):
    serializer = ExpiringProductSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({"detail": "Expired product recorded successfully"}, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def slash_damaging_product(request):
    serializer = DamageProductSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        serializer.save()
        return Response({"detail": "Damaged product recorded successfully"}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def expiring_damaged_products(request):
    """
    Returns all expiring and damaged products, ordered by creation date.
    """
    # Fetch all expiring products
    expiring_products = ExpiringProduct.objects.all().order_by('-created_date')
    # Fetch all damaged products
    damaged_products = DamageProduct.objects.all().order_by('-created_date')

    # Serialize both QuerySets
    expiring_serializer = ExpiringProductViewSerializer(expiring_products, many=True)
    damaged_serializer = DamageProductViewSerializer(damaged_products, many=True)

    summary = {}  

    return Response({
        "expiring_products": expiring_serializer.data,
        "damaged_products": damaged_serializer.data,
        "summary": summary
    })

