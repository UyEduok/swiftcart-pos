# inventory_writeoffs/urls.py
from django.urls import path
from .views import inventory_writeoff_list, inventory_dashboard

urlpatterns = [
    path('write-offs/', inventory_writeoff_list, name='inventory-writeoff-list'),
    path('inventory-dashboard/', inventory_dashboard, name='inventory-writeoff-list'),
    
]
