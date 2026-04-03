from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from .models import Inspection, TreeDetail, ReadyReckonerInfo, ReadyReckonerRate, LandRecord712, FarmerNames,TreeMaster, Asset, AssetMeasurement, AssetTypeMaster, AssetFieldMaster, AssetFormulaMaster, Document, ToolMaster, DocumentMaster, DocumentAttachment, Entry
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.db import connection
import csv
import re
import json
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods



def api_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def handle_document_upload(user, tool_name, files, district=None, taluka=None, village=None, gut_number=None,
                          inspection=None, rr_info=None, land_record=None, asset=None, document_tool_record=None):
    tool, created = ToolMaster.objects.get_or_create(tool_name=tool_name, defaults={'is_active': True})
    doc_master_kwargs = {'user': user, 'tool': tool, 'district': district, 'taluka': taluka, 'village': village, 'gut_number': gut_number}
    if inspection:
        doc_master_kwargs['inspection'] = inspection
    elif rr_info:
        doc_master_kwargs['rr_info'] = rr_info
    elif land_record:
        doc_master_kwargs['land_record'] = land_record
    elif asset:
        doc_master_kwargs['asset'] = asset
    elif document_tool_record:
        doc_master_kwargs['document_tool_record'] = document_tool_record
    
    # Try to get existing DocumentMaster or create new one
    doc_master = None
    if inspection:
        doc_master = DocumentMaster.objects.filter(inspection=inspection).first()
    elif rr_info:
        doc_master = DocumentMaster.objects.filter(rr_info=rr_info).first()
    elif land_record:
        doc_master = DocumentMaster.objects.filter(land_record=land_record).first()
    elif asset:
        doc_master = DocumentMaster.objects.filter(asset=asset).first()
    elif document_tool_record:
        doc_master = DocumentMaster.objects.filter(document_tool_record=document_tool_record).first()
    
    if not doc_master:
        doc_master = DocumentMaster.objects.create(**doc_master_kwargs)
    
    # Create DocumentAttachment entries for each file
    for file in files:
        DocumentAttachment.objects.create(document_master=doc_master, file=file)
    return doc_master

@login_required
def home(request):
    return render(request, 'home.html')

@login_required
def tools(request):
    return render(request, 'tools.html')


@login_required
def ready_reckoner(request):
    if request.method == "POST":
        district = request.POST.get('district')
        taluka = request.POST.get('taluka')
        village = request.POST.get('village')
        year = request.POST.get('year')
        block_count = int(request.POST.get('block_count', 0))
        files = request.FILES.getlist('documents')
        first_info = None
        for bi in range(block_count):
            assessment_type = request.POST.get(f'assessment_type[{bi}]')
            unit = request.POST.get(f'unit[{bi}]')
            if not assessment_type:
                continue
            info = ReadyReckonerInfo.objects.create(
                user=request.user, district=district, taluka=taluka,
                village=village, year=year, assessment_type=assessment_type, unit=unit
            )
            if first_info is None:
                first_info = info
            ri = 0
            while True:
                mn = request.POST.get(f'assessment_range_min[{bi}][{ri}]')
                mx = request.POST.get(f'assessment_range_max[{bi}][{ri}]')
                rt = request.POST.get(f'rate[{bi}][{ri}]')
                if mn is None:
                    break
                if mn and mx and rt:
                    ReadyReckonerRate.objects.create(rr=info, assessment_range_min=mn, assessment_range_max=mx, rate=rt)
                ri += 1
        if files and first_info:
            handle_document_upload(user=request.user, tool_name='Ready Reckoner Rate', rr_info=first_info,
                files=files, district=district, taluka=taluka, village=village)
        return redirect('ready_reckoner_list')
    return render(request, "readyreckoner.html")

@login_required
def ready_reckoner_list(request):
    all_records = ReadyReckonerInfo.objects.prefetch_related('rates').all().order_by('district', 'taluka', 'village', 'year', 'id')

    # Group by village+year — one entry per village
    from itertools import groupby
    groups = []
    keyfunc = lambda r: (r.district, r.taluka, r.village, r.year)
    for key, items in groupby(all_records, key=keyfunc):
        item_list = list(items)
        anchor = item_list[0]  # first record = anchor for edit/docs
        # Collect all documents across all records in this village+year group
        all_docs = []
        for rec in item_list:
            all_docs.extend(rec.get_documents())
        groups.append({
            'anchor': anchor,
            'records': item_list,
            'all_docs': all_docs,
            'has_docs': any(dm.attachments.exists() for dm in all_docs),
            'district': key[0],
            'taluka': key[1],
            'village': key[2],
            'year': key[3],
        })
    return render(request, 'ready_reckoner_list.html', {'groups': groups})

@login_required
def edit_ready_reckoner(request, id):
    # Use the clicked record to identify the village+year group
    anchor = ReadyReckonerInfo.objects.get(id=id)
    village_records = ReadyReckonerInfo.objects.prefetch_related('rates').filter(
        village=anchor.village, year=anchor.year
    ).order_by('id')

    if request.method == "POST":
        district = request.POST.get('district')
        taluka = request.POST.get('taluka')
        village = request.POST.get('village')
        year = request.POST.get('year')
        block_count = int(request.POST.get('block_count', 0))

        # Collect submitted block IDs (existing) and new blocks
        existing_ids_submitted = []
        for bi in range(block_count):
            rec_id = request.POST.get(f'record_id[{bi}]')
            assessment_type = request.POST.get(f'assessment_type[{bi}]')
            unit = request.POST.get(f'unit[{bi}]')
            if not assessment_type:
                continue

            if rec_id:
                # Update existing record
                try:
                    info = ReadyReckonerInfo.objects.get(id=int(rec_id))
                    info.district = district
                    info.taluka = taluka
                    info.village = village
                    info.year = year
                    info.assessment_type = assessment_type
                    info.unit = unit
                    info.save()
                    info.rates.all().delete()
                    existing_ids_submitted.append(info.id)
                except ReadyReckonerInfo.DoesNotExist:
                    info = ReadyReckonerInfo.objects.create(
                        user=request.user, district=district, taluka=taluka,
                        village=village, year=year, assessment_type=assessment_type, unit=unit
                    )
                    existing_ids_submitted.append(info.id)
            else:
                # New block
                info = ReadyReckonerInfo.objects.create(
                    user=request.user, district=district, taluka=taluka,
                    village=village, year=year, assessment_type=assessment_type, unit=unit
                )
                existing_ids_submitted.append(info.id)

            ri = 0
            while True:
                mn = request.POST.get(f'assessment_range_min[{bi}][{ri}]')
                mx = request.POST.get(f'assessment_range_max[{bi}][{ri}]')
                rt = request.POST.get(f'rate[{bi}][{ri}]')
                if mn is None:
                    break
                if mn and mx and rt:
                    ReadyReckonerRate.objects.create(rr=info, assessment_range_min=mn, assessment_range_max=mx, rate=rt)
                ri += 1

        # Delete records that were removed in the form
        ReadyReckonerInfo.objects.filter(
            village=village, year=year
        ).exclude(id__in=existing_ids_submitted).delete()

        files = request.FILES.getlist('documents')
        if files:
            handle_document_upload(user=request.user, tool_name='Ready Reckoner Rate', rr_info=anchor,
                files=files, district=district, taluka=taluka, village=village)
        return redirect('ready_reckoner_list')

    # Collect all documents across all village records
    all_documents = []
    for rec in village_records:
        all_documents.extend(rec.get_documents())

    return render(request, 'edit_ready_reckoner.html', {
        'anchor': anchor,
        'village_records': village_records,
        'all_documents': all_documents,
    })

@login_required
def delete_ready_reckoner(request, id):
    anchor = ReadyReckonerInfo.objects.filter(id=id).first()
    if anchor:
        ReadyReckonerInfo.objects.filter(village=anchor.village, year=anchor.year).delete()
    return redirect('ready_reckoner_list')

@login_required
def delete_document_attachment(request, attachment_id):
    """Delete a document attachment"""
    if request.method == 'POST':
        try:
            attachment = DocumentAttachment.objects.get(id=attachment_id)
            # Delete the file from storage
            if attachment.file:
                attachment.file.delete()
            # Delete the database record
            attachment.delete()
            return JsonResponse({'success': True})
        except DocumentAttachment.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'File not found'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

@login_required
def land_record_712(request):
    if request.method == "POST":
        obj = LandRecord712.objects.create(
            user=request.user,
            district=request.POST.get('district'),
            taluka=request.POST.get('taluka'),
            village=request.POST.get('village'),
            gut_number=request.POST.get('gut_number'),
            date=request.POST.get('date') or None,
            assessment_type=request.POST.get('assessment_type'),
            aakarnee=request.POST.get('aakarnee'),
            rate_applied=request.POST.get('rate_applied'),
            rate_year=request.POST.get('rate_year'),
        )
        for name, total_area, potkharaba in zip(
            request.POST.getlist('farmer_name[]'),
            request.POST.getlist('total_area[]'),
            request.POST.getlist('potkharaba[]'),
        ):
            if name.strip():
                FarmerNames.objects.create(
                    land_record=obj,
                    farmer_name=name.strip(),
                    total_area=total_area.strip() or None,
                    potkharaba=potkharaba.strip() or None,
                )
        
        # Handle document uploads using centralized system
        files = request.FILES.getlist('documents')
        if files:
            handle_document_upload(
                user=request.user,
                tool_name='7/12 Land Record',
                land_record=obj,
                files=files,
                district=obj.district,
                taluka=obj.taluka,
                village=obj.village,
                gut_number=obj.gut_number
            )
        
        return redirect('land_record_712_list')
    return render(request, "landrecord.html")

@login_required
def land_record_712_list(request):
    records = LandRecord712.objects.prefetch_related('farmers').all().order_by('-id')
    # Prefetch documents for each record
    for record in records:
        record.documents_list = record.get_documents()
    return render(request, 'land_record_712_list.html', {'records': records})

@login_required
def edit_land_record_712(request, id):
    obj = LandRecord712.objects.get(id=id)
    farmers = FarmerNames.objects.filter(land_record=obj)
    if request.method == "POST":
        obj.district = request.POST.get('district')
        obj.taluka = request.POST.get('taluka')
        obj.village = request.POST.get('village')
        obj.gut_number = request.POST.get('gut_number')
        obj.date = request.POST.get('date') or None
        obj.assessment_type = request.POST.get('assessment_type')
        obj.aakarnee = request.POST.get('aakarnee')
        obj.rate_applied = request.POST.get('rate_applied')
        obj.rate_year = request.POST.get('rate_year')
        if request.FILES.get('document_712'):
            obj.document_712 = request.FILES.get('document_712')
        obj.save()
        farmers.delete()
        for name, total_area, potkharaba in zip(
            request.POST.getlist('farmer_name[]'),
            request.POST.getlist('total_area[]'),
            request.POST.getlist('potkharaba[]'),
        ):
            if name.strip():
                FarmerNames.objects.create(
                    land_record=obj,
                    farmer_name=name.strip(),
                    total_area=total_area.strip() or None,
                    potkharaba=potkharaba.strip() or None,
                )
        
        # Handle additional document uploads using centralized system
        files = request.FILES.getlist('documents')
        if files:
            handle_document_upload(
                user=request.user,
                tool_name='7/12 Land Record',
                land_record=obj,
                files=files,
                district=obj.district,
                taluka=obj.taluka,
                village=obj.village,
                gut_number=obj.gut_number
            )
        
        return redirect('land_record_712_list')
    
    # Get existing documents
    documents = obj.get_documents()
    return render(request, 'edit_land_record_712.html', {'obj': obj, 'farmers': farmers, 'documents': documents})

@login_required
def delete_land_record_712(request, id):
    LandRecord712.objects.filter(id=id).delete()
    return redirect('land_record_712_list')

@api_login_required
def get_assessment_types_by_village(request, village):
    types = list(ReadyReckonerInfo.objects.filter(village=village).values_list('assessment_type', flat=True).distinct())
    return JsonResponse({'assessment_types': types})

@api_login_required
def get_years_by_village_assessment(request, village, assessment_type):
    years = list(ReadyReckonerInfo.objects.filter(village=village, assessment_type=assessment_type)
        .order_by('-year').values_list('year', flat=True).distinct())
    return JsonResponse({'years': years})

@api_login_required
def get_rates_by_village_assessment(request, village, assessment_type):
    requested_year = request.GET.get('year')
    qs = ReadyReckonerInfo.objects.filter(village=village, assessment_type=assessment_type)
    year = requested_year if requested_year and qs.filter(year=requested_year).exists() else \
        qs.order_by('-year').values_list('year', flat=True).first()
    info = qs.filter(year=year).first()
    records = []
    if info:
        for r in info.rates.all():
            records.append({'assessment_range_min': float(r.assessment_range_min),
                'assessment_range_max': float(r.assessment_range_max), 'rate': float(r.rate),
                'unit': info.unit, 'year': info.year})
    return JsonResponse({'rates': records, 'year': year})

@login_required
def inspection_form(request):
    if request.method == "POST":
        inspection = Inspection.objects.create(
            user=request.user,
            district=request.POST.get("district"),
            taluka=request.POST.get("taluka"),
            village=request.POST.get("village"),
            gut_number=request.POST.get("survey"),
            officer=request.POST.get("officer"),
            date=request.POST.get("date"),
        )
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
                    length=float(lengths[i]) if lengths[i] and lengths[i].strip() and lengths[i].strip() != 'None' else None,
                    width=float(widths[i]) if widths[i] and widths[i].strip() and widths[i].strip() != 'None' else None,
                    girth=float(girths[i]) if girths[i] and girths[i].strip() and girths[i].strip() != 'None' else None,
                    height=float(heights[i]) if heights[i] and heights[i].strip() and heights[i].strip() != 'None' else None,
                )
        
        # Handle document uploads using centralized system
        files = request.FILES.getlist('documents')
        if files:
            handle_document_upload(
                user=request.user,
                tool_name='Inspection',
                inspection=inspection,
                files=files,
                district=inspection.district,
                taluka=inspection.taluka,
                village=inspection.village,
                gut_number=inspection.gut_number
            )
        
        return redirect('inspection_list')
    return render(request, "inspection_form.html")

@login_required
def dashboard(request):
    if not request.user.is_superuser:
        return redirect('/tools/')
    return render(request, "dashboard.html")


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



@api_login_required
def get_guts_by_village(request, district, taluka, village):
    """Fetch list of gut numbers for a specific village from pune_ring_road schema"""
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT gut_no
                FROM pune_ring_road.prj_gut_bd
                WHERE district = %s AND taluka = %s AND village = %s AND gut_no IS NOT NULL
                ORDER BY gut_no;
            """, [district, taluka, village])
            guts = [row[0] for row in cursor.fetchall()]
            return JsonResponse({'guts': guts})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
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

@login_required
def inspection_list(request):
    inspections = Inspection.objects.all().order_by('-id')
    # Prefetch documents for each inspection
    for inspection in inspections:
        inspection.documents_list = inspection.get_documents()
    return render(request, "inspection_list.html", {"inspections": inspections})

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

        def clean_optional_char(value):
            if value is None:
                return ""
            value = str(value).strip()
            if value == "" or value.lower() in {"none", "null"}:
                return ""
            return value

        def clean_optional_float(value):
            if value is None:
                return None
            value = str(value).strip()
            if value == "" or value.lower() in {"none", "null"}:
                return None
            if value is None:
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        if request.method == "POST":

            # âœ… Update main inspection
            inspection.district = request.POST.get("district")
            inspection.taluka = request.POST.get("taluka")
            inspection.village = request.POST.get("village")
            inspection.gut_number = request.POST.get("survey")
            inspection.officer = request.POST.get("officer")
            inspection.date = request.POST.get("date")
            inspection.save()

            # âœ… Delete old tree data
            tree_details.delete()

            # âœ… Save new rows
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
                        plot=clean_optional_char(plots[i]),
                        name=clean_optional_char(names[i]),
                        length=clean_optional_float(lengths[i]),
                        width=clean_optional_float(widths[i]),
                        girth=clean_optional_float(girths[i]),
                        height=clean_optional_float(heights[i]),
                    )
            
            # Handle additional document uploads using centralized system
            files = request.FILES.getlist('documents')
            if files:
                handle_document_upload(
                    user=request.user,
                    tool_name='Inspection',
                    inspection=inspection,
                    files=files,
                    district=inspection.district,
                    taluka=inspection.taluka,
                    village=inspection.village,
                    gut_number=inspection.gut_number
                )

            return redirect('inspection_list')
        
        # Get existing documents
        documents = inspection.get_documents()
        return render(request, "edit_inspection.html", {
            "inspection": inspection,
            "tree_details": tree_details,
            "documents": documents
        })

    except Inspection.DoesNotExist:
        return HttpResponse("Record not found")


@login_required
def download_all_inspections_csv(request):
    inspections = Inspection.objects.all().order_by('id')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="all_inspections.csv"'
    response.write('\ufeff')  # Excel UTF-8 BOM fix

    writer = csv.writer(response)

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
            writer.writerow([
                inspection.id,
                inspection.district,
                inspection.taluka,
                inspection.village,
                inspection.gut_number,
                inspection.officer,
                inspection.date,
                '',
                '',
                '',
                '',
                '',
                ''
            ])

    return response

@login_required
def get_tree_master_list(request):
    try:
        trees = TreeMaster.objects.all().values("id", "tree_name_marathi")
        return JsonResponse({"trees": list(trees)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

def get_asset_fields_by_type(request, asset_code):
    try:
        asset_type = AssetTypeMaster.objects.get(asset_code=asset_code, is_active=True)

        fields = AssetFieldMaster.objects.filter(
            asset_type=asset_type,
            is_active=True
        ).order_by("display_order", "id")

        data = [
            {
                "field_name": field.field_name,
                "field_label_marathi": field.field_label_marathi,
                "field_label_english": field.field_label_english,
                "field_type": field.field_type,
                "unit": field.unit,
                "is_required": field.is_required,
                "display_order": field.display_order,
            }
            for field in fields
        ]

        return JsonResponse({
            "success": True,
            "asset_code": asset_type.asset_code,
            "asset_name_marathi": asset_type.asset_name_marathi,
            "fields": data
        })

    except AssetTypeMaster.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Asset type not found"
        }, status=404)
        
@login_required
def asset_creation(request):
    asset_types = AssetTypeMaster.objects.filter(is_active=True).order_by("display_order", "asset_name_marathi")

    if request.method == "POST":
        asset = Asset.objects.create(
            user=request.user,
            asset_type=request.POST.get("asset_type"),
            asset_name=request.POST.get("asset_name"),
            district=request.POST.get("district"),
            taluka=request.POST.get("taluka"),
            village=request.POST.get("village"),
            gut_number=request.POST.get("gut_number"),
            survey_date=request.POST.get("survey_date") or None,
            rate=request.POST.get("rate") or 0,
            government_estimated_rate=request.POST.get("government_estimated_rate") or None,
            formula_text=request.POST.get("formula_text"),
            total_measurement=request.POST.get("total_measurement") or None,
            final_calculation=request.POST.get("final_calculation"),
            final_amount=request.POST.get("final_amount") or None,
            government_final_amount=request.POST.get("government_final_amount") or None,
            remarks=request.POST.get("remarks"),
        )

        field_names = request.POST.getlist("measurement_field_name[]")
        field_labels = request.POST.getlist("measurement_field_label[]")
        field_values = request.POST.getlist("measurement_field_value[]")
        field_units = request.POST.getlist("measurement_field_unit[]")

        for i in range(len(field_names)):
            if field_names[i] and field_values[i] != "":
                AssetMeasurement.objects.create(
                    asset=asset,
                    field_name=field_names[i],
                    field_label=field_labels[i] if i < len(field_labels) else field_names[i],
                    field_value=field_values[i] or None,
                    unit=field_units[i] if i < len(field_units) else "",
                )
        
        # Handle document uploads using centralized system
        files = request.FILES.getlist('documents')
        if files:
            handle_document_upload(
                user=request.user,
                tool_name='Asset',
                asset=asset,
                files=files,
                district=asset.district,
                taluka=asset.taluka,
                village=asset.village,
                gut_number=asset.gut_number
            )

        return redirect("asset_list")

    return render(request, "asset_creation.html", {
        "asset_types": asset_types
    })

@login_required
def get_asset_fields_by_type(request, asset_code):
    try:
        asset_type = AssetTypeMaster.objects.get(asset_code=asset_code, is_active=True)

        fields = AssetFieldMaster.objects.filter(
            asset_type=asset_type,
            is_active=True
        ).order_by("display_order", "id")

        formula = AssetFormulaMaster.objects.filter(
            asset_type=asset_type,
            is_active=True
        ).first()

        field_data = [
            {
                "field_name": field.field_name,
                "field_label_marathi": field.field_label_marathi,
                "field_label_english": field.field_label_english,
                "field_type": field.field_type,
                "unit": field.unit,
                "is_required": field.is_required,
                "display_order": field.display_order,
            }
            for field in fields
        ]

        allowed_fields = {field.field_name for field in fields}
        allowed_fields.add("rate")

        formula_payload = {
            "formula_label_marathi": "",
            "formula_label_english": "",
            "formula_expression": "",
            "is_valid": False,
            "invalid_fields": [],
        }

        if formula and formula.formula_expression:
            used_variables = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", formula.formula_expression))
            invalid_fields = sorted(list(used_variables - allowed_fields))

            if not invalid_fields:
                formula_payload = {
                    "formula_label_marathi": formula.formula_label_marathi or "",
                    "formula_label_english": formula.formula_label_english or "",
                    "formula_expression": formula.formula_expression or "",
                    "is_valid": True,
                    "invalid_fields": [],
                }
            else:
                formula_payload = {
                    "formula_label_marathi": "",
                    "formula_label_english": "",
                    "formula_expression": "",
                    "is_valid": False,
                    "invalid_fields": invalid_fields,
                }

        return JsonResponse({
            "success": True,
            "asset_code": asset_type.asset_code,
            "asset_name_marathi": asset_type.asset_name_marathi,
            "fields": field_data,
            "formula": formula_payload,
        })

    except AssetTypeMaster.DoesNotExist:
        return JsonResponse({
            "success": False,
            "message": "Asset type not found"
        }, status=404)
    return render(request, "asset_creation.html")

@login_required
@login_required
def doc_upload(request):
    if request.method == "POST":
        doc_type = request.POST.get('document_type')
        
        # Get or create the Document Management tool
        tool, _ = ToolMaster.objects.get_or_create(
            tool_name='Document Management'
        )
        
        # Create Document record (for metadata)
        doc = Document.objects.create(
            user=request.user,
            document_type=doc_type,
            document_level=request.POST.get('document_level'),
            district=request.POST.get('district'),
            taluka=request.POST.get('taluka') or None,
            village=request.POST.get('village') or None,
            gut_number=request.POST.get('gut_number') or None,
            document_name=request.POST.get('document_name'),
            description=request.POST.get('description') or None,
            document_date=request.POST.get('document_date') or None,
            court_date=request.POST.get('court_date') or None,
            owner_name=request.POST.get('owner_name') or None,
            matter_type=request.POST.get('matter_type') or None,
        )
        
        # Handle multiple document uploads using centralized system
        files = request.FILES.getlist('documents')
        if files:
            # Create DocumentMaster with document_type and matter_type
            doc_master = DocumentMaster.objects.create(
                user=request.user,
                tool=tool,
                document_tool_record=doc,
                document_type=doc_type,
                matter_type=request.POST.get('matter_type') or None,
                district=request.POST.get('district'),
                taluka=request.POST.get('taluka') or None,
                village=request.POST.get('village') or None,
                gut_number=request.POST.get('gut_number') or None,
            )
            
            # Create attachments for each file
            for file in files:
                DocumentAttachment.objects.create(
                    document_master=doc_master,
                    file=file
                )
        
        return redirect(f'/tools/documents/?tab={doc_type}')

    tab = request.GET.get('tab', 'general')
    return render(request, 'doc_upload.html', {'active_tab': tab})


@login_required
def doc_delete(request, id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    doc = get_object_or_404(Document, id=id, user=request.user)
    doc_masters = doc.get_documents()
    if doc_masters.exists():
        doc_masters.delete()
    doc.delete()
    return JsonResponse({'success': True})


@login_required
def doc_edit(request, id):
    doc = get_object_or_404(Document, id=id, user=request.user)
    if request.method == 'GET':
        # Get file URL from centralized system
        file_url = ''
        doc_masters = doc.get_documents()
        if doc_masters.exists():
            first_doc_master = doc_masters.first()
            if first_doc_master.attachments.exists():
                first_attachment = first_doc_master.attachments.first()
                if first_attachment.file:
                    file_url = first_attachment.file.url
        
        return JsonResponse({
            'id': doc.id,
            'document_type': doc.document_type,
            'document_level': doc.document_level,
            'district': doc.district,
            'taluka': doc.taluka or '',
            'village': doc.village or '',
            'gut_number': doc.gut_number or '',
            'document_name': doc.document_name,
            'description': doc.description or '',
            'document_date': doc.document_date.strftime('%Y-%m-%d') if doc.document_date else '',
            'court_date': doc.court_date.strftime('%Y-%m-%d') if doc.court_date else '',
            'owner_name': doc.owner_name or '',
            'matter_type': doc.matter_type or '',
            'file_url': file_url,
        })
    if request.method == 'POST':
        doc.document_level = request.POST.get('document_level', doc.document_level)
        doc.district = request.POST.get('district', doc.district)
        doc.taluka = request.POST.get('taluka') or None
        doc.village = request.POST.get('village') or None
        doc.gut_number = request.POST.get('gut_number') or None
        doc.document_name = request.POST.get('document_name', doc.document_name)
        doc.description = request.POST.get('description') or None
        doc.document_date = request.POST.get('document_date') or None
        doc.court_date = request.POST.get('court_date') or None
        doc.owner_name = request.POST.get('owner_name') or None
        doc.matter_type = request.POST.get('matter_type') or None
        
        # Handle new file upload
        if request.FILES.get('document'):
            # Get or create tool
            tool, _ = ToolMaster.objects.get_or_create(tool_name='Document Management')
            
            # Get or create DocumentMaster for this document
            doc_master = DocumentMaster.objects.filter(document_tool_record=doc).first()
            if not doc_master:
                doc_master = DocumentMaster.objects.create(
                    user=request.user,
                    tool=tool,
                    document_tool_record=doc,
                    document_type=doc.document_type,
                    matter_type=doc.matter_type,
                    district=doc.district,
                    taluka=doc.taluka,
                    village=doc.village,
                    gut_number=doc.gut_number,
                )
            
            # Add new attachment
            DocumentAttachment.objects.create(
                document_master=doc_master,
                file=request.FILES.get('document')
            )
        
        doc.save()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
def doc_list_api(request):
    doc_type = request.GET.get('type', 'general')
    docs = Document.objects.filter(document_type=doc_type, user=request.user).order_by('-uploaded_at')
    matter_labels = dict(Document.MATTER_TYPE_CHOICES)
    data = []
    for d in docs:
        # Get associated documents from centralized system
        doc_masters = d.get_documents()
        if not doc_masters.exists():
            continue
        
        # Get the first attachment if available
        first_attachment = None
        ext = ''
        file_url = ''
        
        if doc_masters.exists():
            first_doc_master = doc_masters.first()
            if first_doc_master.attachments.exists():
                first_attachment = first_doc_master.attachments.first()
                if first_attachment.file:
                    file_url = first_attachment.file.url
                    ext = first_attachment.file.name.rsplit('.', 1)[-1].lower() if '.' in first_attachment.file.name else ''

        # Skip orphaned document records with no backing attachment.
        if not file_url:
            continue
        
        data.append({
            'id': d.id,
            'document_name': d.document_name,
            'document_level': d.document_level,
            'district': d.district,
            'taluka': d.taluka or '',
            'village': d.village or '',
            'gut_number': d.gut_number or '',
            'description': d.description or '',
            'document_date': d.document_date.strftime('%d/%m/%Y') if d.document_date else '',
            'court_date': d.court_date.strftime('%d/%m/%Y') if d.court_date else '',
            'owner_name': d.owner_name or '',
            'matter_type': d.matter_type or '',
            'matter_type_display': matter_labels.get(d.matter_type, '') if d.matter_type else '',
            'uploaded_at': d.uploaded_at.strftime('%d/%m/%Y'),
            'file_url': file_url,
            'ext': ext,
        })
    return JsonResponse({'documents': data})


@api_login_required
def get_filtered_documents(request):
    """Return documents for the exact selected location level with real uploaded files only."""
    import re as _re
    district = request.GET.get('district') or None
    taluka   = request.GET.get('taluka')   or None
    village  = request.GET.get('village')  or None
    gut      = request.GET.get('gut')      or None

    if not district:
        return JsonResponse({'documents': []})

    if gut and village and taluka and district:
        numeric = _re.search(r'\d+', gut)
        if numeric:
            num = numeric.group()
            qs = Document.objects.filter(
                document_level='gut',
                district__iexact=district,
                taluka__iexact=taluka,
                village__iexact=village,
                gut_number__iregex=r'(^|[^0-9])' + num + r'([^0-9]|$)'
            ).order_by('-uploaded_at')
        else:
            qs = Document.objects.filter(
                document_level='gut',
                district__iexact=district, taluka__iexact=taluka,
                village__iexact=village, gut_number__iexact=gut
            ).order_by('-uploaded_at')

    elif village and taluka and district:
        qs = Document.objects.filter(
            document_level='village',
            district__iexact=district,
            taluka__iexact=taluka,
            village__iexact=village
        ).order_by('-uploaded_at')

    elif taluka and district:
        qs = Document.objects.filter(
            document_level='taluka',
            district__iexact=district,
            taluka__iexact=taluka
        ).order_by('-uploaded_at')

    else:
        qs = Document.objects.filter(
            document_level='district',
            district__iexact=district
        ).order_by('-uploaded_at')

    data = []
    for d in qs:
        for dm in d.get_documents():
            for att in dm.attachments.all():
                if att.file:
                    data.append({
                        'id': d.id,
                        'document_name': d.document_name,
                        'file_url': att.file.url,
                        'ext': att.file.name.rsplit('.', 1)[-1].lower() if '.' in att.file.name else '',
                        'uploaded_at': d.uploaded_at.strftime('%d/%m/%Y'),
                        'document_type': d.document_type,
                        'document_level': d.document_level,
                        'uploaded_by': d.user.username if d.user else '',
                        'uploaded_by_id': d.user_id,
                        'location': ' â€º '.join(filter(None, [d.district, d.taluka, d.village, d.gut_number])),
                    })

    return JsonResponse({'documents': data})
@login_required
def asset_list(request):
    assets = Asset.objects.all().order_by('-id')
    for asset in assets:
        asset.documents_list = DocumentMaster.objects.filter(asset=asset).prefetch_related('attachments')
    return render(request, 'asset_list.html', {'assets': assets})

@login_required
def delete_asset(request, id):
    asset = Asset.objects.get(id=id)
    asset.delete()
    return redirect('asset_list')

@login_required
def edit_asset(request, id):
    asset = Asset.objects.get(id=id)

    if request.method == "POST":
        asset.asset_name = request.POST.get("asset_name")
        asset.district = request.POST.get("district")
        asset.taluka = request.POST.get("taluka")
        asset.village = request.POST.get("village")
        asset.gut_number = request.POST.get("gut_number")
        asset.survey_date = request.POST.get("survey_date") or None
        asset.rate = request.POST.get("rate") or 0
        asset.government_estimated_rate = request.POST.get("government_estimated_rate") or None
        asset.final_amount = request.POST.get("final_amount") or None
        asset.government_final_amount = request.POST.get("government_final_amount") or None
        asset.remarks = request.POST.get("remarks")
        asset.save()

        files = request.FILES.getlist('documents')
        if files:
            handle_document_upload(
                user=request.user,
                tool_name='Asset',
                asset=asset,
                files=files,
                district=asset.district,
                taluka=asset.taluka,
                village=asset.village,
                gut_number=asset.gut_number
            )

        return redirect('asset_list')

    documents = DocumentMaster.objects.filter(asset=asset).prefetch_related('attachments')
    return render(request, 'edit_asset.html', {'asset': asset, 'documents': documents})





@login_required
@csrf_exempt
@require_http_methods(["POST", "PUT", "GET"])
def add_entry(request):
    def _to_decimal(payload, key, default=None):
        value = payload.get(key)
        if value is None or value == "":
            return default
        try:
            return Decimal(str(value))
        except Exception:
            return default

    def _round0(value):
        return value.quantize(Decimal('1'), rounding='ROUND_HALF_UP')

    if request.method == "GET":
        entry_id = request.GET.get('id')
        if not entry_id:
            return render(request, 'add_entries.html')

        entry = get_object_or_404(Entry, id=entry_id)
        entry_data = {
            'id': entry.id,
            'district': entry.district,
            'taluka': entry.taluka,
            'village': entry.village,
            'sr_no_02': entry.sr_no_02,
            'owner_name_03': entry.owner_name_03,
            'land_class_04': entry.land_class_04,
            'total_area_05': float(entry.total_area_05) if entry.total_area_05 is not None else None,
            'total_assessment_06': float(entry.total_assessment_06) if entry.total_assessment_06 is not None else None,
            'per_hectare_assessment_07': float(entry.per_hectare_assessment_07) if entry.per_hectare_assessment_07 is not None else None,
            'land_group_08': entry.land_group_08,
            'to_create_09': float(entry.to_create_09) if entry.to_create_09 is not None else None,
            'shighrasiddha_number_10': entry.shighrasiddha_number_10,
            'committee_market_rate_12': float(entry.committee_market_rate_12) if entry.committee_market_rate_12 is not None else None,
            'land_type_13': entry.land_type_13,
            'considered_market_rate_14': float(entry.considered_market_rate_14) if entry.considered_market_rate_14 is not None else None,
            'market_value_15a': float(entry.market_value_15a) if entry.market_value_15a is not None else None,
            'zone_15b': entry.zone_15b,
            'coefficient_15c': float(entry.coefficient_15c) if entry.coefficient_15c is not None else None,
            'total_market_value_15d': float(entry.total_market_value_15d) if entry.total_market_value_15d is not None else None,
            'fruit_trees_16a': float(entry.fruit_trees_16a) if entry.fruit_trees_16a is not None else None,
            'forest_trees_16b': float(entry.forest_trees_16b) if entry.forest_trees_16b is not None else None,
            'construction_16c': float(entry.construction_16c) if entry.construction_16c is not None else None,
            'other_assets_16d': float(entry.other_assets_16d) if entry.other_assets_16d is not None else None,
            'total_assets_16e': float(entry.total_assets_16e) if entry.total_assets_16e is not None else None,
            'determined_compensation_17': float(entry.determined_compensation_17) if entry.determined_compensation_17 is not None else None,
            'solatium_amount_18': float(entry.solatium_amount_18) if entry.solatium_amount_18 is not None else None,
            'notification_date': entry.notification_date.strftime('%Y-%m-%d') if entry.notification_date else None,
            'award_date': entry.award_date.strftime('%Y-%m-%d') if entry.award_date else None,
            'days_difference': entry.days_difference,
            'additional_12_percent_19': float(entry.additional_12_percent_19) if entry.additional_12_percent_19 is not None else None,
            'non_consent_compensation_20': float(entry.non_consent_compensation_20) if entry.non_consent_compensation_20 is not None else None,
            'class2_deduction_21': float(entry.class2_deduction_21) if entry.class2_deduction_21 is not None else None,
            'payable_non_consent_22': float(entry.payable_non_consent_22) if entry.payable_non_consent_22 is not None else None,
            'consent_bonus_23': float(entry.consent_bonus_23) if entry.consent_bonus_23 is not None else None,
            'consent_total_24': float(entry.consent_total_24) if entry.consent_total_24 is not None else None,
            'class2_deduction_consent_25': float(entry.class2_deduction_consent_25) if entry.class2_deduction_consent_25 is not None else None,
            'payable_consent_26': float(entry.payable_consent_26) if entry.payable_consent_26 is not None else None,
            'establishment_expense_percent': float(entry.establishment_expense_percent) if entry.establishment_expense_percent is not None else None,
            'facility_amount_percent': float(entry.facility_amount_percent) if entry.facility_amount_percent is not None else None,
            'is_with_consent': entry.is_with_consent,
        }
        return JsonResponse({'success': True, 'entry': entry_data})

    is_json_request = (request.content_type == 'application/json') or (request.method == 'PUT')

    try:
        data = json.loads(request.body or '{}') if is_json_request else request.POST

        entry_id = data.get('entry_id')
        entry = get_object_or_404(Entry, id=entry_id) if entry_id else Entry()

        entry.district = data.get('district') or ''
        entry.taluka = data.get('taluka') or None
        entry.village = data.get('village') or None
        entry.sr_no_02 = data.get('sr_no_02') or None
        entry.owner_name_03 = data.get('owner_name_03') or None
        entry.land_class_04 = data.get('land_class_04') or None

        entry.total_area_05 = _to_decimal(data, 'total_area_05')
        entry.total_assessment_06 = _to_decimal(data, 'total_assessment_06')

        if entry.total_area_05 and entry.total_assessment_06 and entry.total_area_05 != 0:
            entry.per_hectare_assessment_07 = entry.total_assessment_06 / entry.total_area_05
            per_hectare = float(entry.per_hectare_assessment_07)
            if per_hectare <= 1.25:
                entry.land_group_08 = "I"
            elif per_hectare <= 2.5:
                entry.land_group_08 = "II"
            elif per_hectare <= 5:
                entry.land_group_08 = "III"
            elif per_hectare <= 7.5:
                entry.land_group_08 = "IV"
            elif per_hectare <= 10:
                entry.land_group_08 = "V"
            elif per_hectare <= 12.5:
                entry.land_group_08 = "VI"
            else:
                entry.land_group_08 = "VII"
        else:
            entry.per_hectare_assessment_07 = None
            entry.land_group_08 = None

        entry.to_create_09 = _to_decimal(data, 'to_create_09')
        entry.shighrasiddha_number_10 = data.get('shighrasiddha_number_10') or None
        entry.committee_market_rate_12 = _to_decimal(data, 'committee_market_rate_12')
        entry.land_type_13 = data.get('land_type_13') or None
        entry.zone_15b = data.get('zone_15b') or None
        entry.coefficient_15c = _to_decimal(data, 'coefficient_15c', Decimal('0'))

        entry.fruit_trees_16a = _to_decimal(data, 'fruit_trees_16a', Decimal('0'))
        entry.forest_trees_16b = _to_decimal(data, 'forest_trees_16b', Decimal('0'))
        entry.construction_16c = _to_decimal(data, 'construction_16c', Decimal('0'))
        entry.other_assets_16d = _to_decimal(data, 'other_assets_16d', Decimal('0'))

        entry.establishment_expense_percent = _to_decimal(data, 'establishment_expense_percent', Decimal('0'))
        entry.facility_amount_percent = _to_decimal(data, 'facility_amount_percent', Decimal('0'))
        entry.is_with_consent = str(data.get('is_with_consent', '')).lower() in ('1', 'true', 'on', 'yes')

        if entry.committee_market_rate_12 is not None:
            multiplier = Decimal('1')
            if entry.land_type_13 == "?????? ??????":
                multiplier = Decimal('1.5')
            elif entry.land_type_13 == "??????":
                multiplier = Decimal('2')
            entry.considered_market_rate_14 = entry.committee_market_rate_12 * multiplier
        else:
            entry.considered_market_rate_14 = None

        if entry.considered_market_rate_14 is not None and entry.to_create_09 is not None:
            entry.market_value_15a = _round0(entry.considered_market_rate_14 * entry.to_create_09)
        else:
            entry.market_value_15a = None

        if entry.market_value_15a is not None and entry.coefficient_15c is not None:
            entry.total_market_value_15d = _round0(entry.market_value_15a * entry.coefficient_15c)
        else:
            entry.total_market_value_15d = None

        entry.total_assets_16e = _round0(
            (entry.fruit_trees_16a or Decimal('0')) +
            (entry.forest_trees_16b or Decimal('0')) +
            (entry.construction_16c or Decimal('0')) +
            (entry.other_assets_16d or Decimal('0'))
        )

        if entry.total_market_value_15d is not None:
            entry.determined_compensation_17 = _round0(entry.total_market_value_15d + entry.total_assets_16e)
            entry.solatium_amount_18 = _round0(entry.determined_compensation_17)
        else:
            entry.determined_compensation_17 = None
            entry.solatium_amount_18 = None

        entry.notification_date = data.get('notification_date') or None
        entry.award_date = data.get('award_date') or None
        entry.days_difference = int(data.get('days_difference') or 0)

        if entry.solatium_amount_18 is not None:
            entry.consent_bonus_23 = _round0(entry.solatium_amount_18 * Decimal('0.25'))
            entry.additional_12_percent_19 = _round0(
                ((entry.solatium_amount_18 + entry.consent_bonus_23) * Decimal('0.12') / Decimal('365')) * Decimal(str(entry.days_difference or 0))
            )
            entry.non_consent_compensation_20 = _round0(
                entry.determined_compensation_17 + entry.solatium_amount_18 + entry.additional_12_percent_19
            )
        else:
            entry.consent_bonus_23 = None
            entry.additional_12_percent_19 = None
            entry.non_consent_compensation_20 = None

        if entry.non_consent_compensation_20 is not None:
            entry.class2_deduction_21 = _round0(entry.non_consent_compensation_20 * Decimal('0.10')) if entry.land_class_04 == "2" else Decimal('0')
            base_non_consent = entry.non_consent_compensation_20 - entry.class2_deduction_21
            est_add_nc = base_non_consent * (entry.establishment_expense_percent or Decimal('0')) / Decimal('100')
            fac_add_nc = base_non_consent * (entry.facility_amount_percent or Decimal('0')) / Decimal('100')
            entry.payable_non_consent_22 = _round0(base_non_consent + est_add_nc + fac_add_nc)

            entry.consent_total_24 = _round0(entry.non_consent_compensation_20 + (entry.consent_bonus_23 or Decimal('0')))
            entry.class2_deduction_consent_25 = _round0(entry.consent_total_24 * Decimal('0.10')) if entry.land_class_04 == "2" else Decimal('0')

            base_consent = entry.consent_total_24 - entry.class2_deduction_consent_25
            est_add_c = base_consent * (entry.establishment_expense_percent or Decimal('0')) / Decimal('100')
            fac_add_c = base_consent * (entry.facility_amount_percent or Decimal('0')) / Decimal('100')
            entry.payable_consent_26 = _round0(base_consent + est_add_c + fac_add_c)
        else:
            entry.class2_deduction_21 = None
            entry.payable_non_consent_22 = None
            entry.consent_total_24 = None
            entry.class2_deduction_consent_25 = None
            entry.payable_consent_26 = None

        entry.save()

        calculations = {
            'per_hectare_assessment_07': float(entry.per_hectare_assessment_07) if entry.per_hectare_assessment_07 is not None else None,
            'land_group_08': entry.land_group_08,
            'considered_market_rate_14': float(entry.considered_market_rate_14) if entry.considered_market_rate_14 is not None else None,
            'market_value_15a': float(entry.market_value_15a) if entry.market_value_15a is not None else None,
            'total_market_value_15d': float(entry.total_market_value_15d) if entry.total_market_value_15d is not None else None,
            'total_assets_16e': float(entry.total_assets_16e) if entry.total_assets_16e is not None else None,
            'determined_compensation_17': float(entry.determined_compensation_17) if entry.determined_compensation_17 is not None else None,
            'solatium_amount_18': float(entry.solatium_amount_18) if entry.solatium_amount_18 is not None else None,
            'additional_12_percent_19': float(entry.additional_12_percent_19) if entry.additional_12_percent_19 is not None else None,
            'non_consent_compensation_20': float(entry.non_consent_compensation_20) if entry.non_consent_compensation_20 is not None else None,
            'class2_deduction_21': float(entry.class2_deduction_21) if entry.class2_deduction_21 is not None else None,
            'payable_non_consent_22': float(entry.payable_non_consent_22) if entry.payable_non_consent_22 is not None else None,
            'consent_bonus_23': float(entry.consent_bonus_23) if entry.consent_bonus_23 is not None else None,
            'consent_total_24': float(entry.consent_total_24) if entry.consent_total_24 is not None else None,
            'class2_deduction_consent_25': float(entry.class2_deduction_consent_25) if entry.class2_deduction_consent_25 is not None else None,
            'payable_consent_26': float(entry.payable_consent_26) if entry.payable_consent_26 is not None else None,
            'establishment_expense_percent': float(entry.establishment_expense_percent) if entry.establishment_expense_percent is not None else None,
            'facility_amount_percent': float(entry.facility_amount_percent) if entry.facility_amount_percent is not None else None,
        }
        message = '???? ???????????? ????? ????!' if entry_id else '???? ???????????? ??? ????!'

        if is_json_request:
            return JsonResponse({
                'success': True,
                'entry_id': entry.id,
                'message': message,
                'calculations': calculations,
            })

        return render(request, 'add_entries.html', {'success': True, 'entry_id': entry.id})
    except Exception as e:
        if is_json_request:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        return render(request, 'add_entries.html', {'error': str(e)})


@api_login_required
def get_rr_rate_by_village(request, village):
    """Return all 2025-2026 ready reckoner assessment types and rates for a village."""
    qs = ReadyReckonerInfo.objects.filter(village__iexact=village, year='2025-2026').prefetch_related('rates').order_by('assessment_type')
    if not qs.exists():
        return JsonResponse({'found': False, 'assessment_types': []})
    types = []
    for info in qs:
        # Use the highest rate from child rates for display
        top_rate = info.rates.order_by('-rate').first()
        if top_rate:
            types.append({'assessment_type': info.assessment_type, 'rate': float(top_rate.rate),
                'unit': info.unit, 'year': info.year})
    return JsonResponse({'found': bool(types), 'assessment_types': types})