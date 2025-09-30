from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Overhead
from .serializers import OverheadSerializer, OverheadTotalsSerializer, OverheadCreateSerializer
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from .serializers import DashboardSummarySerializer,RevenueTrendSerializer
from rest_framework import generics, filters
from sales.models import Sale
from .serializers import SaleSerializer
from django.db.models import Q
from rest_framework.generics import UpdateAPIView
from .serializers import UpdateOverheadSerializer
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import NotFound

class OverheadPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = "page_size"
    max_page_size = 10

    def paginate_queryset(self, queryset, request, view=None):
        try:
            return super().paginate_queryset(queryset, request, view)
        except NotFound:
            # Return last page if page requested is too high
            last_page_number = self.django_paginator_class(
                queryset, self.get_page_size(request)
            ).num_pages

            request.query_params._mutable = True
            request.query_params["page"] = last_page_number
            request.query_params._mutable = False

            return super().paginate_queryset(queryset, request, view)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overhead_list(request):
    """
    Returns paginated overhead records to authenticated users with optional filters:
    - from: start date
    - to: end date
    - overhead_type: capital/recurring
    - category: category
    - search: text search on description
    """
    queryset = Overhead.objects.all().order_by('-created_at')

    # --- DATE FILTERS ---
    start_date = request.GET.get("from")
    end_date = request.GET.get("to")
    if start_date:
        queryset = queryset.filter(created_at__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(created_at__date__lte=end_date)

    # --- TYPE FILTER ---
    overhead_type = request.GET.get("overhead_type")
    if overhead_type:
        queryset = queryset.filter(overhead_type=overhead_type)

    # --- CATEGORY FILTER ---
    category = request.GET.get("category")
    if category:
        queryset = queryset.filter(category=category)

    # --- SEARCH ---
    search_query = request.GET.get("search")
    if search_query:
        queryset = queryset.filter(description__icontains=search_query)

    # --- PAGINATION ---
    paginator = OverheadPagination()
    result_page = paginator.paginate_queryset(queryset, request)
    serializer = OverheadSerializer(result_page, many=True)
    return paginator.get_paginated_response(serializer.data)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overhead_totals(request):
    """
    Returns calculated overhead totals to authenticated users:
    - fixed_overhead_total
    - variable_prev_month_total
    - variable_current_month_total
    - grand_total
    """
    totals_data = OverheadTotalsSerializer.calculate_totals()
    serializer = OverheadTotalsSerializer(totals_data)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_overhead(request):
    serializer = OverheadCreateSerializer(data=request.data, context={"request": request})
    if serializer.is_valid():
        overhead = serializer.save()
        return Response(OverheadCreateSerializer(overhead).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    Returns the dashboard summary including:
    - Current and previous month discounts
    - Current and previous month profit
    - All-time profit (minus overhead)
    - Top 10 and worst 10 products
    """
    data = DashboardSummarySerializer.get_dashboard_data()
    serializer = DashboardSummarySerializer(data)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def revenue_trend(request):
    """
    Revenue trend API.
    Query param: ?range=7d|1m|3m|6m|1y
    Default = 7d
    """
    range_param = request.GET.get("range", "7d")  
    valid_ranges = ["7d", "1m", "3m", "6m", "1y"]

    if range_param not in valid_ranges:
        return Response(
            {"error": f"Invalid range '{range_param}'. Must be one of {valid_ranges}."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = RevenueTrendSerializer.get_revenue_data(range_param)
    serializer = RevenueTrendSerializer(data)
    return Response(serializer.data)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def sale_list(request):
    queryset = Sale.objects.all().order_by("-sale_date")

    # --- DATE FILTERS ---
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if start_date:
        queryset = queryset.filter(sale_date__date__gte=start_date)
    if end_date:
        queryset = queryset.filter(sale_date__date__lte=end_date)

    # --- SEARCH ---
    search_query = request.GET.get("search")
    if search_query:
        queryset = queryset.filter(
            Q(customer__name__icontains=search_query) |
            Q(reference__icontains=search_query)
        )

    # --- ORDERING ---
    ordering = request.GET.get("ordering")
    if ordering:
        queryset = queryset.order_by(ordering)

    # --- PAGINATION ---
    paginator = OverheadPagination()


    # Paginate
    paginated_qs = paginator.paginate_queryset(queryset, request)

    serializer = SaleSerializer(paginated_qs, many=True)
    return paginator.get_paginated_response(serializer.data)


class OverheadUpdateView(UpdateAPIView):
    queryset = Overhead.objects.all()
    serializer_class = UpdateOverheadSerializer
    permission_classes = [IsAuthenticated]  
    lookup_field = "id"



