from django.urls import path
from .views import slash_damaging_product, slash_expiring_product
from .import views

urlpatterns = [
    path('damaging/', slash_damaging_product, name='slash-damaging'),
    path('expiring/', slash_expiring_product, name='slash-expiring'),
    path('expiring-damage-products/', views.expiring_damaged_products, name='expiring_damaged_products'),
]