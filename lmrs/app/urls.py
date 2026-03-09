from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/district-boundary/', views.get_district_boundary, name='district_boundary'),
    path('api/taluka-boundary/', views.get_taluka_boundary, name='taluka_boundary'),
    path('api/villages-boundary/', views.get_villages_boundary, name='villages_boundary'),
    path('api/villages-gut/', views.get_villages_with_gut, name='villages_gut'),
    path('api/villages-list/', views.get_villages_list, name='villages_list'),
    path('api/village/<str:village_name>/', views.get_single_village_boundary, name='single_village'),
    path('api/project-stats/', views.get_project_stats, name='project_stats'),
    path('api/asset-layer/<str:asset_name>/', views.get_asset_layer, name='asset_layer'),
]
