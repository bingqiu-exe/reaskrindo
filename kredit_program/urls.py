from django.urls import path
from . import views

urlpatterns = [
    path('api/import-soa-kp/', views.process_and_export_kp, name='import-soa-kp'),
]