from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .models import InventoryWriteOff
from .serializers import InventoryWriteOffSerializer
from .serializers import ProductSerializerCal, WriteOffSerializerCal

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from django.db.models import Q
from datetime import datetime, time
from .models import InventoryWriteOff
from .serializers import InventoryWriteOffSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def inventory_writeoff_list(request):
    writeoffs = InventoryWriteOff.objects.all().order_by('-date')

    # Filters
    product = request.GET.get('product')
    reason = request.GET.get('reason')
    from_date = request.GET.get('from')
    to_date = request.GET.get('to')

    if product:
        writeoffs = writeoffs.filter(
            Q(product__name__icontains=product) |
            Q(reference__icontains=product)
        )

    if reason and reason != "All":
        writeoffs = writeoffs.filter(reason=reason)

    if from_date:
        try:
            from_dt = datetime.combine(datetime.strptime(from_date, "%Y-%m-%d"), time.min)
            writeoffs = writeoffs.filter(date__gte=from_dt)
        except ValueError:
            pass

    if to_date:
        try:
            to_dt = datetime.combine(datetime.strptime(to_date, "%Y-%m-%d"), time.max)
            writeoffs = writeoffs.filter(date__lte=to_dt)
        except ValueError:
            pass

    # Pagination
    paginator = PageNumberPagination()
    paginator.page_size = 100
    result_page = paginator.paginate_queryset(writeoffs, request)
    serializer = InventoryWriteOffSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def inventory_dashboard(request):

    product_data = ProductSerializerCal({}).data
    writeoff_data = WriteOffSerializerCal({}).data

    combined_data = {**product_data, **writeoff_data}
    return Response(combined_data)

