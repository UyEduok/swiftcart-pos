from django.urls import path
from .views import ProductDetailView, products_by_category, get_all_stock_history, product_batch_detail, stock_history_view,ProductReceiveAPIView
from .views import get_suppliers, get_categories, supplier_list_with_supplies, delete_category, update_category, ProductSearchAPIView
from .views import add_category, product_batch_list, create_supplier, ProductCreateUpdateAPIView, get_units, ProductListView
from .views import get_product_by_code
urlpatterns = [
    path('create-update/', ProductCreateUpdateAPIView.as_view(), name='product-create-update'),
    path('suppliers/', get_suppliers, name='get_suppliers'),
    path('categories/', get_categories, name='get_categories'),
    path('units/', get_units, name='get_units'),
    path('inventory/', ProductListView.as_view(), name='product-list'),
    path('inventory/<int:pk>/', ProductDetailView.as_view(), name='product-detail'),
    path('by-category/', products_by_category, name='products-by-category'),
    path('stockhistory/', get_all_stock_history, name='get-all-stock-history'),
    path('suppliers/create/', create_supplier, name='create-supplier'),
    path('suppliers/', supplier_list_with_supplies, name='suppliers'),
    path('product-batches/', product_batch_list, name='product-batch-list'),
    path('product-batches/<int:pk>/', product_batch_detail, name='product-batch-detail'),
    path('stock-history/', stock_history_view, name='stock-history'),
    path('stock-history/<int:pk>/', stock_history_view, name='stock-history'),
    path('add-category/', add_category, name='add-category'),
    path('delete-category/<int:category_id>/', delete_category, name='delete-category'),
    path('update-category/<int:pk>/', update_category, name='update-category'),
    path('search/', ProductSearchAPIView.as_view(), name='product-search'),
    path('receive/', ProductReceiveAPIView.as_view(), name='product-search'),
    path("code-search-update/<str:code>/", get_product_by_code, name="get-product-by-code"),
    
]
