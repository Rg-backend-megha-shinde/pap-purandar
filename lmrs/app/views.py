from django.shortcuts import render
from django.http import JsonResponse
from django.db import connection
import requests
import os
from django.conf import settings

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

def get_aoi_boundary(request):
    """Fetch AOI boundary GeoJSON"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(ST_Transform(geometry, 4326))::json,
                        'properties', json_build_object(
                            'name', 'Airport AOI'
                        )
                    )
                )
            )
            FROM public.purandar_aoi;
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

def get_village_compensation(request, village_name):
    """Fetch village-wise compensation from all asset tables"""
    with connection.cursor() as cursor:
        total_compensation = 0
        asset_tables = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell']
        
        for table in asset_tables:
            try:
                # Check if VILLAGE column exists
                cursor.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                    AND column_name ILIKE '%village%';
                """)
                village_col = cursor.fetchone()
                
                if village_col:
                    col_name = village_col[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.{table}
                        WHERE "{col_name}" = %s;
                    """, [village_name])
                    result = cursor.fetchone()
                    if result and result[0]:
                        total_compensation += float(result[0])
            except Exception as e:
                print(f"Error fetching compensation from {table}: {e}")
                continue
        
        return JsonResponse({
            'village_name': village_name,
            'total_compensation': total_compensation
        })

def get_all_villages_compensation(request):
    """Fetch compensation for all villages"""
    with connection.cursor() as cursor:
        # Get list of all villages
        cursor.execute("""
            SELECT DISTINCT "Village_Na" 
            FROM public.purandhar_airport_village_bo 
            ORDER BY "Village_Na";
        """)
        villages = [row[0] for row in cursor.fetchall()]
        
        villages_data = []
        asset_tables = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell']
        
        for village in villages:
            total_compensation = 0
            
            for table in asset_tables:
                try:
                    # Check if VILLAGE column exists
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                        AND column_name ILIKE '%village%';
                    """)
                    village_col = cursor.fetchone()
                    
                    if village_col:
                        col_name = village_col[0]
                        cursor.execute(f"""
                            SELECT COALESCE(SUM(valuation), 0)
                            FROM public.{table}
                            WHERE "{col_name}" = %s;
                        """, [village])
                        result = cursor.fetchone()
                        if result and result[0]:
                            total_compensation += float(result[0])
                except Exception as e:
                    print(f"Error fetching compensation from {table} for {village}: {e}")
                    continue
            
            villages_data.append({
                'village_name': village,
                'compensation': total_compensation
            })
        
        # Sort by compensation descending
        villages_data.sort(key=lambda x: x['compensation'], reverse=True)
        
        return JsonResponse({'villages': villages_data})

def get_all_villages_farmers(request):
    """Fetch affected farmers count for all villages"""
    with connection.cursor() as cursor:
        # Get list of all villages
        cursor.execute("""
            SELECT DISTINCT "Village_Na" 
            FROM public.purandhar_airport_village_bo 
            ORDER BY "Village_Na";
        """)
        villages = [row[0] for row in cursor.fetchall()]
        
        # Check which column name exists for village in purandar_farmers table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'purandar_farmers'
            AND (column_name ILIKE '%village%' OR column_name = 'VILLAGE')
            LIMIT 1;
        """)
        village_col_result = cursor.fetchone()
        
        if not village_col_result:
            return JsonResponse({'villages': []})
        
        village_col = village_col_result[0]
        villages_data = []
        
        for village in villages:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM public.purandar_farmers
                    WHERE affected_farmer = true 
                    AND UPPER(TRIM("{village_col}")) = UPPER(TRIM(%s));
                """, [village])
                farmers_count = cursor.fetchone()[0] or 0
                
                villages_data.append({
                    'village_name': village,
                    'farmers_count': farmers_count
                })
            except Exception as e:
                print(f"Error fetching farmers from {village}: {e}")
                continue
        
        # Sort by farmers count descending
        villages_data.sort(key=lambda x: x['farmers_count'], reverse=True)
        
        return JsonResponse({'villages': villages_data})

def get_project_stats(request):
    """Fetch project statistics - supports optional village filter"""
    village_name = request.GET.get('village', None)
    
    with connection.cursor() as cursor:
        # Count villages within AOI boundary
        cursor.execute("""
            SELECT COUNT(DISTINCT v."Village_Na")
            FROM public.purandhar_airport_village_bo v, public.purandar_aoi a
            WHERE ST_Intersects(v.geometry, a.geometry);
        """)
        affected_villages = cursor.fetchone()[0] or 0
        
        # Count affected farmers - with optional village filter
        if village_name:
            # Check which column name exists for village in purandar_farmers table
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'purandar_farmers'
                AND (column_name ILIKE '%village%' OR column_name = 'VILLAGE')
                LIMIT 1;
            """)
            village_col_result = cursor.fetchone()
            
            if village_col_result:
                village_col = village_col_result[0]
                # Count farmers from selected village where affected_farmer = true
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM public.purandar_farmers
                    WHERE affected_farmer = true 
                    AND UPPER(TRIM("{village_col}")) = UPPER(TRIM(%s));
                """, [village_name])
                affected_farmers = cursor.fetchone()[0] or 0
                print(f"Village filter: {village_name}, Column: {village_col}, Count: {affected_farmers}")
            else:
                # No village column found, return total
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM public.purandar_farmers
                    WHERE affected_farmer = true;
                """)
                affected_farmers = cursor.fetchone()[0] or 0
        else:
            # Total affected farmers across all villages
            cursor.execute("""
                SELECT COUNT(*)
                FROM public.purandar_farmers
                WHERE affected_farmer = true;
            """)
            affected_farmers = cursor.fetchone()[0] or 0
        
        # Calculate area acquired from gut_bnd table (in hectares) - with optional village filter
        try:
            if village_name:
                # Check if gut_bnd table exists and get column names
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'gut_bnd'
                    AND (column_name ILIKE '%village%' OR column_name = 'VILLAGE')
                    LIMIT 1;
                """)
                village_col_result = cursor.fetchone()
                
                if village_col_result:
                    village_col = village_col_result[0]
                    # Check if area and affected_gut columns exist (check various naming conventions)
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'gut_bnd'
                        AND (column_name ILIKE '%area%' OR column_name ILIKE '%affected%');
                    """)
                    columns = {row[0].lower(): row[0] for row in cursor.fetchall()}
                    
                    # Find area column (could be Area_In_Ha, area_in_ha, area, etc.)
                    area_col = None
                    for col_lower, col_actual in columns.items():
                        if 'area' in col_lower and 'ha' in col_lower:
                            area_col = col_actual
                            break
                    
                    if not area_col:
                        for col_lower, col_actual in columns.items():
                            if 'area' in col_lower:
                                area_col = col_actual
                                break
                    
                    # Find affected_gut column
                    affected_col = None
                    for col_lower, col_actual in columns.items():
                        if 'affected' in col_lower and 'gut' in col_lower:
                            affected_col = col_actual
                            break
                    
                    if area_col and affected_col:
                        cursor.execute(f"""
                            SELECT COALESCE(SUM("{area_col}"), 0)
                            FROM public.gut_bnd
                            WHERE UPPER("{village_col}") = UPPER(%s) AND "{affected_col}" = true;
                        """, [village_name])
                        area_acquired = cursor.fetchone()[0] or 0
                        area_acquired = round(float(area_acquired), 2)
                    elif area_col:
                        # If no affected_gut column, just sum all area for the village
                        cursor.execute(f"""
                            SELECT COALESCE(SUM("{area_col}"), 0)
                            FROM public.gut_bnd
                            WHERE UPPER("{village_col}") = UPPER(%s);
                        """, [village_name])
                        area_acquired = cursor.fetchone()[0] or 0
                        area_acquired = round(float(area_acquired), 2)
                    else:
                        # Fallback: try purandhar_airport_villages table
                        cursor.execute("""
                            SELECT COALESCE(SUM("Area_In_Ha"), 0)
                            FROM public.purandhar_airport_villages
                            WHERE UPPER("Village_Na") = UPPER(%s);
                        """, [village_name])
                        area_acquired = cursor.fetchone()[0] or 0
                        area_acquired = round(float(area_acquired), 2)
                else:
                    # Fallback: try purandhar_airport_villages table
                    cursor.execute("""
                        SELECT COALESCE(SUM("Area_In_Ha"), 0)
                        FROM public.purandhar_airport_villages
                        WHERE UPPER("Village_Na") = UPPER(%s);
                    """, [village_name])
                    area_acquired = cursor.fetchone()[0] or 0
                    area_acquired = round(float(area_acquired), 2)
            else:
                # Total area - try gut_bnd first, fallback to purandhar_airport_villages
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' 
                        AND table_name = 'gut_bnd'
                    );
                """)
                gut_bnd_exists = cursor.fetchone()[0]
                
                if gut_bnd_exists:
                    cursor.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = 'gut_bnd'
                        AND (column_name ILIKE '%area%' OR column_name ILIKE '%affected%');
                    """)
                    columns = {row[0].lower(): row[0] for row in cursor.fetchall()}
                    
                    # Find area column
                    area_col = None
                    for col_lower, col_actual in columns.items():
                        if 'area' in col_lower and 'ha' in col_lower:
                            area_col = col_actual
                            break
                    
                    if not area_col:
                        for col_lower, col_actual in columns.items():
                            if 'area' in col_lower:
                                area_col = col_actual
                                break
                    
                    # Find affected_gut column
                    affected_col = None
                    for col_lower, col_actual in columns.items():
                        if 'affected' in col_lower and 'gut' in col_lower:
                            affected_col = col_actual
                            break
                    
                    if area_col and affected_col:
                        cursor.execute(f"""
                            SELECT COALESCE(SUM("{area_col}"), 0)
                            FROM public.gut_bnd
                            WHERE "{affected_col}" = true;
                        """)
                        area_acquired = cursor.fetchone()[0] or 0
                        area_acquired = round(float(area_acquired), 2)
                    elif area_col:
                        cursor.execute(f"""
                            SELECT COALESCE(SUM("{area_col}"), 0)
                            FROM public.gut_bnd;
                        """)
                        area_acquired = cursor.fetchone()[0] or 0
                        area_acquired = round(float(area_acquired), 2)
                    else:
                        # Fallback to purandhar_airport_villages
                        cursor.execute("""
                            SELECT COALESCE(SUM("Area_In_Ha"), 0)
                            FROM public.purandhar_airport_villages;
                        """)
                        area_acquired = cursor.fetchone()[0] or 0
                        area_acquired = round(float(area_acquired), 2)
                else:
                    cursor.execute("""
                        SELECT COALESCE(SUM(area), 0) / 10000
                        FROM public.bund;
                    """)
                    area_acquired = cursor.fetchone()[0] or 0
                    area_acquired = round(float(area_acquired), 2)
        except Exception as e:
            print(f"Error calculating area acquired: {e}")
            area_acquired = 0
        
        # Calculate total compensation from all assets - with optional village filter
        total_compensation = 0
        
        # Sum valuations from each asset table
        asset_tables = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell']
        
        if village_name:
            # when a village is selected, reuse the logic from get_village_compensation
            for table in asset_tables:
                try:
                    # look for any column containing the word "village" (same as other endpoint)
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                        AND column_name ILIKE '%village%';
                    """)
                    village_col = cursor.fetchone()
                    if village_col:
                        col_name = village_col[0]
                        cursor.execute(f"""
                            SELECT COALESCE(SUM(valuation), 0)
                            FROM public.{table}
                            WHERE "{col_name}" = %s;
                        """, [village_name])
                        result = cursor.fetchone()
                        if result and result[0]:
                            total_compensation += float(result[0])
                    # if no village column was found, nothing is added for this table
                except Exception as e:
                    print(f"Error fetching compensation from {table} for village stats: {e}")
                    continue
        else:
            # total project compensation (no village filter)
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
        
        # Get asset counts - with optional village filter
        assets = {}
        asset_list = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell', 'purandar_farmers']
        
        for asset in asset_list:
            try:
                if village_name:
                    # Check if VILLAGE column exists
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = '{asset}'
                        AND (column_name ILIKE '%village%' OR column_name = 'VILLAGE')
                        LIMIT 1;
                    """)
                    village_col_result = cursor.fetchone()
                    
                    if village_col_result:
                        col_name = village_col_result[0]
                        cursor.execute(f"""
                            SELECT COUNT(*)
                            FROM public.{asset}
                            WHERE UPPER(TRIM("{col_name}")) = UPPER(TRIM(%s));
                        """, [village_name])
                        result = cursor.fetchone()
                        assets[asset] = result[0] if result else 0
                        print(f"Asset {asset}: Village {village_name}, Column: {col_name}, Count: {assets[asset]}")
                    else:
                        cursor.execute(f"""
                            SELECT COUNT(*)
                            FROM public.{asset};
                        """)
                        result = cursor.fetchone()
                        assets[asset] = result[0] if result else 0
                else:
                    cursor.execute(f"""
                        SELECT COUNT(*)
                        FROM public.{asset};
                    """)
                    result = cursor.fetchone()
                    assets[asset] = result[0] if result else 0
            except Exception as e:
                print(f"Error fetching count from {asset}: {e}")
                assets[asset] = 0
        
        # Calculate categorized counts for Land Classification - ALWAYS SHOW TOTAL (not village-specific)
        land_classification = {}
        
        # Trees: sum of cnt_trees from bag table + count of tree table
        # (respect village filter when provided)
        try:
            if village_name:
                # bag table
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'bag'
                      AND column_name ILIKE '%village%'
                    LIMIT 1;
                """)
                bag_vcol = cursor.fetchone()
                if bag_vcol:
                    bv = bag_vcol[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(cnt_trees),0), COALESCE(SUM(valuation),0)
                        FROM public.bag
                        WHERE UPPER(TRIM("{bv}")) = UPPER(TRIM(%s));
                    """, [village_name])
                    bag_trees, bag_valuation = cursor.fetchone() or (0,0)
                else:
                    bag_trees = bag_valuation = 0

                # tree table
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'tree'
                      AND column_name ILIKE '%village%'
                    LIMIT 1;
                """)
                tree_vcol = cursor.fetchone()
                if tree_vcol:
                    tv = tree_vcol[0]
                    cursor.execute(f"""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.tree
                        WHERE UPPER(TRIM("{tv}")) = UPPER(TRIM(%s));
                    """, [village_name])
                    tree_count, tree_valuation = cursor.fetchone() or (0,0)
                else:
                    tree_count = tree_valuation = 0
            else:
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
                
                cursor.execute("""
                    SELECT COALESCE(SUM(valuation), 0)
                    FROM public.bag;
                """)
                bag_valuation = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                    SELECT COALESCE(SUM(valuation), 0)
                    FROM public.tree;
                """)
                tree_valuation = cursor.fetchone()[0] or 0

            land_classification['trees_total'] = int(bag_trees) + int(tree_count)
            land_classification['trees_valuation'] = float(bag_valuation) + float(tree_valuation)
        except Exception as e:
            print(f"Error calculating trees: {e}")
            land_classification['trees_total'] = 0
            land_classification['trees_valuation'] = 0
        
        # Structures: permanent (structures table) + temporary (shed table)
        try:
            if village_name:
                # structures table
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'structures'
                      AND column_name ILIKE '%village%'
                    LIMIT 1;
                """)
                str_vcol = cursor.fetchone()
                if str_vcol:
                    sv = str_vcol[0]
                    cursor.execute(f"""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.structures
                        WHERE UPPER(TRIM("{sv}")) = UPPER(TRIM(%s));
                    """, [village_name])
                else:
                    cursor.execute("""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.structures;
                    """)
                result = cursor.fetchone()
                permanent_count = result[0] or 0
                permanent_valuation = result[1] or 0

                # shed table
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'shed'
                      AND column_name ILIKE '%village%'
                    LIMIT 1;
                """)
                shed_vcol = cursor.fetchone()
                if shed_vcol:
                    sh = shed_vcol[0]
                    cursor.execute(f"""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.shed
                        WHERE UPPER(TRIM("{sh}")) = UPPER(TRIM(%s));
                    """, [village_name])
                else:
                    cursor.execute("""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.shed;
                    """)
                result = cursor.fetchone()
                temporary_count = result[0] or 0
                temporary_valuation = result[1] or 0
            else:
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(valuation), 0)
                    FROM public.structures;
                """)
                result = cursor.fetchone()
                permanent_count = result[0] or 0
                permanent_valuation = result[1] or 0
                
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(valuation), 0)
                    FROM public.shed;
                """)
                result = cursor.fetchone()
                temporary_count = result[0] or 0
                temporary_valuation = result[1] or 0

            land_classification['structures_permanent'] = int(permanent_count)
            land_classification['structures_permanent_valuation'] = float(permanent_valuation)
            land_classification['structures_temporary'] = int(temporary_count)
            land_classification['structures_temporary_valuation'] = float(temporary_valuation)
            land_classification['structures_total'] = int(permanent_count) + int(temporary_count)
            land_classification['structures_valuation'] = float(permanent_valuation) + float(temporary_valuation)
        except Exception as e:
            print(f"Error calculating structures: {e}")
            land_classification['structures_permanent'] = 0
            land_classification['structures_permanent_valuation'] = 0
            land_classification['structures_temporary'] = 0
            land_classification['structures_temporary_valuation'] = 0
            land_classification['structures_total'] = 0
            land_classification['structures_valuation'] = 0
        
        # Water: well + borewell (optionally filtered by village)
        try:
            if village_name:
                # well
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'well'
                      AND column_name ILIKE '%village%'
                    LIMIT 1;
                """)
                well_vcol = cursor.fetchone()
                if well_vcol:
                    wv = well_vcol[0]
                    cursor.execute(f"""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.well
                        WHERE UPPER(TRIM("{wv}")) = UPPER(TRIM(%s));
                    """, [village_name])
                else:
                    cursor.execute("""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.well;
                    """)
                result = cursor.fetchone()
                well_count = result[0] or 0
                well_valuation = result[1] or 0

                # borewell
                cursor.execute(f"""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name = 'borewell'
                      AND column_name ILIKE '%village%'
                    LIMIT 1;
                """)
                bore_vcol = cursor.fetchone()
                if bore_vcol:
                    bv = bore_vcol[0]
                    cursor.execute(f"""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.borewell
                        WHERE UPPER(TRIM("{bv}")) = UPPER(TRIM(%s));
                    """, [village_name])
                else:
                    cursor.execute("""
                        SELECT COUNT(*), COALESCE(SUM(valuation),0)
                        FROM public.borewell;
                    """)
                result = cursor.fetchone()
                borewell_count = result[0] or 0
                borewell_valuation = result[1] or 0
            else:
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(valuation), 0)
                    FROM public.well;
                """)
                result = cursor.fetchone()
                well_count = result[0] or 0
                well_valuation = result[1] or 0
                
                cursor.execute("""
                    SELECT COUNT(*), COALESCE(SUM(valuation), 0)
                    FROM public.borewell;
                """)
                result = cursor.fetchone()
                borewell_count = result[0] or 0
                borewell_valuation = result[1] or 0

            land_classification['water_well'] = int(well_count)
            land_classification['water_well_valuation'] = float(well_valuation)
            land_classification['water_borewell'] = int(borewell_count)
            land_classification['water_borewell_valuation'] = float(borewell_valuation)
            land_classification['water_total'] = int(well_count) + int(borewell_count)
            land_classification['water_valuation'] = float(well_valuation) + float(borewell_valuation)
        except Exception as e:
            print(f"Error calculating water: {e}")
            land_classification['water_well'] = 0
            land_classification['water_well_valuation'] = 0
            land_classification['water_borewell'] = 0
            land_classification['water_borewell_valuation'] = 0
            land_classification['water_total'] = 0
            land_classification['water_valuation'] = 0
        
        # Get asset areas in hectares
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
            'area_acquired': area_acquired,
            'total_compensation': total_compensation,
            'assets': assets,
            'asset_areas': asset_areas,
            'land_classification': land_classification
        })

def get_asset_layer(request, asset_name):
    """Fetch asset layer GeoJSON - tries GeoServer first, falls back to PostGIS"""
    valid_assets = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell', 'purandar_farmers']
    if asset_name not in valid_assets:
        return JsonResponse({'error': 'Invalid asset name'}, status=400)

    # --- Try GeoServer first ---
    try:
        geoserver_url = os.getenv('GEOSERVER_URL', 'http://209.182.233.103:9090/geoserver')
        workspace = os.getenv('GEOSERVER_WORKSPACE', 'Purandar')
        wfs_url = f"{geoserver_url}/wfs"
        params = {
            'service': 'WFS',
            'version': '1.0.0',
            'request': 'GetFeature',
            'typeName': f'{workspace}:{asset_name}',
            'outputFormat': 'application/json',
            'srsName': 'EPSG:4326'
        }
        response = requests.get(wfs_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('features'):
                print(f"GeoServer: loaded {asset_name} with {len(data['features'])} features")
                return JsonResponse(data, safe=False)
    except Exception as e:
        print(f"GeoServer unavailable for {asset_name}, falling back to PostGIS: {e}")

    # --- Fallback: query PostGIS directly ---
    try:
        with connection.cursor() as cursor:
            # Detect geometry column name (geometry or geom)
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name IN ('geometry', 'geom')
                LIMIT 1;
            """, [asset_name])
            geom_row = cursor.fetchone()

            if not geom_row:
                return JsonResponse({
                    'error': f'No geometry column found in table {asset_name}',
                    'type': 'FeatureCollection',
                    'features': []
                }, status=500)

            geom_col = geom_row[0]

            # Get all non-geometry columns for properties
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name NOT IN ('geometry', 'geom')
                ORDER BY ordinal_position;
            """, [asset_name])
            prop_columns = [row[0] for row in cursor.fetchall()]

            # Build properties JSON object dynamically
            props_sql = ", ".join(
                f"'{col}', \"{col}\"" for col in prop_columns
            )

            cursor.execute(f"""
                SELECT json_build_object(
                    'type', 'FeatureCollection',
                    'features', COALESCE(json_agg(
                        json_build_object(
                            'type', 'Feature',
                            'geometry', ST_AsGeoJSON(ST_Transform({geom_col}, 4326))::json,
                            'properties', json_build_object({props_sql})
                        )
                    ), '[]'::json)
                )
                FROM public."{asset_name}";
            """)

            result = cursor.fetchone()
            print(f"PostGIS fallback: loaded {asset_name}")
            return JsonResponse(
                result[0] if result and result[0] else {'type': 'FeatureCollection', 'features': []},
                safe=False
            )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': f'Failed to load {asset_name} from both GeoServer and PostGIS: {str(e)}',
            'type': 'FeatureCollection',
            'features': []
        }, status=500)