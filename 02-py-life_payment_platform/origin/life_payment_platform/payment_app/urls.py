from django.urls import path
from django.contrib import admin
from .views import register, user_login, user_logout, bill_list, pay_bill, payment_record_list, user_profile, bill_type_list, bill_type_create, bill_type_edit, bill_type_delete

urlpatterns = [
    path('admin/', admin.site.urls),
    path('register/', register, name='register'),
    path('login/', user_login, name='login'),
    path('logout/', user_logout, name='logout'),
    path('bills/', bill_list, name='bill_list'),
    path('bills/<int:bill_id>/pay/', pay_bill, name='pay_bill'),
    path('payment-records/', payment_record_list, name='payment_record_list'),
    path('profile/', user_profile, name='user_profile'),
    path('bill-types/', bill_type_list, name='bill_type_list'),
    path('bill-types/create/', bill_type_create, name='bill_type_create'),
    path('bill-types/<int:bill_type_id>/edit/', bill_type_edit, name='bill_type_edit'),
    path('bill-types/<int:bill_type_id>/delete/', bill_type_delete, name='bill_type_delete'),
]