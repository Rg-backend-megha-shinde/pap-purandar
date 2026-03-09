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
                            'name', 'Purandar'
                        )
                    )
                )
            )
            FROM public.purandar_tehsil;
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

def get_project_stats(request):
    """Fetch project statistics"""
    with connection.cursor() as cursor:
        # Count villages within AOI boundary
        cursor.execute("""
            SELECT COUNT(DISTINCT v."Village_Na")
            FROM public.purandhar_airport_village_bo v, public.purandar_aoi a
            WHERE ST_Intersects(v.geometry, a.geometry);
        """)
        affected_villages = cursor.fetchone()[0] or 0
        
        # Count affected farmers
        cursor.execute("""
            SELECT COUNT(*)
            FROM public.purandar_farmers
            WHERE affected_farmer = true;
        """)
        affected_farmers = cursor.fetchone()[0] or 0
        
        # Calculate total compensation from all assets
        total_compensation = 0
        
        # Sum valuations from each asset table
        asset_tables = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell']
        
        for table in asset_tables:
            try:
                cursor.execute(f"""
                    SELECT COALESCE(SUM(valuation), 0)
                    FROM public.{table};
                """)
                result = cursor.fetchone()
                if result and result[0]:
                    total_compensation += float(result[0])
            except Exception as e:
                print(f"Error fetching valuation from {table}: {e}")
                continue
        
        # Get asset counts
        assets = {}
        asset_list = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell', 'purandar_farmers']
        
        for asset in asset_list:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM public.{asset};
                """)
                result = cursor.fetchone()
                assets[asset] = result[0] if result else 0
            except Exception as e:
                print(f"Error fetching count from {asset}: {e}")
                assets[asset] = 0
        
        # Calculate categorized counts for Land Classification
        land_classification = {}
        
        # Trees: sum of cnt_trees from bag table + count of tree table
        try:
            cursor.execute("""
                SELECT COALESCE(SUM(cnt_trees), 0)
                FROM public.bag;
            """)
            bag_trees = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COUNT(*)
                FROM public.tree;
            """)
            tree_count = cursor.fetchone()[0] or 0
            
            land_classification['trees_total'] = int(bag_trees) + int(tree_count)
        except Exception as e:
            print(f"Error calculating trees: {e}")
            land_classification['trees_total'] = 0
        
        # Structures: permanent (structures table) + temporary (shed table)
        try:
            cursor.execute("""
                SELECT COUNT(*)
                FROM public.structures;
            """)
            permanent_count = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COUNT(*)
                FROM public.shed;
            """)
            temporary_count = cursor.fetchone()[0] or 0
            
            land_classification['structures_permanent'] = int(permanent_count)
            land_classification['structures_temporary'] = int(temporary_count)
            land_classification['structures_total'] = int(permanent_count) + int(temporary_count)
        except Exception as e:
            print(f"Error calculating structures: {e}")
            land_classification['structures_permanent'] = 0
            land_classification['structures_temporary'] = 0
            land_classification['structures_total'] = 0
        
        # Water: well + borewell
        try:
            cursor.execute("""
                SELECT COUNT(*)
                FROM public.well;
            """)
            well_count = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                SELECT COUNT(*)
                FROM public.borewell;
            """)
            borewell_count = cursor.fetchone()[0] or 0
            
            land_classification['water_well'] = int(well_count)
            land_classification['water_borewell'] = int(borewell_count)
            land_classification['water_total'] = int(well_count) + int(borewell_count)
        except Exception as e:
            print(f"Error calculating water: {e}")
            land_classification['water_well'] = 0
            land_classification['water_borewell'] = 0
            land_classification['water_total'] = 0
        
        # Get asset areas in hectares
        asset_areas = {}
        # Exclude purandar_farmers from land classification as it's point data
        area_asset_list = ['bag', 'shed', 'structures', 'well']
        
        for asset in area_asset_list:
            try:
                # Check which geometry column exists
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = '{asset}'
                    AND column_name IN ('geometry', 'geom');
                """)
                geom_col = cursor.fetchone()
                
                if geom_col:
                    geom_column = geom_col[0]
                    # Calculate total area in hectares (convert from square meters)
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(ST_Area(ST_Transform({geom_column}, 32643))) / 10000, 0)
                        FROM public.{asset};
                    """)
                    result = cursor.fetchone()
                    asset_areas[asset] = round(float(result[0]), 2) if result and result[0] else 0
                else:
                    asset_areas[asset] = 0
            except Exception as e:
                print(f"Error fetching area from {asset}: {e}")
                asset_areas[asset] = 0
        
        return JsonResponse({
            'affected_villages': affected_villages,
            'affected_farmers': affected_farmers,
            'total_compensation': total_compensation,
            'assets': assets,
            'asset_areas': asset_areas,
            'land_classification': land_classification
        })

def get_asset_layer(request, asset_name):
    """Fetch asset layer GeoJSON"""
    # Validate asset name to prevent SQL injection
    valid_assets = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell', 'purandar_farmers']
    if asset_name not in valid_assets:
        return JsonResponse({'error': 'Invalid asset name'}, status=400)
    
    with connection.cursor() as cursor:
        try:
            # First, get column names excluding geometry columns
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = '{asset_name}'
                AND column_name NOT IN ('geometry', 'geom');
            """)
            columns = [row[0] for row in cursor.fetchall()]
            
            if not columns:
                return JsonResponse({'type': 'FeatureCollection', 'features': []}, safe=False)
            
            # Build the properties JSON object
            properties_fields = ', '.join([f"'{col}', \"{col}\"" for col in columns])
            
            # Check which geometry column exists
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = '{asset_name}'
                AND column_name IN ('geometry', 'geom');
            """)
            geom_col = cursor.fetchone()
            geom_column = geom_col[0] if geom_col else 'geom'
            
            cursor.execute(f"""
                SELECT json_build_object(
                    'type', 'FeatureCollection',
                    'features', COALESCE(json_agg(
                        json_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(ST_Transform({geom_column}, 4326))::json,
                            'properties', json_build_object({properties_fields})
                        )
                    ), '[]'::json)
                )
                FROM public.{asset_name};
            """)
            result = cursor.fetchone()
            return JsonResponse(result[0] if result and result[0] else {'type': 'FeatureCollection', 'features': []}, safe=False)
        except Exception as e:
            print(f"Error loading {asset_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e), 'type': 'FeatureCollection', 'features': []}, status=500)
