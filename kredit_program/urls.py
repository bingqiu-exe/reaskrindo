from django.urls import path
from . import views

urlpatterns = [
    path('api/auth/import-export', views.process_and_export_kp,name='import-export'),
]