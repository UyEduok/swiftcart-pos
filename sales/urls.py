from django.urls import path
from . import views

urlpatterns = [
    path('sales-products/', views.sales_products, name='sales-products'),
    path('sales-customers/', views.sales_customers, name='sales-customers'),
    path('expiring-damaged/', views.expiring_and_damaged_products, name='expiring-damaged'),
    path('validate-cart/', views.validate_cart, name='expiring-damaged'),
    path('create/', views.create_sale, name='create-sale'),
    path("create-customers/", views.create_customer, name="create_customer"),
    path('today-receipts/', views.get_todays_receipts, name='today_receipts'),
   
]
