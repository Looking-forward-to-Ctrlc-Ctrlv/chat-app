from django.urls import path
from . import views

urlpatterns = [
    path('sw.js', views.sw_file, name='sw_file'),
    path('upload-file/', views.upload_file, name='upload_file'),
    path('get-file-details/<int:file_id>/', views.get_file_details, name='get_file_details')
]