from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/district-boundary/', views.get_district_boundary, name='district_boundary'),
    path('api/taluka-boundary/', views.get_taluka_boundary, name='taluka_boundary'),
    path('api/villages-boundary/', views.get_villages_boundary, name='villages_boundary'),
    path('api/villages-gut/', views.get_villages_with_gut, name='villages_gut'),
]
