from django.urls import path
from . import views

urlpatterns = [
    path('api/import-soa-finance/', views.process_and_export_finance, name='import-soa-finance'),
    path('api/download-reference/', views.download_reference_file, name='download_reference'),
]