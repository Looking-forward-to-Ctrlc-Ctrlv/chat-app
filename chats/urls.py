from django.urls import path
from . import views

urlpatterns = [
    path('sw.js', views.sw_file, name='sw_file'),
    # Add other URL routes here
]