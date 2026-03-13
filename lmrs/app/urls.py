from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('api/district-boundary/', views.get_district_boundary, name='district_boundary'),
    path('api/taluka-boundary/', views.get_taluka_boundary, name='taluka_boundary'),
    path('api/aoi-boundary/', views.get_aoi_boundary, name='aoi_boundary'),
    path('api/villages-boundary/', views.get_villages_boundary, name='villages_boundary'),
    path('api/villages-gut/', views.get_villages_with_gut, name='villages_gut'),
    path('api/villages-list/', views.get_villages_list, name='villages_list'),
    path('api/village/<str:village_name>/', views.get_single_village_boundary, name='single_village'),
    path('api/village-gut-boundaries/<str:village_name>/', views.get_village_gut_boundaries, name='village_gut_boundaries'),
    path('api/village-compensation/<str:village_name>/', views.get_village_compensation, name='village_compensation'),
    path('api/all-villages-compensation/', views.get_all_villages_compensation, name='all_villages_compensation'),
    path('api/all-villages-farmers/', views.get_all_villages_farmers, name='all_villages_farmers'),
    path('api/project-stats/', views.get_project_stats, name='project_stats'),
    path('api/gut-numbers/<str:village_name>/', views.get_gut_numbers_by_village, name='gut_numbers'),
    path('api/gut-boundary/<str:village_name>/<str:gut_number>/', views.get_gut_boundary, name='gut_boundary'),
    path('api/gut-stats/<str:village_name>/<str:gut_number>/', views.get_gut_stats, name='gut_stats'),
    path('api/layer-bounds/<str:layer_name>/', views.get_layer_bounds, name='layer_bounds'),
]
