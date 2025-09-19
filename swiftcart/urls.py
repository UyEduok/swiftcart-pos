
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include 
from users.views import TokenValidateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/products/', include('products.urls')),
    path('api/token/validate/', TokenValidateView.as_view(), name='token-validate'),
    path('api/inventory/', include('inventory_writeoffs.urls')),
    path('api/price-slash/', include('price_slash.urls')),
    path('api/sales/', include('sales.urls')),
    path('api/overheads/', include('overhead.urls')),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
