from django.urls import path
from . import views

urlpatterns = [
    path('api/import-soa-asum/', views.process_and_export_asum, name='import-soa-asum'),
    path('api/download-reference/', views.download_reference_file, name='download_reference'),
]