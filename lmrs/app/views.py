from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection

def home(request):
    return render(request, 'home.html')

#to fetch the district
def get_district_boundary(request):
    """Fetch district boundary GeoJSON"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::json,
                        'properties', json_build_object(
                            'name', name,
                            'name_m', name_m
                        )
                    )
                )
            )
            FROM public.district_boundry;
        """)
        result = cursor.fetchone()
        return JsonResponse(result[0] if result[0] else {'type': 'FeatureCollection', 'features': []}, safe=False)

def get_taluka_boundary(request):
    """Fetch taluka boundary GeoJSON"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::json,
                        'properties', json_build_object(
                            'name', "TALUKA"
                        )
                    )
                )
            )
            FROM public.puranadar_taluka_bnd;
        """)
        result = cursor.fetchone()
        return JsonResponse(result[0] if result[0] else {'type': 'FeatureCollection', 'features': []}, safe=False)

def get_villages_boundary(request):
    """Fetch villages outer boundary GeoJSON"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::json,
                        'properties', json_build_object(
                            'name', "Village_Na",
                            'taluka', "Taluka"
                        )
                    )
                )
            )
            FROM public.purandhar_airport_village_bo;
        """)
        result = cursor.fetchone()
        return JsonResponse(result[0] if result[0] else {'type': 'FeatureCollection', 'features': []}, safe=False)

def get_villages_with_gut(request):
    """Fetch villages with gut numbers GeoJSON"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::json,
                        'properties', json_build_object(
                            'village', "Village_Na",
                            'gut_no', "Gut_Number",
                            'new_gut_no', "New_Gut_No",
                            'area_ha', "Area_In_Ha",
                            'taluka', "Taluka"
                        )
                    )
                )
            )
            FROM public.purandhar_airport_villages;
        """)
        result = cursor.fetchone()
        return JsonResponse(result[0] if result[0] else {'type': 'FeatureCollection', 'features': []}, safe=False)

def get_villages_list(request):
    """Fetch list of all villages"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT "Village_Na" 
            FROM public.purandhar_airport_village_bo 
            ORDER BY "Village_Na";
        """)
        villages = [row[0] for row in cursor.fetchall()]
        return JsonResponse({'villages': villages})

def get_single_village_boundary(request, village_name):
    """Fetch single village boundary GeoJSON"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::json,
                        'properties', json_build_object(
                            'name', "Village_Na",
                            'taluka', "Taluka"
                        )
                    )
                )
            )
            FROM public.purandhar_airport_village_bo
            WHERE "Village_Na" = %s;
        """, [village_name])
        result = cursor.fetchone()
        return JsonResponse(result[0] if result[0] else {'type': 'FeatureCollection', 'features': []}, safe=False)
