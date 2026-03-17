from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.home, name='home'),
    path('api/villages-list/', views.get_villages_list, name='villages_list'),
    path('api/all-villages-compensation/', views.get_all_villages_compensation, name='all_villages_compensation'),
    path('api/all-villages-farmers/', views.get_all_villages_farmers, name='all_villages_farmers'),
    path('api/project-stats/', views.get_project_stats, name='project_stats'),
    path('api/gut-numbers/<str:village_name>/', views.get_gut_numbers_by_village, name='gut_numbers'),
    path('api/gut-stats/<str:village_name>/<str:gut_number>/', views.get_gut_stats, name='gut_stats'),
    path('api/layer-bounds/<str:layer_name>/', views.get_layer_bounds, name='layer_bounds'),
]
