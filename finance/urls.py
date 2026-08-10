from django.urls import path
from . import views

urlpatterns = [
    path('api/import-soa-finance/', views.process_and_export_finance, name='import-soa-finance'),
]