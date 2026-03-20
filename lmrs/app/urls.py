from django.urls import path
from . import views

urlpatterns = [

    # ─── Auth ────────────────────────────────────────────────────────────────
    path('login/',views.login_view,name='login'),
    path('logout/',views.logout_view,name='logout'),

    # ─── Core Pages ──────────────────────────────────────────────────────────
    path('',views.home,name='home'),
    path('tools/',views.tools,name='tools'),
    path('dashboard/',views.dashboard,name='dashboard'),

    # ─── Inspection ──────────────────────────────────────────────────────────
    path('tools/inspection/',views.inspection_form,name='inspection_form'),
    path('inspections/',views.inspection_list,name='inspection_list'),
    path('inspection/edit/<int:id>/',views.edit_inspection,name='edit_inspection'),
    path('inspection/delete/<int:id>/',views.delete_inspection,name='delete_inspection'),
    path('inspections/download-all/',views.download_all_inspections_csv,name='download_all_inspections_csv'),

    # ─── Ready Reckoner ──────────────────────────────────────────────────────
    path('tools/ready-reckoner/',views.ready_reckoner,name='ready_reckoner'),
    path('tools/ready-reckoner/list/',views.ready_reckoner_list,name='ready_reckoner_list'),
    path('tools/ready-reckoner/edit/<int:id>/',views.edit_ready_reckoner,name='edit_ready_reckoner'),
    path('tools/ready-reckoner/delete/<int:id>/',views.delete_ready_reckoner,name='delete_ready_reckoner'),

    # ─── ७/१२ Land Record ────────────────────────────────────────────────────
    path('tools/712/',views.land_record_712,name='land_record_712'),
    path('tools/712/list/',views.land_record_712_list,name='land_record_712_list'),
    path('tools/712/edit/<int:id>/',views.edit_land_record_712,name='edit_land_record_712'),
    path('tools/712/delete/<int:id>/',views.delete_land_record_712,name='delete_land_record_712'),

    # ─── API: Location & Gut Numbers ─────────────────────────────────────────
    path('api/location-data/',views.get_location_data,name='api_location_data'),
    path('api/gut-numbers/<str:village>/',views.get_gut_numbers,name='api_gut_numbers'),
    path('api/gut-numbers-map/<str:village_name>/', views.get_gut_numbers_by_village, name='api_gut_numbers_map'),

    # ─── API: Ready Reckoner Rates ───────────────────────────────────────────
    path('api/assessment-types/<str:village>/', views.get_assessment_types_by_village, name='api_assessment_types'),
    path('api/years/<str:village>/<str:assessment_type>/', views.get_years_by_village_assessment, name='api_years'),
    path('api/rates/<str:village>/<str:assessment_type>/', views.get_rates_by_village_assessment, name='api_rates'),

    # ─── API: Dashboard / Map Stats ──────────────────────────────────────────
    path('api/villages-list/',views.get_villages_list,name='api_villages_list'),
    path('api/project-stats/',views.get_project_stats,name='api_project_stats'),
    path('api/all-villages-compensation/',views.get_all_villages_compensation, name='api_all_villages_compensation'),
    path('api/all-villages-farmers/',views.get_all_villages_farmers,name='api_all_villages_farmers'),
    path('api/gut-stats/<str:village_name>/<str:gut_number>/',views.get_gut_stats,name='api_gut_stats'),
    path('api/layer-bounds/<str:layer_name>/',views.get_layer_bounds,name='api_layer_bounds'),

]
