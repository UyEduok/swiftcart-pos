from django.urls import path
from .views import overhead_list, overhead_totals, create_overhead, dashboard_summary, revenue_trend, sale_list, OverheadUpdateView

urlpatterns = [
    path("details/", overhead_list, name="overhead-list"),
    path("totals/", overhead_totals, name="overhead-totals"),
    path("create/", create_overhead, name="create-overhead"),
    path('dashboard-summary/', dashboard_summary, name='dashboard-summary'),
    path("revenue-trend/", revenue_trend, name="revenue-trend"),
    path("sales/", sale_list, name="sale-list"),
    path("update/<int:id>/", OverheadUpdateView.as_view(), name="overhead-update"),
]
