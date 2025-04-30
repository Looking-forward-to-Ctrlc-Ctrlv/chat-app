from django.urls import path
from . import views

urlpatterns = [
    path('sw.js', views.sw_file, name='sw_file'),
    path('upload-file/', views.upload_file, name='upload_file')
    # Add other URL routes here
]