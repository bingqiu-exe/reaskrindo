from django.urls import path
from . import views

app_name = 'auto_mapping'

urlpatterns = [
    path('api/process/', views.import_cob_uy, name='process'),
]