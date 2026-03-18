from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import JsonResponse
from django.db import connection
from .models import Inspection, TreeDetail, ReadyReckonerRate, LandRecord712
import csv

def api_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def tools(request):
    return render(request, 'tools.html')

@login_required
def ready_reckoner(request):
    if request.method == "POST":
        obj = ReadyReckonerRate.objects.create(
            district=request.POST.get('district'),
            taluka=request.POST.get('taluka'),
            village=request.POST.get('village'),
            assessment_type=request.POST.get('assessment_type'),
            assessment_range_min=request.POST.get('assessment_range_min'),
            assessment_range_max=request.POST.get('assessment_range_max'),
            rate=request.POST.get('rate'),
            unit=request.POST.get('unit'),
        )
        return redirect('ready_reckoner_list')
    return render(request, "readyreckoner.html")

@login_required
def ready_reckoner_list(request):
    records = ReadyReckonerRate.objects.all().order_by('-id')
    return render(request, 'ready_reckoner_list.html', {'records': records})

@login_required
def edit_ready_reckoner(request, id):
    obj = ReadyReckonerRate.objects.get(id=id)
    if request.method == "POST":
        obj.district = request.POST.get('district')
        obj.taluka = request.POST.get('taluka')
        obj.village = request.POST.get('village')
        obj.assessment_type = request.POST.get('assessment_type')
        obj.assessment_range_min = request.POST.get('assessment_range_min')
        obj.assessment_range_max = request.POST.get('assessment_range_max')
        obj.rate = request.POST.get('rate')
        obj.unit = request.POST.get('unit')
        obj.save()
        return redirect('edit_ready_reckoner', id=obj.id)
    return render(request, 'edit_ready_reckoner.html', {'obj': obj})

@login_required
def delete_ready_reckoner(request, id):
    ReadyReckonerRate.objects.filter(id=id).delete()
    return redirect('ready_reckoner_list')

@login_required
def land_record_712(request):
    if request.method == "POST":
        obj = LandRecord712.objects.create(
            district=request.POST.get('district'),
            taluka=request.POST.get('taluka'),
            village=request.POST.get('village'),
            gut_number=request.POST.get('gut_number'),
            farmer_name=request.POST.get('farmer_name'),
            assessment_type=request.POST.get('assessment_type'),
            aakarnee=request.POST.get('aakarnee'),
            rate_applied=request.POST.get('rate_applied'),
            document_712=request.FILES.get('document_712'),
        )
        return redirect('land_record_712_list')
    return render(request, "landrecord.html")

@login_required
def land_record_712_list(request):
    records = LandRecord712.objects.all().order_by('-id')
    return render(request, 'land_record_712_list.html', {'records': records})

@login_required
def edit_land_record_712(request, id):
    obj = LandRecord712.objects.get(id=id)
    if request.method == "POST":
        obj.district = request.POST.get('district')
        obj.taluka = request.POST.get('taluka')
        obj.village = request.POST.get('village')
        obj.gut_number = request.POST.get('gut_number')
        obj.farmer_name = request.POST.get('farmer_name')
        obj.assessment_type = request.POST.get('assessment_type')
        obj.aakarnee = request.POST.get('aakarnee')
        obj.rate_applied = request.POST.get('rate_applied')
        if request.FILES.get('document_712'):
            obj.document_712 = request.FILES.get('document_712')
        obj.save()
        return redirect('edit_land_record_712', id=obj.id)
    return render(request, 'edit_land_record_712.html', {'obj': obj})

@login_required
def delete_land_record_712(request, id):
    LandRecord712.objects.filter(id=id).delete()
    return redirect('land_record_712_list')

@api_login_required
def get_assessment_types_by_village(request, village):
    types = list(
        ReadyReckonerRate.objects.filter(village=village)
        .values_list('assessment_type', flat=True)
        .distinct()
    )
    return JsonResponse({'assessment_types': types})

@api_login_required
def get_rates_by_village_assessment(request, village, assessment_type):
    records = list(
        ReadyReckonerRate.objects.filter(village=village, assessment_type=assessment_type)
        .values('assessment_range_min', 'assessment_range_max', 'rate', 'unit')
    )
    # Convert Decimal to float for JSON serialization
    for r in records:
        r['assessment_range_min'] = float(r['assessment_range_min'])
        r['assessment_range_max'] = float(r['assessment_range_max'])
        r['rate'] = float(r['rate'])
    return JsonResponse({'rates': records})

@login_required
def inspection_form(request):

    if request.method == "POST":

        # ✅ 1. Save main inspection
        inspection = Inspection.objects.create(
            district=request.POST.get("district"),
            taluka=request.POST.get("taluka"),
            village=request.POST.get("village"),
            gut_number=request.POST.get("survey"),
            officer=request.POST.get("officer"),
            date=request.POST.get("date"),
        )

        # ✅ 2. Get table data (multiple rows)
        plots = request.POST.getlist("plot[]")
        names = request.POST.getlist("name[]")
        lengths = request.POST.getlist("length[]")
        widths = request.POST.getlist("width[]")
        girths = request.POST.getlist("girth[]")
        heights = request.POST.getlist("height[]")

        # ✅ 3. Save each row
        for i in range(len(names)):
            if names[i]:  # skip empty rows
                TreeDetail.objects.create(
                    inspection=inspection,
                    plot=plots[i],
                    name=names[i],
                    length=lengths[i] or None,
                    width=widths[i] or None,
                    girth=girths[i] or None,
                    height=heights[i] or None,
                )

       
        return redirect('inspection_list')

    return render(request, "inspection_form.html")

@login_required
def dashboard(request):
    if not request.user.is_superuser:
        return redirect('/tools/')  

    return render(request, "dashboard.html")


# @login_required
# def tools(request):
#     if request.method == "POST":
#         print(request.POST)  # debug

#     return render(request, "tools.html")

# @login_required
# def tools(request):
#     return HttpResponse("Tools OK")
#to fetch the district
# Views moved or removed because they were redundant (using GeoServer WMS instead)


@api_login_required
@api_login_required
def get_villages_list(request):
    """Fetch list of all villages"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT "village" 
            FROM public.purandhar_airport_village_bo 
            ORDER BY "village";
        """)
        villages = [row[0] for row in cursor.fetchall()]
        return JsonResponse({'villages': villages})



@api_login_required
@api_login_required
def get_all_villages_compensation(request):
    """Fetch compensation for all villages"""
    with connection.cursor() as cursor:
        # Get list of all villages
        cursor.execute("""
            SELECT DISTINCT "village" 
            FROM public.purandhar_airport_village_bo 
            ORDER BY "village";
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
@api_login_required
@api_login_required
def get_all_villages_farmers(request):
    """Fetch affected farmers count for all villages"""
    with connection.cursor() as cursor:
        # Get list of all villages
        cursor.execute("""
            SELECT DISTINCT "village" 
            FROM public.purandhar_airport_village_bo 
            ORDER BY "village";
        """)
        villages = [row[0] for row in cursor.fetchall()]
        
        # Check which column name exists for village in purandar_farmers table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'purandar_farmers'
            AND (column_name ILIKE '%village%' OR column_name = 'village')
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
@api_login_required
@api_login_required
def get_project_stats(request):
    """Fetch project statistics - supports optional village filter"""
    village_name = request.GET.get('village', None)
    
    with connection.cursor() as cursor:
        # Count villages within AOI boundary
        cursor.execute("""
            SELECT COUNT(DISTINCT v."village")
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
                AND (column_name ILIKE '%village%' OR column_name = 'village')
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
                    AND (column_name ILIKE '%village%' OR column_name = 'village')
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
                            WHERE UPPER("village") = UPPER(%s);
                        """, [village_name])
                        area_acquired = cursor.fetchone()[0] or 0
                        area_acquired = round(float(area_acquired), 2)
                else:
                    # Fallback: try purandhar_airport_villages table
                    cursor.execute("""
                        SELECT COALESCE(SUM("Area_In_Ha"), 0)
                        FROM public.purandhar_airport_villages
                        WHERE UPPER("village") = UPPER(%s);
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
                        AND (column_name ILIKE '%village%' OR column_name = 'village')
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
@api_login_required
@api_login_required
def get_gut_numbers_by_village(request, village_name):
    """Fetch list of gut numbers for a specific village"""
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT DISTINCT "Gut_Number" 
                FROM public.gut_bnd 
                WHERE "village" = %s
                ORDER BY "Gut_Number";
            """, [village_name])
            gut_numbers = [row[0] for row in cursor.fetchall()]
            print(f"Found {len(gut_numbers)} gut numbers for village {village_name}: {gut_numbers[:10]}")
            return JsonResponse({'gut_numbers': gut_numbers})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e), 'gut_numbers': []}, status=500)

@api_login_required
@api_login_required
def get_gut_stats(request, village_name, gut_number):
    """Fetch statistics for a specific gut"""
    with connection.cursor() as cursor:
        try:
            # Get gut area
            cursor.execute("""
                SELECT "Area_In_Ha"
                FROM public.gut_bnd
                WHERE "village" = %s AND "Gut_Number" = %s;
            """, [village_name, gut_number])
            gut_area_result = cursor.fetchone()
            area_acquired = float(gut_area_result[0]) if gut_area_result and gut_area_result[0] else 0
            
            # Count affected farmers in this gut
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'purandar_farmers'
                AND column_name IN ('geometry', 'geom')
                LIMIT 1;
            """)
            farmer_geom_col = cursor.fetchone()
            
            affected_farmers = 0
            if farmer_geom_col:
                geom_col = farmer_geom_col[0]
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM public.purandar_farmers f
                    WHERE f.affected_farmer = true
                    AND EXISTS (
                        SELECT 1 FROM public.gut_bnd g
                        WHERE g."village" = %s
                        AND g."Gut_Number" = %s
                        AND ST_Intersects(
                            ST_Transform(f.{geom_col}, 4326),
                            ST_Transform(g.geometry, 4326)
                        )
                    );
                """, [village_name, gut_number])
                affected_farmers = cursor.fetchone()[0] or 0
            
            # Calculate total compensation from all assets in this gut
            total_compensation = 0
            asset_tables = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell']
            assets = {}
            
            for table in asset_tables:
                try:
                    # Check if geometry column exists
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                        AND column_name IN ('geometry', 'geom')
                        LIMIT 1;
                    """)
                    geom_col_result = cursor.fetchone()
                    
                    if geom_col_result:
                        geom_col = geom_col_result[0]
                        
                        # Count assets in gut
                        cursor.execute(f"""
                            SELECT COUNT(*), COALESCE(SUM(valuation), 0)
                            FROM public.{table} a
                            WHERE EXISTS (
                                SELECT 1 FROM public.gut_bnd g
                                WHERE g."village" = %s
                                AND g."Gut_Number" = %s
                                AND ST_Intersects(
                                    ST_Transform(a.{geom_col}, 4326),
                                    ST_Transform(g.geometry, 4326)
                                )
                            );
                        """, [village_name, gut_number])
                        result = cursor.fetchone()
                        count = result[0] or 0
                        valuation = result[1] or 0
                        
                        assets[table] = count
                        total_compensation += float(valuation)
                except Exception as e:
                    print(f"Error fetching {table} for gut: {e}")
                    assets[table] = 0
            
            # Add farmers count to assets
            assets['purandar_farmers'] = affected_farmers
            
            # Calculate land classification for gut
            land_classification = {}
            
            # Trees
            try:
                # bag table - cnt_trees
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'bag'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                bag_geom = cursor.fetchone()
                
                if bag_geom:
                    geom_col = bag_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(cnt_trees), 0), COALESCE(SUM(valuation), 0)
                        FROM public.bag a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    bag_result = cursor.fetchone()
                    bag_trees = int(bag_result[0] or 0)
                    bag_valuation = float(bag_result[1] or 0)
                else:
                    bag_trees = bag_valuation = 0
                
                # tree table
                tree_count = assets.get('tree', 0)
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'tree'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                tree_geom = cursor.fetchone()
                
                tree_valuation = 0
                if tree_geom:
                    geom_col = tree_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.tree a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    tree_valuation = float(cursor.fetchone()[0] or 0)
                
                land_classification['trees_total'] = bag_trees + tree_count
                land_classification['trees_valuation'] = bag_valuation + tree_valuation
            except Exception as e:
                print(f"Error calculating trees for gut: {e}")
                land_classification['trees_total'] = 0
                land_classification['trees_valuation'] = 0
            
            # Structures
            land_classification['structures_permanent'] = assets.get('structures', 0)
            land_classification['structures_temporary'] = assets.get('shed', 0)
            land_classification['structures_total'] = land_classification['structures_permanent'] + land_classification['structures_temporary']
            
            # Get valuations for structures
            try:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'structures'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                struct_geom = cursor.fetchone()
                
                if struct_geom:
                    geom_col = struct_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.structures a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['structures_permanent_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['structures_permanent_valuation'] = 0
                
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'shed'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                shed_geom = cursor.fetchone()
                
                if shed_geom:
                    geom_col = shed_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.shed a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['structures_temporary_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['structures_temporary_valuation'] = 0
                
                land_classification['structures_valuation'] = land_classification['structures_permanent_valuation'] + land_classification['structures_temporary_valuation']
            except Exception as e:
                print(f"Error calculating structures valuation for gut: {e}")
                land_classification['structures_permanent_valuation'] = 0
                land_classification['structures_temporary_valuation'] = 0
                land_classification['structures_valuation'] = 0
            
            # Water
            land_classification['water_well'] = assets.get('well', 0)
            land_classification['water_borewell'] = assets.get('borewell', 0)
            land_classification['water_total'] = land_classification['water_well'] + land_classification['water_borewell']
            
            # Get valuations for water
            try:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'well'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                well_geom = cursor.fetchone()
                
                if well_geom:
                    geom_col = well_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.well a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['water_well_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['water_well_valuation'] = 0
                
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'borewell'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                bore_geom = cursor.fetchone()
                
                if bore_geom:
                    geom_col = bore_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.borewell a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['water_borewell_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['water_borewell_valuation'] = 0
                
                land_classification['water_valuation'] = land_classification['water_well_valuation'] + land_classification['water_borewell_valuation']
            except Exception as e:
                print(f"Error calculating water valuation for gut: {e}")
                land_classification['water_well_valuation'] = 0
                land_classification['water_borewell_valuation'] = 0
                land_classification['water_valuation'] = 0
            
            return JsonResponse({
                'affected_farmers': affected_farmers,
                'area_acquired': round(area_acquired, 2),
                'total_compensation': total_compensation,
                'assets': assets,
                'land_classification': land_classification,
                'village_name': village_name,
                'gut_number': gut_number
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)
@api_login_required
@api_login_required
def get_layer_bounds(request, layer_name):
    """Fetch bounding box for any layer"""
    valid_layers = {
        'district_boundry': 'district_boundry',
        'purandar_tehsil': 'purandar_tehsil',
        'purandar_aoi': 'purandar_aoi',
        'purandhar_airport_village_bo': 'purandhar_airport_village_bo',
        'purandhar_airport_villages': 'purandhar_airport_villages',
        'gut_bnd': 'gut_bnd',
        'bag': 'bag',
        'tree': 'tree',
        'shed': 'shed',
        'structures': 'structures',
        'well': 'well',
        'borewell': 'borewell',
        'purandar_farmers': 'purandar_farmers'
    }
    
    if layer_name not in valid_layers:
        return JsonResponse({'error': 'Invalid layer name'}, status=400)
    
    table_name = valid_layers[layer_name]
    village_name = request.GET.get('village', None)
    gut_number = request.GET.get('gut_number', None)
    
    try:
        with connection.cursor() as cursor:
            # Detect geometry column name
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                  AND column_name IN ('geometry', 'geom')
                LIMIT 1;
            """, [table_name])
            geom_row = cursor.fetchone()
            
            if not geom_row:
                return JsonResponse({'error': f'No geometry column found in {table_name}'}, status=500)
            
            geom_col = geom_row[0]
            
            # Build WHERE clause for filtering
            where_clause = ""
            params = []
            
            if gut_number and village_name and table_name != 'gut_bnd':
                # Filter by gut intersection
                where_clause = f"""
                    WHERE EXISTS (
                        SELECT 1 FROM public.gut_bnd g
                        WHERE UPPER(TRIM(g."village")) = UPPER(TRIM(%s))
                        AND g."Gut_Number" = %s
                        AND ST_Intersects(
                            ST_Transform(a.{geom_col}, 4326),
                            ST_Transform(g.geometry, 4326)
                        )
                    )
                """
                params = [village_name, gut_number]
            elif village_name and table_name != 'gut_bnd':
                # Filter by village intersection
                where_clause = f"""
                    WHERE EXISTS (
                        SELECT 1 FROM public.purandhar_airport_village_bo v
                        WHERE UPPER(TRIM(v."village")) = UPPER(TRIM(%s))
                        AND ST_Intersects(
                            ST_Transform(a.{geom_col}, 4326),
                            ST_Transform(v.geometry, 4326)
                        )
                    )
                """
                params = [village_name]
            elif village_name and table_name == 'gut_bnd':
                # For gut_bnd, filter by village and optionally Gut_Number
                if gut_number:
                    where_clause = 'WHERE UPPER(TRIM("village")) = UPPER(TRIM(%s)) AND "Gut_Number" = %s'
                    params = [village_name, gut_number]
                else:
                    where_clause = 'WHERE UPPER(TRIM("village")) = UPPER(TRIM(%s))'
                    params = [village_name]
            
            # Calculate bounds in WGS84
            if where_clause:
                query = f"""
                    SELECT 
                        ST_XMin(extent) as minx,
                        ST_YMin(extent) as miny,
                        ST_XMax(extent) as maxx,
                        ST_YMax(extent) as maxy
                    FROM (
                        SELECT ST_Extent(ST_Transform({geom_col}, 4326)) as extent
                        FROM public.{table_name} a
                        {where_clause}
                    ) as subquery;
                """
            else:
                query = f"""
                    SELECT 
                        ST_XMin(extent) as minx,
                        ST_YMin(extent) as miny,
                        ST_XMax(extent) as maxx,
                        ST_YMax(extent) as maxy
                    FROM (
                        SELECT ST_Extent(ST_Transform({geom_col}, 4326)) as extent
                        FROM public.{table_name}
                    ) as subquery;
                """
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            
            if result and result[0] is not None:
                return JsonResponse({
                    'bounds': {
                        'minLng': float(result[0]),
                        'minLat': float(result[1]),
                        'maxLng': float(result[2]),
                        'maxLat': float(result[3])
                    }
                })
            else:
                return JsonResponse({'error': 'No features found'}, status=404)
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)
    """Fetch statistics for a specific gut"""
    with connection.cursor() as cursor:
        try:
            # Get gut area
            cursor.execute("""
                SELECT "Area_In_Ha"
                FROM public.gut_bnd
                WHERE "village" = %s AND "Gut_Number" = %s;
            """, [village_name, gut_number])
            gut_area_result = cursor.fetchone()
            area_acquired = float(gut_area_result[0]) if gut_area_result and gut_area_result[0] else 0
            
            # Count affected farmers in this gut
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'purandar_farmers'
                AND column_name IN ('geometry', 'geom')
                LIMIT 1;
            """)
            farmer_geom_col = cursor.fetchone()
            
            affected_farmers = 0
            if farmer_geom_col:
                geom_col = farmer_geom_col[0]
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM public.purandar_farmers f
                    WHERE f.affected_farmer = true
                    AND EXISTS (
                        SELECT 1 FROM public.gut_bnd g
                        WHERE g."village" = %s
                        AND g."Gut_Number" = %s
                        AND ST_Intersects(
                            ST_Transform(f.{geom_col}, 4326),
                            ST_Transform(g.geometry, 4326)
                        )
                    );
                """, [village_name, gut_number])
                affected_farmers = cursor.fetchone()[0] or 0
            
            # Calculate total compensation from all assets in this gut
            total_compensation = 0
            asset_tables = ['bag', 'tree', 'shed', 'structures', 'well', 'borewell']
            assets = {}
            
            for table in asset_tables:
                try:
                    # Check if geometry column exists
                    cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = 'public' 
                        AND table_name = '{table}'
                        AND column_name IN ('geometry', 'geom')
                        LIMIT 1;
                    """)
                    geom_col_result = cursor.fetchone()
                    
                    if geom_col_result:
                        geom_col = geom_col_result[0]
                        
                        # Count assets in gut
                        cursor.execute(f"""
                            SELECT COUNT(*), COALESCE(SUM(valuation), 0)
                            FROM public.{table} a
                            WHERE EXISTS (
                                SELECT 1 FROM public.gut_bnd g
                                WHERE g."village" = %s
                                AND g."Gut_Number" = %s
                                AND ST_Intersects(
                                    ST_Transform(a.{geom_col}, 4326),
                                    ST_Transform(g.geometry, 4326)
                                )
                            );
                        """, [village_name, gut_number])
                        result = cursor.fetchone()
                        count = result[0] or 0
                        valuation = result[1] or 0
                        
                        assets[table] = count
                        total_compensation += float(valuation)
                except Exception as e:
                    print(f"Error fetching {table} for gut: {e}")
                    assets[table] = 0
            
            # Add farmers count to assets
            assets['purandar_farmers'] = affected_farmers
            
            # Calculate land classification for gut
            land_classification = {}
            
            # Trees
            try:
                # bag table - cnt_trees
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'bag'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                bag_geom = cursor.fetchone()
                
                if bag_geom:
                    geom_col = bag_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(cnt_trees), 0), COALESCE(SUM(valuation), 0)
                        FROM public.bag a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    bag_result = cursor.fetchone()
                    bag_trees = int(bag_result[0] or 0)
                    bag_valuation = float(bag_result[1] or 0)
                else:
                    bag_trees = bag_valuation = 0
                
                # tree table
                tree_count = assets.get('tree', 0)
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'tree'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                tree_geom = cursor.fetchone()
                
                tree_valuation = 0
                if tree_geom:
                    geom_col = tree_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.tree a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    tree_valuation = float(cursor.fetchone()[0] or 0)
                
                land_classification['trees_total'] = bag_trees + tree_count
                land_classification['trees_valuation'] = bag_valuation + tree_valuation
            except Exception as e:
                print(f"Error calculating trees for gut: {e}")
                land_classification['trees_total'] = 0
                land_classification['trees_valuation'] = 0
            
            # Structures
            land_classification['structures_permanent'] = assets.get('structures', 0)
            land_classification['structures_temporary'] = assets.get('shed', 0)
            land_classification['structures_total'] = land_classification['structures_permanent'] + land_classification['structures_temporary']
            
            # Get valuations for structures
            try:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'structures'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                struct_geom = cursor.fetchone()
                
                if struct_geom:
                    geom_col = struct_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.structures a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['structures_permanent_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['structures_permanent_valuation'] = 0
                
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'shed'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                shed_geom = cursor.fetchone()
                
                if shed_geom:
                    geom_col = shed_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.shed a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['structures_temporary_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['structures_temporary_valuation'] = 0
                
                land_classification['structures_valuation'] = land_classification['structures_permanent_valuation'] + land_classification['structures_temporary_valuation']
            except Exception as e:
                print(f"Error calculating structures valuation for gut: {e}")
                land_classification['structures_permanent_valuation'] = 0
                land_classification['structures_temporary_valuation'] = 0
                land_classification['structures_valuation'] = 0
            
            # Water
            land_classification['water_well'] = assets.get('well', 0)
            land_classification['water_borewell'] = assets.get('borewell', 0)
            land_classification['water_total'] = land_classification['water_well'] + land_classification['water_borewell']
            
            # Get valuations for water
            try:
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'well'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                well_geom = cursor.fetchone()
                
                if well_geom:
                    geom_col = well_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.well a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['water_well_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['water_well_valuation'] = 0
                
                cursor.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'borewell'
                    AND column_name IN ('geometry', 'geom')
                    LIMIT 1;
                """)
                bore_geom = cursor.fetchone()
                
                if bore_geom:
                    geom_col = bore_geom[0]
                    cursor.execute(f"""
                        SELECT COALESCE(SUM(valuation), 0)
                        FROM public.borewell a
                        WHERE EXISTS (
                            SELECT 1 FROM public.gut_bnd g
                            WHERE g."village" = %s
                            AND g."Gut_Number" = %s
                            AND ST_Intersects(
                                ST_Transform(a.{geom_col}, 4326),
                                ST_Transform(g.geometry, 4326)
                            )
                        );
                    """, [village_name, gut_number])
                    land_classification['water_borewell_valuation'] = float(cursor.fetchone()[0] or 0)
                else:
                    land_classification['water_borewell_valuation'] = 0
                
                land_classification['water_valuation'] = land_classification['water_well_valuation'] + land_classification['water_borewell_valuation']
            except Exception as e:
                print(f"Error calculating water valuation for gut: {e}")
                land_classification['water_well_valuation'] = 0
                land_classification['water_borewell_valuation'] = 0
                land_classification['water_valuation'] = 0
            
            return JsonResponse({
                'affected_farmers': affected_farmers,
                'area_acquired': round(area_acquired, 2),
                'total_compensation': total_compensation,
                'assets': assets,
                'land_classification': land_classification,
                'village_name': village_name,
                'gut_number': gut_number
            })
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=500)

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'login.html', {"error": "Invalid credentials"})

    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('login')



def get_location_data(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT
                    'Pune' as district,
                    "Taluka",
                    "village"
                FROM public.purandhar_airport_villages
                ORDER BY "Taluka", "village";
            """)

            rows = cursor.fetchall()

            data = [
                {
                    "district": row[0],
                    "taluka": row[1],
                    "village_name": row[2],
                }
                for row in rows
            ]

            return JsonResponse({"villages": data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)



def get_gut_numbers(request, village):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT "Gut_Number"
                FROM public.purandhar_airport_villages
                WHERE "village" = %s
                ORDER BY "Gut_Number";
            """, [village])

            rows = cursor.fetchall()

            data = [row[0] for row in rows]

            return JsonResponse({"gut_numbers": data})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# @login_required
# def inspection_list(request):
#     inspections = Inspection.objects.all().order_by('-id')
#     return render(request, 'inspection_list.html', {'inspections': inspections})

@login_required
def inspection_list(request):
    try:
        inspections = Inspection.objects.all().order_by('-id')
        return render(request, 'inspection_list.html', {'inspections': inspections})

    except Exception as e:
        import traceback
        print("🔥 ERROR IN inspection_list VIEW:")
        traceback.print_exc()   # prints full error in terminal

        return HttpResponse(f"Error occurred: {str(e)}")

@login_required
def delete_inspection(request, id):
    try:
        inspection = Inspection.objects.get(id=id)
        inspection.delete()
        return redirect('/inspections/')  
    except Inspection.DoesNotExist:
        return HttpResponse("Record not found")

@login_required
def edit_inspection(request, id):
    try:
        inspection = Inspection.objects.get(id=id)
        tree_details = TreeDetail.objects.filter(inspection=inspection)

        if request.method == "POST":

            # ✅ Update main inspection
            inspection.district = request.POST.get("district")
            inspection.taluka = request.POST.get("taluka")
            inspection.village = request.POST.get("village")
            inspection.gut_number = request.POST.get("survey")
            inspection.officer = request.POST.get("officer")
            inspection.date = request.POST.get("date")
            inspection.save()

            # ✅ Delete old tree data
            tree_details.delete()

            # ✅ Save new rows
            plots = request.POST.getlist("plot[]")
            names = request.POST.getlist("name[]")
            lengths = request.POST.getlist("length[]")
            widths = request.POST.getlist("width[]")
            girths = request.POST.getlist("girth[]")
            heights = request.POST.getlist("height[]")

            for i in range(len(names)):
                if names[i]:
                    TreeDetail.objects.create(
                        inspection=inspection,
                        plot=plots[i],
                        name=names[i],
                        length=lengths[i] or None,
                        width=widths[i] or None,
                        girth=girths[i] or None,
                        height=heights[i] or None,
                    )

            return redirect('inspection_list')

        return render(request, "edit_inspection.html", {
            "inspection": inspection,
            "tree_details": tree_details
        })

    except Inspection.DoesNotExist:
        return HttpResponse("Record not found")


@login_required
def download_all_inspections_csv(request):
    inspections = Inspection.objects.all().order_by('id')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="all_inspections.csv"'

    writer = csv.writer(response)

    # Header
    writer.writerow([
        'Inspection ID',
        'District',
        'Taluka',
        'Village',
        'Gut Number',
        'Officer',
        'Date',
        'Plot',
        'Tree Name',
        'Length',
        'Width',
        'Girth',
        'Height'
    ])

    # Data
    for inspection in inspections:
        trees = TreeDetail.objects.filter(inspection=inspection)

        if trees.exists():
            for tree in trees:
                writer.writerow([
                    inspection.id,
                    inspection.district,
                    inspection.taluka,
                    inspection.village,
                    inspection.gut_number,
                    inspection.officer,
                    inspection.date,
                    tree.plot,
                    tree.name,
                    tree.length,
                    tree.width,
                    tree.girth,
                    tree.height
                ])
        else:
            # If no tree data
            writer.writerow([
                inspection.id,
                inspection.district,
                inspection.taluka,
                inspection.village,
                inspection.gut_number,
                inspection.officer,
                inspection.date,
                '', '', '', '', '', ''
            ])

    return response