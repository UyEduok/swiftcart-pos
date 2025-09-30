from django.contrib import admin
from django.conf import settings
from django.urls import path, include, re_path
from users.views import TokenValidateView
from products.consumers import InventoryConsumer
from .views import index
from django.views.static import serve
import socket

host_ip = socket.gethostbyname(socket.gethostname())
admin.site.site_url = f"http://{host_ip}:8000/inventory-dashboard"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/products/', include('products.urls')),
    path('api/token/validate/', TokenValidateView.as_view(), name='token-validate'),
    path('api/inventory/', include('inventory_writeoffs.urls')),
    path('api/price-slash/', include('price_slash.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/overheads/', include('overhead.urls')),
    re_path(r'ws/inventory/$', InventoryConsumer.as_asgi()),  
    path("", index, name="index"),
    path("inventory-dashboard/", index, name="inventory-dashboard"),
]


urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
