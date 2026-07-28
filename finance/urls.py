from django.urls import path
from . import views

urlpatterns = [
    path('api/import-export', views.process_and_export_finance,name='import-export'),
]