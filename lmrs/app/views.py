from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.sessions.models import Session
from .models import Inspection, ReadyReckonerInfo, ReadyReckonerRate, LandRecord712, FarmerNames,TreeMaster, Asset, AssetMeasurement, AssetTypeMaster, AssetFieldMaster, AssetFormulaMaster, Document, ToolMaster, DocumentMaster, DocumentAttachment, Entry, VillageData, VillageData8ARecord, VillageDataSec15Rate, VillageDataFile, VillageData8AFile, VillageData15_2Row, VillageData15_2RowFile, VillageData18_1Row, VillageData18_1RowFile, ActiveUserSession, AssetDetail
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseForbidden
from django.db import connection
from django.core.files.base import ContentFile
import csv
import re
import json
import os
import requests
from io import BytesIO
import unicodedata
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont, ImageOps
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.dateparse import parse_date
from datetime import date as datetime_date
from django.utils import timezone

def clean_optional_char(value):
    if value is None:
        return ""
    value = str(value).strip()
    if value == "" or value.lower() in {"none", "null"}:
        return ""
    return value


def clean_optional_decimal(value):
    cleaned = clean_optional_char(value)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (ArithmeticError, ValueError):
        return None


def clean_asset_parameter(raw_value):
    if not raw_value:
        return {}

    try:
        payload = json.loads(raw_value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    cleaned = {}
    for field_name, metadata in payload.items():
        if not isinstance(metadata, dict):
            continue

        value = metadata.get("value")
        if value is None:
            continue

        if isinstance(value, str):
            value = value.strip()

        if value in {"", "None", "null"}:
            continue

        cleaned[field_name] = {
            "label": clean_optional_char(metadata.get("label")) or field_name,
            "value": str(value),
            "unit": clean_optional_char(metadata.get("unit")),
            "type": clean_optional_char(metadata.get("type")) or "text",
        }

    return cleaned


def build_asset_detail_rows_from_request(request):
    plots = request.POST.getlist("plot[]")
    names = request.POST.getlist("name[]")
    valuations = request.POST.getlist("valuation[]")
    parameters = request.POST.getlist("asset_parameter[]")

    row_count = max(len(plots), len(names), len(valuations), len(parameters))
    detail_rows = []

    for index in range(row_count):
        plot = clean_optional_char(plots[index]) if index < len(plots) else ""
        name = clean_optional_char(names[index]) if index < len(names) else ""
        valuation = clean_optional_decimal(valuations[index]) if index < len(valuations) else None
        asset_parameter = clean_asset_parameter(parameters[index]) if index < len(parameters) else {}

        if not name and not plot and valuation is None and not asset_parameter:
            continue

        detail_rows.append({
            "plot": plot,
            "name": name,
            "valuation": valuation,
            "asset_parameter": asset_parameter,
        })

    return detail_rows


def inspection_request_has_uploads(request, detail_rows):
    for index, _row in enumerate(detail_rows):
        if request.FILES.getlist(f"row_doc_{index}") or request.FILES.getlist(f"row_cam_{index}"):
            return True
    return False


def clear_inspection_attachments(inspection):
    doc_master = DocumentMaster.objects.filter(inspection=inspection).first()
    if not doc_master:
        return

    for attachment in doc_master.attachments.all():
        if attachment.file:
            attachment.file.delete(save=False)
        attachment.delete()


def save_asset_detail_rows(inspection, detail_rows, request=None):
    for i, row in enumerate(detail_rows):
        asset_params = row["asset_parameter"]
        
        if request:
            # Try direct access to files
            row_docs_key = f"row_doc_{i}"
            row_cam_key = f"row_cam_{i}"
            
            row_docs = request.FILES.getlist(row_docs_key) if row_docs_key in request.FILES else []
            row_cam = request.FILES.getlist(row_cam_key) if row_cam_key in request.FILES else []
            
            # Combine both document and camera files, but only take the first from each
            all_files = []
            if row_docs:
                all_files.append(row_docs[0])  # Only take first file
            if row_cam:
                all_files.append(
                    stamp_location_on_photo(
                        row_cam[0],
                        inspection.latitude,
                        inspection.longitude,
                    )
                )  # Only take first camera photo
                
            if all_files:
                doc_master = DocumentMaster.objects.filter(inspection=inspection).first()
                if not doc_master:
                    tool, _ = ToolMaster.objects.get_or_create(tool_name='Inspection', defaults={'is_active': True})
                    doc_master = DocumentMaster.objects.create(
                        user=request.user,
                        tool=tool,
                        inspection=inspection,
                        district=inspection.district,
                        taluka=inspection.taluka,
                        village=inspection.village,
                        gut_number=inspection.gut_number
                    )
                    
                urls = []
                for f in all_files:
                    attachment = DocumentAttachment.objects.create(document_master=doc_master, file=f)
                    urls.append(attachment.file.url)
                
                asset_params["_documents"] = {
                    "id": doc_master.id,
                    "urls": urls
                }

        AssetDetail.objects.create(
            inspection=inspection,
            plot=row["plot"],
            name=row["name"],
            valuation=row["valuation"],
            asset_parameter=asset_params,
        )


def serialize_asset_detail_rows(details):
    rows = []
    for detail in details:
        rows.append({
            "plot": detail.plot or "",
            "name": detail.name or "",
            "valuation": str(detail.valuation) if detail.valuation is not None else "",
            "asset_parameter": detail.asset_parameter or {},
        })
    return rows


def format_asset_parameter_for_display(asset_parameter):
    parts = []
    for field_name, metadata in (asset_parameter or {}).items():
        if not isinstance(metadata, dict):
            continue
        label = clean_optional_char(metadata.get("label")) or field_name
        value = clean_optional_char(metadata.get("value"))
        unit = clean_optional_char(metadata.get("unit"))
        if not value:
            continue
        parts.append(f"{label}: {value}{(' ' + unit) if unit else ''}")
    return ", ".join(parts)


def build_inspection_form_context(inspection=None, detail_rows=None, documents=None, error_message=None):
    asset_types = AssetTypeMaster.objects.filter(is_active=True).order_by("display_order", "asset_name_marathi")
    if detail_rows is None:
        detail_rows = []
    inspection_asset_type = ""
    if inspection:
        if isinstance(inspection, dict):
            inspection_asset_type = inspection.get("inspection_asset_type") or ""
        else:
            inspection_asset_type = inspection.inspection_asset_type or ""
    return {
        "asset_types": asset_types,
        "inspection": inspection,
        "documents": documents or [],
        "detail_rows": detail_rows,
        "today_date": timezone.localdate(),
        "error_message": error_message,
        "selected_asset_type": inspection_asset_type or ("tree_asset" if inspection else ""),
        
    }

def get_valid_inspection_date(raw_date):
    try:
        inspection_date = datetime_date.fromisoformat(raw_date or "")
    except ValueError:
        return None, "कृपया वैध तपासणी दिनांक निवडा."

    if inspection_date > timezone.localdate():
        return None, "तपासणी दिनांक आजच्या दिनांकापेक्षा पुढील असू शकत नाही."

    return inspection_date, None


def get_inspection_latitude(request):
    latitude = clean_optional_decimal(request.POST.get("photo_latitude"))
    if latitude is None or latitude < Decimal("-90") or latitude > Decimal("90"):
        return None
    return latitude


def get_inspection_longitude(request):
    longitude = clean_optional_decimal(request.POST.get("photo_longitude"))
    if longitude is None or longitude < Decimal("-180") or longitude > Decimal("180"):
        return None
    return longitude


def stamp_location_on_photo(uploaded_file, latitude, longitude):
    if latitude is None or longitude is None:
        return uploaded_file

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image).convert("RGB")

        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=max(18, image.width // 45))
        text = f"Lat: {latitude}  Long: {longitude}"
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_height = text_bbox[3] - text_bbox[1]
        padding = max(12, image.width // 80)
        strip_height = text_height + (padding * 2)
        y1 = image.height - strip_height

        draw.rectangle([(0, y1), (image.width, image.height)], fill=(0, 0, 0))
        draw.text((padding, y1 + padding), text, fill=(255, 255, 255), font=font)

        output = BytesIO()
        image_format = "JPEG"
        filename = uploaded_file.name
        if filename.lower().endswith(".png"):
            image_format = "PNG"
        image.save(output, format=image_format, quality=90)
        output.seek(0)

        return ContentFile(output.read(), name=filename)
    except Exception:
        uploaded_file.seek(0)
        return uploaded_file


def api_login_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Unauthorized"}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def get_land_record_api_headers():
    key = (
        os.getenv('7_12_key')
        or os.getenv('SEVEN_TWELVE_KEY')
        or os.getenv('LAND_RECORD_API_KEY')
    )
    if not key:
        return {}
    return {'X-Internal-Auth': key.strip()}

def normalize_match_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()

def build_location_aliases(district, taluka, village):
    """
    Build normalized aliases (English + Marathi) for a selected location.
    This allows matching rows that may come in either language.
    """
    aliases = {
        'district': set(),
        'taluka': set(),
        'village': set(),
    }

    if district:
        aliases['district'].add(normalize_match_text(district))
    if taluka:
        aliases['taluka'].add(normalize_match_text(taluka))
    if village:
        aliases['village'].add(normalize_match_text(village))

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    a.name,
                    COALESCE(NULLIF(dm.district_name_m, ''), ''),
                    c.taluka,
                    COALESCE(NULLIF(tm.taluka_name_m, ''), ''),
                    d.village,
                    COALESCE(NULLIF(vm.village_name_m, ''), '')
                FROM pune_ring_road.prj_district a
                JOIN pune_ring_road.prj_taluka c
                    ON a.district_id = c.district_id
                JOIN pune_ring_road.prj_village d
                    ON c.taluka_id = d.taluka_id
                LEFT JOIN public.district_master dm
                    ON a.district_id = dm.id
                LEFT JOIN public.taluka_master tm
                    ON c.taluka_id = tm.id
                LEFT JOIN public.village_master vm
                    ON d.village_id = vm.id
                WHERE
                    (UPPER(TRIM(a.name)) = UPPER(TRIM(%s))
                     OR UPPER(TRIM(dm.district_name_m)) = UPPER(TRIM(%s)))
                    AND (UPPER(TRIM(c.taluka)) = UPPER(TRIM(%s))
                         OR UPPER(TRIM(tm.taluka_name_m)) = UPPER(TRIM(%s)))
                    AND (UPPER(TRIM(d.village)) = UPPER(TRIM(%s))
                         OR UPPER(TRIM(vm.village_name_m)) = UPPER(TRIM(%s)))
            """, [district, district, taluka, taluka, village, village])

            for row in cursor.fetchall():
                aliases['district'].update(
                    normalize_match_text(v) for v in (row[0], row[1]) if v
                )
                aliases['taluka'].update(
                    normalize_match_text(v) for v in (row[2], row[3]) if v
                )
                aliases['village'].update(
                    normalize_match_text(v) for v in (row[4], row[5]) if v
                )
    except Exception:
        # Fall back to user-selected values only.
        pass

    return aliases

def text_matches_aliases(value, aliases, normalizer=normalize_match_text):
    normalized_value = normalizer(value)
    if not normalized_value:
        return False
    for alias in aliases:
        if alias and (alias in normalized_value or normalized_value in alias):
            return True
    return False

def clean_holder_name_list(value):
    """
    Keep only valid holder names from noisy API strings like:
    "[ Name1, Name2, ------सामाईक क्षेत्र------ ]"
    Rule: if an item starts with special character, ignore it.
    """
    text = str(value or '').strip()
    if not text:
        return ''

    # Remove common wrappers around list-like payload values.
    text = text.strip("[](){}")
    parts = [p.strip().strip('"\'' ) for p in text.split(',')]

    names = []
    for part in parts:
        if not part:
            continue
        first = part[0]
        # Keep names that start with a letter (Marathi/English/other scripts).
        if unicodedata.category(first).startswith('L'):
            names.append(part)

    return ', '.join(names)


def handle_document_upload(user, tool_name, files, district=None, taluka=None, village=None, gut_number=None,
                          inspection=None, rr_info=None, land_record=None, asset=None, entry=None, document_tool_record=None):
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
    elif entry:
        doc_master_kwargs['entry'] = entry
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
    elif entry:
        doc_master = DocumentMaster.objects.filter(entry=entry).first()
    elif document_tool_record:
        doc_master = DocumentMaster.objects.filter(document_tool_record=document_tool_record).first()
    if not doc_master:
        doc_master = DocumentMaster.objects.create(**doc_master_kwargs)
    
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
        village_type = request.POST.get('village_type', '')

        # Allow only one ready reckoner entry per district+taluka+village.
        duplicate_exists = ReadyReckonerInfo.objects.filter(
            district__iexact=(district or '').strip(),
            taluka__iexact=(taluka or '').strip(),
            village__iexact=(village or '').strip()
        ).exists()
        if duplicate_exists:
            return render(request, "readyreckoner.html", {
                "duplicate_error": "या गावासाठी रेडी रेकनर नोंद आधीच अस्तित्वात आहे."
            })

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
                rt = request.POST.get(f'rate[{bi}][{ri}]')
                if rt is None:
                    break
                if village_type == 'prabhav':
                    sv = request.POST.get(f'shighrasiddha_vibhag[{bi}][{ri}]', '')
                    if sv and rt:
                        ReadyReckonerRate.objects.create(
                            rr=info, assessment_range_min=0, assessment_range_max=0,
                            rate=rt, village_type=village_type, shighrasiddha_vibhag=sv
                        )
                else:
                    mn = request.POST.get(f'assessment_range_min[{bi}][{ri}]')
                    mx = request.POST.get(f'assessment_range_max[{bi}][{ri}]')
                    if mn and mx and rt:
                        ReadyReckonerRate.objects.create(
                            rr=info, assessment_range_min=mn, assessment_range_max=mx,
                            rate=rt, village_type=village_type
                        )
                ri += 1
        if files and first_info:
            handle_document_upload(user=request.user, tool_name='Ready Reckoner Rate', rr_info=first_info,
                files=files, district=district, taluka=taluka, village=village)
        return redirect('ready_reckoner_list')
    return render(request, "readyreckoner.html")


@login_required
def check_ready_reckoner_village_exists(request):
    district = (request.GET.get('district') or '').strip()
    taluka = (request.GET.get('taluka') or '').strip()
    village = (request.GET.get('village') or '').strip()

    if not district or not taluka or not village:
        return JsonResponse(
            {'exists': False, 'error': 'district, taluka and village are required'},
            status=400
        )

    exists = ReadyReckonerInfo.objects.filter(
        district__iexact=district,
        taluka__iexact=taluka,
        village__iexact=village
    ).exists()

    return JsonResponse({
        'exists': exists,
        'message': 'या गावासाठी रेडी रेकनर नोंद आधीच अस्तित्वात आहे.' if exists else ''
    })

def get_marathi_name(level, district=None, taluka=None, village=None):
    """Helper function to get Marathi name for a location"""
    try:
        with connection.cursor() as cursor:
            if level == 'district' and district:
                cursor.execute("""
                    SELECT DISTINCT COALESCE(NULLIF(dm.district_name_m, ''), a.name)
                    FROM pune_ring_road.prj_district a
                    LEFT JOIN public.district_master dm ON a.district_id = dm.id
                    WHERE UPPER(TRIM(a.name)) = UPPER(TRIM(%s))
                    LIMIT 1;
                """, [district])
                result = cursor.fetchone()
                return result[0] if result else district
            elif level == 'taluka' and district and taluka:
                cursor.execute("""
                    SELECT DISTINCT COALESCE(NULLIF(tm.taluka_name_m, ''), c.taluka)
                    FROM pune_ring_road.prj_district a
                    JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                    LEFT JOIN public.taluka_master tm ON c.taluka_id = tm.id
                    WHERE UPPER(TRIM(a.name)) = UPPER(TRIM(%s))
                      AND UPPER(TRIM(c.taluka)) = UPPER(TRIM(%s))
                    LIMIT 1;
                """, [district, taluka])
                result = cursor.fetchone()
                return result[0] if result else taluka
            elif level == 'village' and district and taluka and village:
                cursor.execute("""
                    SELECT DISTINCT COALESCE(NULLIF(vm.village_name_m, ''), d.village)
                    FROM pune_ring_road.prj_district a
                    JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                    JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                    LEFT JOIN public.village_master vm ON d.village_id = vm.id
                    WHERE UPPER(TRIM(a.name)) = UPPER(TRIM(%s))
                      AND UPPER(TRIM(c.taluka)) = UPPER(TRIM(%s))
                      AND UPPER(TRIM(d.village)) = UPPER(TRIM(%s))
                    LIMIT 1;
                """, [district, taluka, village])
                result = cursor.fetchone()
                return result[0] if result else village
    except Exception:
        pass
    return district if level == 'district' else (taluka if level == 'taluka' else village)

@login_required
def ready_reckoner_list(request):
    all_records = ReadyReckonerInfo.objects.prefetch_related('rates').all().order_by('district', 'taluka', 'village', 'year', 'id')

    # Group by village+year â€” one entry per village
    from itertools import groupby
    groups = []
    keyfunc = lambda r: (r.district, r.taluka, r.village, r.year)
    for key, items in groupby(all_records, key=keyfunc):
        item_list = list(items)
        anchor = item_list[0]  # first record = anchor for edit/docs
        # Collect all documents across all records in this village+year group
        all_docs = []
        total_attachment_count = 0
        for rec in item_list:
            docs = rec.get_documents()
            all_docs.extend(docs)
            # Count all attachments across all documents for this record
            for doc in docs:
                total_attachment_count += doc.attachments.count()
        
        district_mr = get_marathi_name('district', key[0])
        taluka_mr = get_marathi_name('taluka', key[0], key[1])
        village_mr = get_marathi_name('village', key[0], key[1], key[2])
        
        groups.append({
            'anchor': anchor,
            'records': item_list,
            'all_docs': all_docs,
            'has_docs': any(dm.attachments.exists() for dm in all_docs),
            'total_attachment_count': total_attachment_count,
            'district': key[0],
            'district_mr': district_mr,
            'taluka': key[1],
            'taluka_mr': taluka_mr,
            'village': key[2],
            'village_mr': village_mr,
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
        village_type = request.POST.get('village_type', 'gramin')

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
                    info.user = request.user
                    info.save()
                    # Delete sec15 references before deleting rates (PROTECT FK)
                    VillageDataSec15Rate.objects.filter(rr_rate__rr=info).delete()
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
                sv = request.POST.get(f'shighrasiddha_vibhag[{bi}][{ri}]')
                if mn is None and sv is None:
                    break
                if rt:
                    ReadyReckonerRate.objects.create(
                        rr=info,
                        village_type=village_type,
                        assessment_range_min=mn or 0,
                        assessment_range_max=mx or 0,
                        shighrasiddha_vibhag=sv or '',
                        rate=rt
                    )
                ri += 1

        # Delete records that were removed in the form
        removed_infos = ReadyReckonerInfo.objects.filter(
            village=village, year=year
        ).exclude(id__in=existing_ids_submitted)
        VillageDataSec15Rate.objects.filter(rr_rate__rr__in=removed_infos).delete()
        removed_infos.delete()

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
        # Get all records for this village+year group
        village_records = ReadyReckonerInfo.objects.filter(
            village=anchor.village, 
            year=anchor.year
        )
        
        # Delete dependent sec15 rows only when that table exists (schema may be partial).
        if 'app_villagedatasec15rate' in connection.introspection.table_names():
            for record in village_records:
                VillageDataSec15Rate.objects.filter(rr_rate__rr=record).delete()
        
        # Now we can safely delete the ReadyReckonerInfo records
        # (ReadyReckonerRate records will be cascade deleted automatically)
        village_records.delete()
    
    return redirect('ready_reckoner_list')

@login_required
def download_all_ready_reckoner_csv(request):
    from itertools import groupby
    
    all_records = ReadyReckonerInfo.objects.prefetch_related('rates').all().order_by('district', 'taluka', 'village', 'year', 'id')
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="ready_reckoner_rates.csv"'
    response.write('\ufeff')  # Excel UTF-8 BOM fix
    
    writer = csv.writer(response)
    
    # CSV Header
    header = [
        'जिल्हा (District)',
        'तालुका (Taluka)', 
        'गाव (Village)',
        'वर्ष (Year)',
        'मूल्यदरासाठी गावाचा प्रकार (Village Type)',
        'मूल्यांकन प्रकार (Assessment Type)',
        'एकक (Unit)',
        'आकारणी श्रेणी किमान (Min Range)',
        'आकारणी श्रेणी कमाल (Max Range)', 
        'शिघ्रसिध्द विभाग (Shighrasiddha Vibhag)',
        'दर ₹ (Rate)',
        'Updated Date',
        'Updated By'
    ]
    writer.writerow(header)
    
    # Group by village+year like in the list view
    keyfunc = lambda r: (r.district, r.taluka, r.village, r.year)
    for key, items in groupby(all_records, key=keyfunc):
        item_list = list(items)
        anchor = item_list[0]  # first record for metadata
        
        # Get Marathi names
        district_mr = get_marathi_name('district', key[0])
        taluka_mr = get_marathi_name('taluka', key[0], key[1])
        village_mr = get_marathi_name('village', key[0], key[1], key[2])
        
        # Get village type from first rate if available
        village_type = ''
        if item_list and item_list[0].rates.exists():
            first_rate = item_list[0].rates.first()
            village_type = 'प्रभाव' if first_rate.village_type == 'prabhav' else 'ग्रामीण'
        
        # Write each assessment type and its rates
        for record in item_list:
            if record.rates.exists():
                for rate in record.rates.all():
                    row = [
                        district_mr,
                        taluka_mr,
                        village_mr,
                        record.year,
                        village_type,
                        record.assessment_type,
                        record.unit,
                        rate.assessment_range_min if rate.village_type != 'prabhav' else '',
                        rate.assessment_range_max if rate.village_type != 'prabhav' else '',
                        rate.shighrasiddha_vibhag if rate.village_type == 'prabhav' else '',
                        rate.rate,
                        anchor.updated_at.strftime('%d/%m/%Y %H:%M') if anchor.updated_at else '',
                        anchor.user.username if anchor.user else ''
                    ]
                    writer.writerow(row)
            else:
                # Record without rates
                row = [
                    district_mr,
                    taluka_mr, 
                    village_mr,
                    record.year,
                    village_type,
                    record.assessment_type,
                    record.unit,
                    '',  # min range
                    '',  # max range
                    '',  # shighrasiddha
                    '',  # rate
                    anchor.updated_at.strftime('%d/%m/%Y %H:%M') if anchor.updated_at else '',
                    anchor.user.username if anchor.user else ''
                ]
                writer.writerow(row)
    
    return response

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
    NA_TOKENS = {'', '-', 'na', 'n/a', 'उपलब्ध नाही'}

    def fix_encoding(text):
        try:
            return text.encode('latin1').decode('utf-8')
        except:
            return text

    def normalize_text(value):
        return re.sub(r'\s+', ' ', fix_encoding(str(value or ''))).strip().casefold()

    def normalize_gut(value):
        nums = re.findall(r'\d+', str(value or ''))
        return '/'.join(nums) if nums else ''

    def row_get(row, *keys):
        for key in keys:
            value = row.get(key)
            if value:
                return fix_encoding(str(value).strip())
        return ''

    def as_yes_no(value):
        val = normalize_text(value)
        if val in {'yes', 'होय', 'hoy'}:
            return 'Yes'
        if val in {'no', 'नाही', 'nahi'}:
            return 'No'
        return None

    def clean_optional(value):
        text = str(value or '').strip()
        if text.casefold() in NA_TOKENS:
            return None
        return text

    def fetch_api_rows(uploaded_file):
        api_url = os.getenv(
            'LAND_RECORD_UPLOAD_API_URL',
            'http://209.182.233.103:8005/api/upload-land-record/'
        )
        try:
            uploaded_file.seek(0)
            content = uploaded_file.read().decode('utf-8', errors='ignore').encode('utf-8')

            response = requests.post(
                api_url,
                files={'file': (uploaded_file.name, content, 'text/html')},
                headers=get_land_record_api_headers(),
                timeout=60
            )
            response.raise_for_status()

            payload = json.loads(response.content.decode('utf-8'))

        except requests.RequestException:
            raise ValueError('Service is not working.')
        except ValueError:
            raise ValueError('7/12 API कडून वैध JSON मिळाले नाही.')

        rows = payload.get('eligible', [])
        kul_khand_info = payload.get('कुळ, खंड व इतर अधिकार', '')
        
        if not isinstance(rows, list) or not rows:
            raise ValueError('अपलोड केलेल्या HTML मधून वैध 7/12 डेटा मिळाला नाही.')

        return rows, kul_khand_info

    def validate_and_map_rows(rows, district, taluka, village, gut_number, kul_khand_info):
        matched = []

        location_aliases = build_location_aliases(district, taluka, village)
        selected_gut = normalize_gut(gut_number)

        for row in rows:
            row_district = row_get(row, 'जिल्हा', 'district')
            row_taluka = row_get(row, 'तालुका', 'taluka')
            row_village = row_get(row, 'गावाचे नाव', 'village', 'village_name')
            row_gut = row_get(
                row,
                'गट नंबर/सर्वे नंबर',
                'सर्वे नंबर', 'सर्व्हे नंबर', 'गट क्रमांक', 'गट नंबर',
                'स_नं_ग_न', 'स_नं_ग_न_हिस्सा',
                'gut_number', 'survey_number', 'survey_no', 'survey number', 'survey'
            )

            if not (
                text_matches_aliases(row_district, location_aliases['district'], normalize_text) and
                text_matches_aliases(row_taluka, location_aliases['taluka'], normalize_text) and
                text_matches_aliases(row_village, location_aliases['village'], normalize_text)
            ):
                continue

            normalized_row_gut = normalize_gut(row_gut)
            if selected_gut and normalized_row_gut and selected_gut not in normalized_row_gut:
                continue

            matched.append({
                'gut_number': row_gut,
                'khata_number': row_get(row, 'खाता क्रमांक', 'खाता_नं', 'khata_number'),
                'puid_ulip_no': row_get(row, 'PUID_ULIP_No'),
                'hissa_number': row_get(row, 'हिस्सा क्रमांक', 'स_नं_ग_न_हिस्सा', 'hissa_number'),
                'jirayit': row_get(row, 'जिरायत', 'जिरायात'),
                'bagayat': row_get(row, 'बागायत'),
                'potkharaba': row_get(row, 'पोटखराब'),
                'total_area': row_get(row, 'एकूण क्षेत्र', 'एकूण_क्षेत्र'),
                'aakarni': row_get(row, 'आकारणी', 'आकारणी_रुपये'),
                'khata_area': row_get(row, 'खाते क्षेत्र', 'खाता_क्षेत्र'),
                'aakar': row_get(row, 'आकार'),
                'holder_name': clean_holder_name_list(row_get(row, 'भोगवटादाराचे नांव', 'धारकाचे नाव', 'धारकाचे_नाव')),
                'kul_khand_other_rights': kul_khand_info,  # Add the same कुळ, खंड व इतर अधिकार data to each record
            })

        if not matched:
            raise ValueError('निवडलेल्या ठिकाणाशी HTML मधील माहिती जुळत नाही.')

        return matched

    if request.method == "POST":
        district = request.POST.get('district')
        taluka = request.POST.get('taluka')
        village = request.POST.get('village')
        gut_number = request.POST.get('gut_number')
        uploaded_html = request.FILES.get('document_712')

        try:
            if uploaded_html:
                rows, kul_khand_info = fetch_api_rows(uploaded_html)
                rows_to_save = validate_and_map_rows(rows, district, taluka, village, gut_number, kul_khand_info)
            else:
                raise ValueError('कृपया HTML फाइल अपलोड करा.')

            for row in rows_to_save:
                LandRecord712.objects.create(
                    user=request.user,
                    district=district,
                    taluka=taluka,
                    village=village,
                    gut_number=gut_number,
                    khata_number=clean_optional(row.get('khata_number')),
                    puid_ulip_no=clean_optional(row.get('puid_ulip_no')),
                    hissa_number=clean_optional(row.get('hissa_number')),
                    jirayit=clean_optional(row.get('jirayit')),
                    bagayat=clean_optional(row.get('bagayat')),
                    potkharaba=clean_optional(row.get('potkharaba')),
                    total_area=clean_optional(row.get('total_area')),
                    aakarni=clean_optional(row.get('aakarni')),
                    khata_area=clean_optional(row.get('khata_area')),
                    aakar=clean_optional(row.get('aakar')),
                    holder_name=clean_optional(clean_holder_name_list(row.get('holder_name'))),
                    kul_khand_other_rights=clean_optional(row.get('kul_khand_other_rights')),
                )

        except ValueError as ex:
            return render(request, "landrecord.html", {"error_message": str(ex)})

        return redirect('land_record_712_list')

    return render(request, "landrecord.html")


@login_required
@require_http_methods(["POST"])
def parse_land_record_712_html(request):

    def fix_encoding(text):
        try:
            return text.encode('latin1').decode('utf-8')
        except:
            return text

    def normalize_text(value):
        return re.sub(r'\s+', ' ', fix_encoding(str(value or ''))).strip().casefold()

    def normalize_gut(value):
        nums = re.findall(r'\d+', str(value or ''))
        return '/'.join(nums) if nums else ''

    def row_get(row, *keys):
        for key in keys:
            value = row.get(key)
            if value:
                return fix_encoding(str(value).strip())
        return ''

    district = request.POST.get('district')
    taluka = request.POST.get('taluka')
    village = request.POST.get('village')
    gut_number = request.POST.get('gut_number')
    uploaded_html = request.FILES.get('document_712')

    if not all([district, taluka, village, gut_number]):
        return JsonResponse({'success': False, 'error': 'जिल्हा, तालुका, गाव आणि गट क्रमांक निवडणे आवश्यक आहे.'}, status=400)

    if not uploaded_html:
        return JsonResponse({'success': False, 'error': 'कृपया HTML फाइल अपलोड करा.'}, status=400)

    api_url = os.getenv(
        'LAND_RECORD_UPLOAD_API_URL',
        'http://209.182.233.103:8005/api/upload-land-record/'
    )

    try:
        uploaded_html.seek(0)
        content = uploaded_html.read().decode('utf-8', errors='ignore').encode('utf-8')

        response = requests.post(
            api_url,
            files={'file': (uploaded_html.name, content, 'text/html')},
            headers=get_land_record_api_headers(),
            timeout=60
        )
        response.raise_for_status()

        payload = json.loads(response.content.decode('utf-8'))

    except requests.RequestException:
        return JsonResponse({'success': False, 'error': 'Service is not working.'}, status=502)
    except ValueError:
        return JsonResponse({'success': False, 'error': 'API कडून वैध JSON मिळाले नाही.'}, status=502)

    # Extract eligible records and कुळ, खंड व इतर अधिकार
    rows = payload.get('eligible', [])
    kul_khand_info = payload.get('कुळ, खंड व इतर अधिकार', '')
    if not rows:
        return JsonResponse({'success': False, 'error': 'HTML मधून डेटा मिळाला नाही.'}, status=400)

    selected_district = normalize_text(district)
    selected_taluka = normalize_text(taluka)
    selected_village = normalize_text(village)
    location_aliases = build_location_aliases(district, taluka, village)
    selected_gut = normalize_gut(gut_number)

    records = []

    for row in rows:
        row_district = row_get(row, 'जिल्हा', 'district')
        row_taluka = row_get(row, 'तालुका', 'taluka')
        row_village = row_get(row, 'गावाचे नाव', 'village', 'village_name')
        row_gut = row_get(
            row,
            'गट नंबर/सर्वे नंबर',
            'सर्वे नंबर', 'सर्व्हे नंबर', 'गट क्रमांक', 'गट नंबर',
            'स_नं_ग_न', 'स_नं_ग_न_हिस्सा',
            'gut_number', 'survey_number', 'survey_no', 'survey number', 'survey'
        )

        if not (
            text_matches_aliases(row_district, location_aliases['district'], normalize_text) and
            text_matches_aliases(row_taluka, location_aliases['taluka'], normalize_text) and
            text_matches_aliases(row_village, location_aliases['village'], normalize_text)
        ):
            continue

        normalized_row_gut = normalize_gut(row_gut)
        if selected_gut and normalized_row_gut and selected_gut not in normalized_row_gut:
            continue

        records.append({
            'gut_number': row_gut,
            'khata_number': row_get(row, 'खाता क्रमांक', 'खाता_नं', 'khata_number'),
            'puid_ulip_no': row_get(row, 'PUID_ULIP_No'),
            'hissa_number': row_get(row, 'हिस्सा क्रमांक', 'स_नं_ग_न_हिस्सा', 'hissa_number'),
            'jirayit': row_get(row, 'जिरायत', 'जिरायात'),
            'bagayat': row_get(row, 'बागायत'),
            'potkharaba': row_get(row, 'पोटखराब'),
            'total_area': row_get(row, 'एकूण क्षेत्र', 'एकूण_क्षेत्र'),
            'aakarni': row_get(row, 'आकारणी', 'आकारणी_रुपये'),
            'khata_area': row_get(row, 'खाते क्षेत्र', 'खाता_क्षेत्र'),
            'aakar': row_get(row, 'आकार'),
            'holder_name': clean_holder_name_list(row_get(row, 'भोगवटादाराचे नांव', 'धारकाचे नाव', 'धारकाचे_नाव')),
            'kul_khand_other_rights': kul_khand_info,  # Add the same कुळ, खंड व इतर अधिकार data to each record
        })

    if not records:
        return JsonResponse({
            'success': False,
            'error': 'HTML मधून गट क्रमांक किंवा स्थान जुळत नाही.'
        }, status=400)

    return JsonResponse({
        'success': True, 
        'records': records, 
        'count': len(records),
        'कुळ, खंड व इतर अधिकार': kul_khand_info
    })

@login_required
def land_record_712_list(request):
    records = LandRecord712.objects.all().order_by('-id')
    
    # Add Marathi names to each record
    for record in records:
        record.district_mr = get_marathi_name('district', record.district)
        record.taluka_mr = get_marathi_name('taluka', record.district, record.taluka)
        record.village_mr = get_marathi_name('village', record.district, record.taluka, record.village)
    
    return render(request, 'land_record_712_list.html', {'records': records})

@login_required
def download_all_land_record_712_csv(request):
    records = LandRecord712.objects.all().order_by('-id')
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="land_record_712.csv"'
    response.write('\ufeff')  # Excel UTF-8 BOM fix
    
    writer = csv.writer(response)
    
    # CSV Header
    header = [
        'ID',
        'जिल्हा (District)',
        'तालुका (Taluka)',
        'गाव (Village)',
        'गट क्रमांक (Gut Number)',
        'खाता नंबर (Khata Number)',
        'PUID/ULIP नंबर',
        'जिरायत (Jirayit)',
        'बागायत (Bagayat)',
        'पोटखराब (Potkharaba)',
        'एकूण क्षेत्र (Total Area)',
        'आकारणी (Aakarni)',
        'खाता क्षेत्र (Khata Area)',
        'आकार (Aakar)',
        'भोगवटादारांचे नांव (Holder Names)',
        'कुळ, खंड व इतर अधिकार (Kul Khand Other Rights)',
        'Created Date',
        'Updated Date',
        'Updated By'
    ]
    writer.writerow(header)
    
    # Write data rows
    for record in records:
        # Get Marathi names
        district_mr = get_marathi_name('district', record.district)
        taluka_mr = get_marathi_name('taluka', record.district, record.taluka)
        village_mr = get_marathi_name('village', record.district, record.taluka, record.village)
        
        row = [
            record.id,
            district_mr,
            taluka_mr,
            village_mr,
            record.gut_number or 'उपलब्ध नाही',
            record.khata_number or 'उपलब्ध नाही',
            record.puid_ulip_no or 'उपलब्ध नाही',
            record.jirayit or 'उपलब्ध नाही',
            record.bagayat or 'उपलब्ध नाही',
            record.potkharaba or 'उपलब्ध नाही',
            record.total_area or 'उपलब्ध नाही',
            record.aakarni or 'उपलब्ध नाही',
            record.khata_area or 'उपलब्ध नाही',
            record.aakar or 'उपलब्ध नाही',
            record.holder_name or 'उपलब्ध नाही',
            record.kul_khand_other_rights or 'उपलब्ध नाही',
            record.created_at.strftime('%d/%m/%Y %H:%M') if record.created_at else '',
            record.updated_at.strftime('%d/%m/%Y %H:%M') if record.updated_at else '',
            record.user.username if record.user else ''
        ]
        writer.writerow(row)
    
    return response

@login_required
def edit_land_record_712(request, id):
    NA_TOKENS = {'', '-', 'na', 'n/a', 'à¤‰à¤ªà¤²à¤¬à¥à¤§ à¤¨à¤¾à¤¹à¥€'}

    def clean_optional(value):
        text = str(value or '').strip()
        if text.casefold() in NA_TOKENS:
            return None
        return text

    def clean_yes_no(value):
        val = str(value or '').strip().casefold()
        if val in {'yes', 'à¤¹à¥‹à¤¯', 'hoy'}:
            return 'Yes'
        if val in {'no', 'à¤¨à¤¾à¤¹à¥€', 'nahi'}:
            return 'No'
        return None

    obj = LandRecord712.objects.get(id=id)
    if request.method == "POST":
        obj.district = clean_optional(request.POST.get('district')) or obj.district
        obj.taluka = clean_optional(request.POST.get('taluka')) or obj.taluka
        obj.village = clean_optional(request.POST.get('village')) or obj.village
        obj.gut_number = clean_optional(request.POST.get('gut_number')) or obj.gut_number
        obj.khata_number = clean_optional(request.POST.get('khata_number'))
        obj.puid_ulip_no = clean_optional(request.POST.get('puid_ulip_no'))
        obj.jirayit = clean_optional(request.POST.get('jirayit'))
        obj.bagayat = clean_optional(request.POST.get('bagayat'))
        obj.potkharaba = clean_optional(request.POST.get('potkharaba'))
        obj.total_area = clean_optional(request.POST.get('total_area'))
        obj.aakarni = clean_optional(request.POST.get('aakarni'))
        obj.khata_area = clean_optional(request.POST.get('khata_area'))
        obj.aakar = clean_optional(request.POST.get('aakar'))
        obj.holder_name = clean_optional(request.POST.get('holder_name'))
        obj.kul_khand_other_rights = clean_optional(request.POST.get('kul_khand_other_rights'))
        obj.save()
        return redirect('land_record_712_list')
    return render(request, 'edit_land_record_712.html', {'obj': obj})

@login_required
def delete_land_record_712(request, id):
    # Clear dependent document links first to satisfy DB foreign key constraints.
    DocumentMaster.objects.filter(land_record_id=id).update(land_record=None)
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
        inspection_date, error_message = get_valid_inspection_date(request.POST.get("date"))
        if error_message:
            posted_inspection = {
                "district": request.POST.get("district"),
                "taluka": request.POST.get("taluka"),
                "village": request.POST.get("village"),
                "gut_number": request.POST.get("survey"),
                "inspection_asset_type": request.POST.get("inspection_asset_type") or None,
                "officer": request.POST.get("officer"),
                "date": inspection_date,
                "latitude": get_inspection_latitude(request),
                "longitude": get_inspection_longitude(request),
                "remark": request.POST.get("remark"),
            }
            return render(
                request,
                "inspection_form.html",
                build_inspection_form_context(
                    inspection=posted_inspection,
                    detail_rows=build_asset_detail_rows_from_request(request),
                    error_message=error_message,
                ),
                status=400,
            )

        inspection = Inspection.objects.create(
            user=request.user,
            district=request.POST.get("district"),
            taluka=request.POST.get("taluka"),
            village=request.POST.get("village"),
            gut_number=request.POST.get("survey"),
            inspection_asset_type=request.POST.get("inspection_asset_type") or None,
            officer=request.POST.get("officer"),
            date=inspection_date,
            latitude=get_inspection_latitude(request),
            longitude=get_inspection_longitude(request),
            remark=request.POST.get("remark"),
        )
        detail_rows = build_asset_detail_rows_from_request(request)
        save_asset_detail_rows(inspection, detail_rows, request)
                
        
        return redirect('inspection_list')

    return render(request, "inspection_form.html", build_inspection_form_context())

@login_required
def dashboard(request):
    if not request.user.is_superuser:
        return redirect('/tools/')
    return render(request, "dashboard.html")






@api_login_required
def get_all_villages_farmers(request):
    """Fetch affected farmers count hierarchically based on filters"""
    district_name = request.GET.get('district', None)
    taluka_name = request.GET.get('taluka', None)
    village_name = request.GET.get('village', None)
    
    with connection.cursor() as cursor:
        farmers_data = []
        
        try:
            if village_name and taluka_name and district_name:
                # Village selected - show gut-wise breakdown
                cursor.execute("""
                    SELECT 
                        gut_no,
                        COUNT(*) as farmers_count
                    FROM pune_ring_road.prj_farmer
                    WHERE UPPER(TRIM(district)) = UPPER(TRIM(%s))
                    AND UPPER(TRIM(taluka)) = UPPER(TRIM(%s))
                    AND UPPER(TRIM(village)) = UPPER(TRIM(%s))
                    GROUP BY gut_no
                    ORDER BY farmers_count DESC;
                """, [district_name, taluka_name, village_name])
                
                results = cursor.fetchall()
                for row in results:
                    farmers_data.append({
                        'name': row[0] or 'Unknown Gut',
                        'farmers_count': row[1],
                        'level': 'gut'
                    })
                    
            elif taluka_name and district_name:
                # Taluka selected - show village-wise breakdown
                cursor.execute("""
                    SELECT 
                        village,
                        COUNT(*) as farmers_count
                    FROM pune_ring_road.prj_farmer
                    WHERE UPPER(TRIM(district)) = UPPER(TRIM(%s))
                    AND UPPER(TRIM(taluka)) = UPPER(TRIM(%s))
                    GROUP BY village
                    ORDER BY farmers_count DESC;
                """, [district_name, taluka_name])
                
                results = cursor.fetchall()
                for row in results:
                    farmers_data.append({
                        'name': row[0] or 'Unknown Village',
                        'farmers_count': row[1],
                        'level': 'village'
                    })
                    
            elif district_name:
                # District selected - show taluka-wise breakdown
                cursor.execute("""
                    SELECT 
                        taluka,
                        COUNT(*) as farmers_count
                    FROM pune_ring_road.prj_farmer
                    WHERE UPPER(TRIM(district)) = UPPER(TRIM(%s))
                    GROUP BY taluka
                    ORDER BY farmers_count DESC;
                """, [district_name])
                
                results = cursor.fetchall()
                for row in results:
                    farmers_data.append({
                        'name': row[0] or 'Unknown Taluka',
                        'farmers_count': row[1],
                        'level': 'taluka'
                    })
                    
            else:
                # No filter - show district-wise breakdown
                cursor.execute("""
                    SELECT 
                        district,
                        COUNT(*) as farmers_count
                    FROM pune_ring_road.prj_farmer
                    GROUP BY district
                    ORDER BY farmers_count DESC;
                """)
                
                results = cursor.fetchall()
                for row in results:
                    farmers_data.append({
                        'name': row[0] or 'Unknown District',
                        'farmers_count': row[1],
                        'level': 'district'
                    })
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'farmers': [], 'error': str(e)})
        
        return JsonResponse({'farmers': farmers_data})


@api_login_required
def get_project_stats(request):
    district_id = request.GET.get('district_id')
    taluka_id = request.GET.get('taluka_id')
    village_id = request.GET.get('village_id')
    district_name = (request.GET.get('district') or '').strip() or None
    taluka_name = (request.GET.get('taluka') or '').strip() or None
    village_name = (request.GET.get('village') or '').strip() or None
    gut_number = request.GET.get('gut')

    with connection.cursor() as cursor:
        column_cache = {}

        def table_has_column(table_name, column_name):
            key = (table_name, column_name)
            if key not in column_cache:
                cursor.execute("""
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = 'pune_ring_road'
                      AND table_name = %s
                      AND column_name = %s
                    LIMIT 1;
                """, [table_name, column_name])
                column_cache[key] = cursor.fetchone() is not None
            return column_cache[key]

        # Resolve public master IDs when the frontend sends names instead of IDs.
        if not district_id and district_name:
            cursor.execute("""
                SELECT id
                FROM public.district_master
                WHERE UPPER(TRIM(COALESCE(district_name, ''))) = UPPER(TRIM(%s))
                   OR UPPER(TRIM(COALESCE(district_name_m, ''))) = UPPER(TRIM(%s))
                LIMIT 1;
            """, [district_name, district_name])
            row = cursor.fetchone()
            district_id = row[0] if row else None

        if not taluka_id and taluka_name and district_name:
            cursor.execute("""
                SELECT id
                FROM public.taluka_master
                WHERE (
                    district_id = %s
                    OR UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))
                    OR UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))
                )
                  AND (
                    UPPER(TRIM(COALESCE(taluka_name, ''))) = UPPER(TRIM(%s))
                    OR UPPER(TRIM(COALESCE(taluka_name_m, ''))) = UPPER(TRIM(%s))
                  )
                LIMIT 1;
            """, [district_id or -1, district_name, district_name, taluka_name, taluka_name])
            row = cursor.fetchone()
            taluka_id = row[0] if row else None

        if not village_id and village_name and district_name and taluka_name:
            cursor.execute("""
                SELECT id
                FROM public.village_master
                WHERE (
                    taluka_id = %s
                    OR (
                        UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))
                        AND UPPER(TRIM(COALESCE(taluka, ''))) = UPPER(TRIM(%s))
                    )
                    OR (
                        UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))
                        AND UPPER(TRIM(COALESCE(taluka, ''))) = UPPER(TRIM(%s))
                    )
                )
                  AND (
                    UPPER(TRIM(COALESCE(village_name, ''))) = UPPER(TRIM(%s))
                    OR UPPER(TRIM(COALESCE(village_name_m, ''))) = UPPER(TRIM(%s))
                  )
                LIMIT 1;
            """, [
                taluka_id or -1,
                district_name, taluka_name,
                district_name, taluka_name,
                village_name, village_name
            ])
            row = cursor.fetchone()
            village_id = row[0] if row else None

            if village_id is None and district_id and taluka_id:
                cursor.execute("""
                    SELECT village_id
                    FROM pune_ring_road.prj_village
                    WHERE district_id = %s
                      AND taluka_id = %s
                      AND UPPER(TRIM(village)) = UPPER(TRIM(%s))
                    LIMIT 1;
                """, [district_id, taluka_id, village_name])
                row = cursor.fetchone()
                village_id = row[0] if row else None

        invalid_location = (
            (district_name and not district_id) or
            (taluka_name and not taluka_id) or
            (village_name and not village_id)
        )

        if invalid_location:
            return JsonResponse({
                "affected_villages": 0,
                "affected_farmers": 0,
                "area_acquired": 0,
                "total_compensation": 0,
                "land_classification": {
                    "trees_total": 0,
                    "trees_valuation": 0,
                    "tree_categories": {},
                    "other_total": 0,
                    "other_valuation": 0,
                    "other_categories": {},
                    "structures_total": 0,
                    "structures_permanent": 0,
                    "structures_temporary": 0,
                    "structures_permanent_valuation": 0,
                    "structures_temporary_valuation": 0,
                    "structures_valuation": 0,
                    "water_total": 0,
                    "water_valuation": 0,
                }
            })

        # Build filters for asset tables (which may not always have district_id/taluka_id).
        def build_asset_filters(table_name):
            table_conditions = []
            table_params = []

            if village_id and table_has_column(table_name, 'village_id'):
                table_conditions.append("village_id = %s")
                table_params.append(village_id)
            else:
                if village_name:
                    if table_has_column(table_name, 'village') and table_has_column(table_name, 'village_m'):
                        table_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(village, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(village_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        table_params.extend([village_name, village_name])
                    elif table_has_column(table_name, 'village'):
                        table_conditions.append("UPPER(TRIM(COALESCE(village, ''))) = UPPER(TRIM(%s))")
                        table_params.append(village_name)
                    elif table_has_column(table_name, 'village_m'):
                        table_conditions.append("UPPER(TRIM(COALESCE(village_m, ''))) = UPPER(TRIM(%s))")
                        table_params.append(village_name)

                if taluka_name:
                    if table_has_column(table_name, 'taluka') and table_has_column(table_name, 'taluka_m'):
                        table_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(taluka, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(taluka_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        table_params.extend([taluka_name, taluka_name])
                    elif table_has_column(table_name, 'taluka'):
                        table_conditions.append("UPPER(TRIM(COALESCE(taluka, ''))) = UPPER(TRIM(%s))")
                        table_params.append(taluka_name)
                    elif table_has_column(table_name, 'taluka_m'):
                        table_conditions.append("UPPER(TRIM(COALESCE(taluka_m, ''))) = UPPER(TRIM(%s))")
                        table_params.append(taluka_name)

                if district_name:
                    if table_has_column(table_name, 'district') and table_has_column(table_name, 'district_m'):
                        table_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(district_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        table_params.extend([district_name, district_name])
                    elif table_has_column(table_name, 'district'):
                        table_conditions.append("UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))")
                        table_params.append(district_name)
                    elif table_has_column(table_name, 'district_m'):
                        table_conditions.append("UPPER(TRIM(COALESCE(district_m, ''))) = UPPER(TRIM(%s))")
                        table_params.append(district_name)

            table_where = ""
            if table_conditions:
                table_where = " AND " + " AND ".join(table_conditions)
            return table_where, table_params

        # -----------------------------
        # COMMON FILTER BUILDER
        # -----------------------------
        conditions = []
        params = []

        if district_id:
            conditions.append("district_id = %s")
            params.append(district_id)

        if taluka_id:
            conditions.append("taluka_id = %s")
            params.append(taluka_id)

        if village_id:
            conditions.append("village_id = %s")
            params.append(village_id)

        where_clause = ""
        if conditions:
            where_clause = " AND " + " AND ".join(conditions)

        # -----------------------------
        # 1. AFFECTED VILLAGES
        # -----------------------------
        try:
            if table_has_column('prj_gut_bd', 'affected'):
                gut_conditions = ["affected = 1"]
                gut_params = []

                if village_id and table_has_column('prj_gut_bd', 'village_id'):
                    gut_conditions.append("village_id = %s")
                    gut_params.append(village_id)
                else:
                    if district_name:
                        gut_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(district_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        gut_params.extend([district_name, district_name])

                    if taluka_name:
                        gut_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(taluka, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(taluka_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        gut_params.extend([taluka_name, taluka_name])

                    if village_name:
                        gut_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(village, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(village_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        gut_params.extend([village_name, village_name])

                if gut_number:
                    if table_has_column('prj_gut_bd', 'gut_no'):
                        gut_conditions.append("UPPER(TRIM(COALESCE(gut_no::text, ''))) = UPPER(TRIM(%s))")
                        gut_params.append(str(gut_number))
                    elif table_has_column('prj_gut_bd', 'gut_no_m'):
                        gut_conditions.append("UPPER(TRIM(COALESCE(gut_no_m::text, ''))) = UPPER(TRIM(%s))")
                        gut_params.append(str(gut_number))

                gut_where = " WHERE " + " AND ".join(gut_conditions)
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT COALESCE(village_id::text, NULLIF(TRIM(village_m), ''), NULLIF(TRIM(village), '')))
                    FROM pune_ring_road.prj_gut_bd
                    {gut_where}
                """, gut_params)
                affected_villages = cursor.fetchone()[0] or 0
            else:
                if village_id:
                    affected_villages = 1
                else:
                    cursor.execute(f"""
                        SELECT COUNT(DISTINCT v.village_id)
                        FROM pune_ring_road.prj_vlg_bd v
                        CROSS JOIN pune_ring_road.prj_bd p
                        WHERE ST_Intersects(v.geom, p.geom)
                        {where_clause}
                    """, params)
                    affected_villages = cursor.fetchone()[0] or 0

        except Exception:
            affected_villages = 0

        # -----------------------------
        # 2. AFFECTED FARMERS
        # -----------------------------
        try:
            query = f"""
                SELECT COUNT(*)
                FROM pune_ring_road.prj_farmer
                WHERE 1=1
                {where_clause}
            """

            farmer_params = list(params)

            if gut_number:
                query += " AND gut_no = %s"
                farmer_params.append(gut_number)

            cursor.execute(query, farmer_params)
            affected_farmers = cursor.fetchone()[0] or 0

        except Exception:
            affected_farmers = 0

        # -----------------------------
        # 3. AREA ACQUIRED
        # -----------------------------
        try:
            if table_has_column('prj_gut_bd', 'affected'):
                gut_conditions = ["affected = 1"]
                gut_params = []

                if village_id and table_has_column('prj_gut_bd', 'village_id'):
                    gut_conditions.append("village_id = %s")
                    gut_params.append(village_id)
                else:
                    if district_name:
                        gut_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(district, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(district_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        gut_params.extend([district_name, district_name])

                    if taluka_name:
                        gut_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(taluka, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(taluka_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        gut_params.extend([taluka_name, taluka_name])

                    if village_name:
                        gut_conditions.append("""
                            (
                                UPPER(TRIM(COALESCE(village, ''))) = UPPER(TRIM(%s))
                                OR UPPER(TRIM(COALESCE(village_m, ''))) = UPPER(TRIM(%s))
                            )
                        """)
                        gut_params.extend([village_name, village_name])

                if gut_number:
                    if table_has_column('prj_gut_bd', 'gut_no'):
                        gut_conditions.append("UPPER(TRIM(COALESCE(gut_no::text, ''))) = UPPER(TRIM(%s))")
                        gut_params.append(str(gut_number))
                    elif table_has_column('prj_gut_bd', 'gut_no_m'):
                        gut_conditions.append("UPPER(TRIM(COALESCE(gut_no_m::text, ''))) = UPPER(TRIM(%s))")
                        gut_params.append(str(gut_number))

                gut_where = " WHERE " + " AND ".join(gut_conditions)
                cursor.execute(f"""
                    SELECT COALESCE(SUM(COALESCE("Shape_Area", area, 0)), 0)
                    FROM pune_ring_road.prj_gut_bd
                    {gut_where}
                """, gut_params)
                total_area_sq_m = float(cursor.fetchone()[0] or 0)
                area_acquired = round(total_area_sq_m / 10000.0, 2)
            else:
                cursor.execute(f"""
                    SELECT COALESCE(SUM(v.area), 0)
                    FROM pune_ring_road.prj_vlg_bd v
                    CROSS JOIN pune_ring_road.prj_bd p
                    WHERE ST_Intersects(v.geom, p.geom)
                    {where_clause}
                """, params)

                area_acquired = round(float(cursor.fetchone()[0] or 0), 2)

        except Exception:
            area_acquired = 0

        # -----------------------------
        # 4. TOTAL COMPENSATION
        # -----------------------------
        total_compensation = 0

        try:
            val_expr = """
                COALESCE(SUM(
                    CASE 
                        WHEN valuation ~ '^[0-9]+[.]?[0-9]*$'
                        THEN CAST(valuation AS NUMERIC)
                        ELSE 0 
                    END
                ), 0)
            """

            for table in ['prj_ass_pt', 'prj_ass_pl', 'prj_ass_poly']:
                if gut_number and not table_has_column(table, 'gut_no'):
                    continue

                table_where, table_params = build_asset_filters(table)
                query = f"""
                    SELECT {val_expr}
                    FROM pune_ring_road.{table}
                    WHERE 1=1
                    {table_where}
                """

                comp_params = list(table_params)

                if gut_number and table_has_column(table, 'gut_no'):
                    query += " AND gut_no = %s"
                    comp_params.append(gut_number)

                cursor.execute(query, comp_params)
                total_compensation += float(cursor.fetchone()[0] or 0)

        except Exception:
            total_compensation = 0

        # -----------------------------
        # 5. LAND CLASSIFICATION
        # -----------------------------
        land_classification = {
            "trees_total": 0,
            "trees_valuation": 0,
            "tree_categories": {},
            "other_total": 0,
            "other_valuation": 0,
            "other_categories": {},
            "structures_total": 0,
            "structures_permanent": 0,
            "structures_temporary": 0,
            "structures_permanent_valuation": 0,
            "structures_temporary_valuation": 0,
            "structures_valuation": 0,
            "water_total": 0,
            "water_valuation": 0,
        }

        try:
            all_categories = {}

            for table in ['prj_ass_pt', 'prj_ass_pl', 'prj_ass_poly']:
                if gut_number and not table_has_column(table, 'gut_no'):
                    continue

                table_where, table_params = build_asset_filters(table)
                query = f"""
                    SELECT 
                        COALESCE(category, 'Other'),
                        COUNT(*),
                        COALESCE(SUM(
                            CASE 
                                WHEN valuation ~ '^[0-9]+\\.?[0-9]*$'
                                THEN CAST(valuation AS NUMERIC)
                                ELSE 0 
                            END
                        ), 0)
                    FROM pune_ring_road.{table}
                    WHERE 1=1
                    {table_where}
                """

                cat_params = list(table_params)

                if gut_number and table_has_column(table, 'gut_no'):
                    query += " AND gut_no = %s"
                    cat_params.append(gut_number)

                query += " GROUP BY category"

                cursor.execute(query, cat_params)
                results = cursor.fetchall()

                for row in results:
                    category = row[0]
                    count = row[1]
                    valuation = float(row[2])

                    if category in all_categories:
                        all_categories[category]['count'] += count
                        all_categories[category]['valuation'] += valuation
                    else:
                        all_categories[category] = {
                            'count': count,
                            'valuation': valuation
                        }

            # Split categories
            tree_categories = {}
            other_categories = {}

            for cat, data in all_categories.items():
                if cat in ['Fruit Tree', 'Forest Tree']:
                    tree_categories[cat] = data
                else:
                    other_categories[cat] = data

            land_classification["trees_total"] = sum(c['count'] for c in tree_categories.values())
            land_classification["trees_valuation"] = sum(c['valuation'] for c in tree_categories.values())
            land_classification["tree_categories"] = tree_categories

            land_classification["other_total"] = sum(c['count'] for c in other_categories.values())
            land_classification["other_valuation"] = sum(c['valuation'] for c in other_categories.values())
            land_classification["other_categories"] = other_categories
            land_classification["structures_total"] = other_categories.get('Structure', {}).get('count', 0)
            land_classification["structures_valuation"] = other_categories.get('Structure', {}).get('valuation', 0)
            land_classification["water_total"] = other_categories.get('Other Asset', {}).get('count', 0)
            land_classification["water_valuation"] = other_categories.get('Other Asset', {}).get('valuation', 0)

        except Exception:
            pass

        # -----------------------------
        # FINAL RESPONSE
        # -----------------------------
        return JsonResponse({
            "affected_villages": affected_villages,
            "affected_farmers": affected_farmers,
            "area_acquired": area_acquired,
            "total_compensation": total_compensation,
            "land_classification": land_classification
        })

@api_login_required
def get_gut_numbers_by_village(request, village_name):
    """Fetch list of gut numbers for a specific village"""
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT DISTINCT gut_no
                FROM pune_ring_road.prj_ass_bund_poly
                WHERE UPPER(TRIM(village)) = UPPER(TRIM(%s))
                AND gut_no IS NOT NULL
                ORDER BY gut_no;
            """, [village_name])
            gut_numbers = [row[0] for row in cursor.fetchall()]
            return JsonResponse({'gut_numbers': gut_numbers})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e), 'gut_numbers': []}, status=500)


@api_login_required
def get_layer_bounds(request, layer_name):
    """
    Returns bounding box for given layer with filters
    """

    district = request.GET.get('district')
    taluka = request.GET.get('taluka')
    village = request.GET.get('village')
    district_id = request.GET.get('district_id')
    taluka_id = request.GET.get('taluka_id')
    village_id = request.GET.get('village_id')
    gut_number = request.GET.get('gut_number')

    # Allowed layers (security)
    allowed_layers = [
        'prj_vlg_bd',
        'prj_gut_bd'
    ]

    if layer_name not in allowed_layers:
        return JsonResponse({"error": "Invalid layer"}, status=400)

    try:
        with connection.cursor() as cursor:
            conditions = []
            params = []

            if layer_name == "prj_vlg_bd":
                # Village boundary bounds: derive geometry from master villages,
                # but restrict to villages present in project table.
                if district:
                    conditions.append("UPPER(TRIM(dm.district_name)) = UPPER(TRIM(%s))")
                    params.append(district)
                if taluka:
                    conditions.append("UPPER(TRIM(tm.taluka_name)) = UPPER(TRIM(%s))")
                    params.append(taluka)
                if village:
                    conditions.append("UPPER(TRIM(vm.village_name)) = UPPER(TRIM(%s))")
                    params.append(village)
                if district_id:
                    conditions.append("pv.district_id = %s")
                    params.append(district_id)
                if taluka_id:
                    conditions.append("pv.taluka_id = %s")
                    params.append(taluka_id)
                if village_id:
                    conditions.append("pv.village_id = %s")
                    params.append(village_id)

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                query = f"""
                    SELECT
                        ST_XMin(extent),
                        ST_YMin(extent),
                        ST_XMax(extent),
                        ST_YMax(extent)
                    FROM (
                        SELECT ST_Extent(ST_Transform(vm.geom, 4326)) AS extent
                        FROM public.village_master vm
                        JOIN pune_ring_road.prj_village pv
                            ON pv.village_id = vm.id
                        JOIN public.taluka_master tm
                            ON tm.id = pv.taluka_id
                        JOIN public.district_master dm
                            ON dm.id = pv.district_id
                        {where_clause}
                    ) AS subquery;
                """
            else:
                # Gut bounds: geometry is in project gut table; use master joins
                # for name-based filters.
                if district:
                    conditions.append("UPPER(TRIM(dm.district_name)) = UPPER(TRIM(%s))")
                    params.append(district)
                if taluka:
                    conditions.append("UPPER(TRIM(tm.taluka_name)) = UPPER(TRIM(%s))")
                    params.append(taluka)
                if village:
                    conditions.append("UPPER(TRIM(vm.village_name)) = UPPER(TRIM(%s))")
                    params.append(village)
                if district_id:
                    conditions.append("pg.district_id = %s")
                    params.append(district_id)
                if taluka_id:
                    conditions.append("pg.taluka_id = %s")
                    params.append(taluka_id)
                if village_id:
                    conditions.append("pg.village_id = %s")
                    params.append(village_id)
                if gut_number:
                    conditions.append("UPPER(TRIM(pg.gut_no::text)) = UPPER(TRIM(%s))")
                    params.append(str(gut_number))

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                query = f"""
                    SELECT
                        ST_XMin(extent),
                        ST_YMin(extent),
                        ST_XMax(extent),
                        ST_YMax(extent)
                    FROM (
                        SELECT ST_Extent(ST_Transform(pg.geom, 4326)) AS extent
                        FROM pune_ring_road.prj_gut_bd pg
                        JOIN public.village_master vm
                            ON vm.id = pg.village_id
                        JOIN public.taluka_master tm
                            ON tm.id = pg.taluka_id
                        JOIN public.district_master dm
                            ON dm.id = pg.district_id
                        {where_clause}
                    ) AS subquery;
                """

            cursor.execute(query, params)
            result = cursor.fetchone()

            if result and all(value is not None for value in result):
                min_lng, min_lat, max_lng, max_lat = result
                return JsonResponse({
                    # Primary shape expected by dashboard JS
                    "bounds": {
                        "minLng": float(min_lng),
                        "minLat": float(min_lat),
                        "maxLng": float(max_lng),
                        "maxLat": float(max_lat),
                    },
                    # Backward-compatible keys
                    "xmin": float(min_lng),
                    "ymin": float(min_lat),
                    "xmax": float(max_lng),
                    "ymax": float(max_lat),
                })
            else:
                return JsonResponse({"message": "No data found"}, status=404)

    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)
    
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            active_session = ActiveUserSession.objects.filter(user=user).first()
            if active_session:
                Session.objects.filter(session_key=active_session.session_key).delete()

            login(request, user)
            ActiveUserSession.objects.update_or_create(
                user=user,
                defaults={"session_key": request.session.session_key},
            )
            return redirect('home')
        else:
            return render(request, 'login.html', {"error": "Invalid credentials"})

    return render(request, 'login.html')


def logout_view(request):
    if request.user.is_authenticated:
        ActiveUserSession.objects.filter(
            user=request.user,
            session_key=request.session.session_key,
        ).delete()
    logout(request)
    return redirect('login')



@api_login_required
def get_locations(request):
    """
    Unified location API that returns data based on provided parameters:
    - No params → districts
    - district only → talukas for that district  
    - district + taluka → villages for that taluka
    - district + taluka + village → guts for that village
    """
    try:
        district = request.GET.get('district', '').strip()
        taluka = request.GET.get('taluka', '').strip()
        village = request.GET.get('village', '').strip()
        district_id = request.GET.get('district_id', '').strip()
        taluka_id = request.GET.get('taluka_id', '').strip()
        village_id = request.GET.get('village_id', '').strip()
        use_marathi = request.GET.get('lang', '').strip().lower() == 'mr'
        
        with connection.cursor() as cursor:
            # Level 4: Return guts for selected village
            if village_id or (district and taluka and village):
                cursor.execute("""
                    SELECT DISTINCT e.gut_no
                    FROM pune_ring_road.prj_district a
                    JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                    JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                    JOIN pune_ring_road.prj_gut_bd e ON d.village_id = e.village_id
                    WHERE (
                            (%s <> '' AND d.village_id::text = %s)
                            OR (
                                %s = '' AND
                                UPPER(TRIM(a.name)) = UPPER(TRIM(%s))
                                AND UPPER(TRIM(c.taluka)) = UPPER(TRIM(%s))
                                AND UPPER(TRIM(d.village)) = UPPER(TRIM(%s))
                            )
                        )
                      AND e.gut_no IS NOT NULL
                    ORDER BY e.gut_no;
                """, [village_id, village_id, village_id, district, taluka, village])
                guts = [row[0] for row in cursor.fetchall()]
                return JsonResponse({'level': 'guts', 'data': guts})
            
            # Level 3: Return villages for selected taluka
            elif taluka_id or (district and taluka):
                if use_marathi:
                    cursor.execute("""
                        SELECT DISTINCT
                            d.village_id AS id,
                            d.village AS value,
                            COALESCE(NULLIF(vm.village_name_m, ''), d.village) AS label
                        FROM pune_ring_road.prj_district a
                        JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                        JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                        JOIN pune_ring_road.prj_gut_bd e ON d.village_id = e.village_id
                        LEFT JOIN public.village_master vm ON d.village_id = vm.id
                        WHERE (
                                (%s <> '' AND c.taluka_id::text = %s)
                                OR (
                                    %s = '' AND
                                    UPPER(TRIM(a.name)) = UPPER(TRIM(%s))
                                    AND UPPER(TRIM(c.taluka)) = UPPER(TRIM(%s))
                                )
                              )
                          AND d.village IS NOT NULL
                        ORDER BY value;
                    """, [taluka_id, taluka_id, taluka_id, district, taluka])
                    villages = [{'id': row[0], 'value': row[1], 'label': row[2]} for row in cursor.fetchall()]
                else:
                    cursor.execute("""
                        SELECT DISTINCT d.village_id, d.village
                        FROM pune_ring_road.prj_district a
                        JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                        JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                        JOIN pune_ring_road.prj_gut_bd e ON d.village_id = e.village_id
                        WHERE (
                                (%s <> '' AND c.taluka_id::text = %s)
                                OR (
                                    %s = '' AND
                                    UPPER(TRIM(a.name)) = UPPER(TRIM(%s))
                                    AND UPPER(TRIM(c.taluka)) = UPPER(TRIM(%s))
                                )
                              )
                          AND d.village IS NOT NULL
                        ORDER BY d.village;
                    """, [taluka_id, taluka_id, taluka_id, district, taluka])
                    villages = [{'id': row[0], 'value': row[1], 'label': row[1]} for row in cursor.fetchall()]
                return JsonResponse({'level': 'villages', 'data': villages})
            
            # Level 2: Return talukas for selected district
            elif district_id or district:
                if use_marathi:
                    cursor.execute("""
                        SELECT DISTINCT
                            c.taluka_id AS id,
                            c.taluka AS value,
                            COALESCE(NULLIF(tm.taluka_name_m, ''), c.taluka) AS label
                        FROM pune_ring_road.prj_district a
                        JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                        JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                        JOIN pune_ring_road.prj_gut_bd e ON d.village_id = e.village_id
                        LEFT JOIN public.taluka_master tm ON c.taluka_id = tm.id
                        WHERE (
                                (%s <> '' AND a.district_id::text = %s)
                                OR (%s = '' AND UPPER(TRIM(a.name)) = UPPER(TRIM(%s)))
                              )
                          AND c.taluka IS NOT NULL
                        ORDER BY value;
                    """, [district_id, district_id, district_id, district])
                    talukas = [{'id': row[0], 'value': row[1], 'label': row[2]} for row in cursor.fetchall()]
                else:
                    cursor.execute("""
                        SELECT DISTINCT c.taluka_id, c.taluka
                        FROM pune_ring_road.prj_district a
                        JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                        JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                        JOIN pune_ring_road.prj_gut_bd e ON d.village_id = e.village_id
                        WHERE (
                                (%s <> '' AND a.district_id::text = %s)
                                OR (%s = '' AND UPPER(TRIM(a.name)) = UPPER(TRIM(%s)))
                              )
                          AND c.taluka IS NOT NULL
                        ORDER BY c.taluka;
                    """, [district_id, district_id, district_id, district])
                    talukas = [{'id': row[0], 'value': row[1], 'label': row[1]} for row in cursor.fetchall()]
                return JsonResponse({'level': 'talukas', 'data': talukas})
            
            # Level 1: Return all districts
            else:
                if use_marathi:
                    cursor.execute("""
                        SELECT DISTINCT
                            a.district_id AS id,
                            a.name AS value,
                            COALESCE(NULLIF(dm.district_name_m, ''), a.name) AS label
                        FROM pune_ring_road.prj_district a
                        JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                        JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                        JOIN pune_ring_road.prj_gut_bd e ON d.village_id = e.village_id
                        LEFT JOIN public.district_master dm ON a.district_id = dm.id
                        WHERE a.name IS NOT NULL
                        ORDER BY value;
                    """)
                    districts = [{'id': row[0], 'value': row[1], 'label': row[2]} for row in cursor.fetchall()]
                else:
                    cursor.execute("""
                        SELECT DISTINCT a.district_id, a.name
                        FROM pune_ring_road.prj_district a
                        JOIN pune_ring_road.prj_taluka c ON a.district_id = c.district_id
                        JOIN pune_ring_road.prj_village d ON c.taluka_id = d.taluka_id
                        JOIN pune_ring_road.prj_gut_bd e ON d.village_id = e.village_id
                        WHERE a.name IS NOT NULL
                        ORDER BY a.name;
                    """)
                    districts = [{'id': row[0], 'value': row[1], 'label': row[1]} for row in cursor.fetchall()]
                return JsonResponse({'level': 'districts', 'data': districts})
                
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

# def get_location_data(request):
#     try:
#         with connection.cursor() as cursor:
#             cursor.execute("""
#                 SELECT DISTINCT
#                     district,
#                     taluka,
#                     village
#                 FROM pune_ring_road.prj_ass_bund_poly
#                 WHERE district IS NOT NULL 
#                 AND taluka IS NOT NULL 
#                 AND village IS NOT NULL
#                 ORDER BY district, taluka, village;
#             """)

#             rows = cursor.fetchall()

#             data = [
#                 {
#                     "district": row[0],
#                     "taluka": row[1],
#                     "village_name": row[2],
#                 }
#                 for row in rows
#             ]

#             return JsonResponse({"villages": data})

#     except Exception as e:
#         return JsonResponse({"error": str(e)}, status=500)


def get_location_data(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT DISTINCT
                    a.name AS district,
                    c.taluka AS taluka,
                    d.village AS village_name
                FROM pune_ring_road.prj_district a
                JOIN pune_ring_road.prj_taluka c 
                    ON a.district_id = c.district_id
                JOIN pune_ring_road.prj_village d 
                    ON c.taluka_id = d.taluka_id
                JOIN pune_ring_road.prj_gut_bd e 
                    ON d.village_id = e.village_id
                WHERE 
                    a.name IS NOT NULL
                    AND c.taluka IS NOT NULL
                    AND d.village IS NOT NULL
                ORDER BY 
                    a.name, c.taluka, d.village;
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

        return JsonResponse({
            "status": "success",
            "count": len(data),
            "villages": data
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=500)




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
        # Delete related AssetDetail records first (they have CASCADE, but let's be explicit)
        inspection.details.all().delete()
        # Delete the inspection
        inspection.delete()
        return redirect('/inspections/')  
    except Inspection.DoesNotExist:
        return HttpResponse("Record not found")
    except Exception as e:
        return HttpResponse(f"Error deleting inspection: {str(e)}")

@login_required
def edit_inspection(request, id):
    try:
        inspection = Inspection.objects.get(id=id)
        inspection_details = AssetDetail.objects.filter(inspection=inspection)

        if request.method == "POST":
            detail_rows = build_asset_detail_rows_from_request(request)

            # Ã¢Å“â€¦ Update main inspection
            inspection.district = request.POST.get("district")
            inspection.taluka = request.POST.get("taluka")
            inspection.village = request.POST.get("village")
            inspection.gut_number = request.POST.get("survey")
            inspection.inspection_asset_type = request.POST.get("inspection_asset_type") or None
            inspection.officer = request.POST.get("officer")
            inspection.date = request.POST.get("date")
            inspection_date, error_message = get_valid_inspection_date(request.POST.get("date"))
            if error_message:
                inspection.district = request.POST.get("district")
                inspection.taluka = request.POST.get("taluka")
                inspection.village = request.POST.get("village")
                inspection.gut_number = request.POST.get("survey")
                inspection.inspection_asset_type = request.POST.get("inspection_asset_type") or None
                inspection.officer = request.POST.get("officer")
                inspection.date = inspection_date
                inspection.latitude = get_inspection_latitude(request)
                inspection.longitude = get_inspection_longitude(request)
                inspection.remark = request.POST.get("remark")
                return render(
                    request,
                    "inspection_form.html",
                    build_inspection_form_context(
                        inspection=inspection,
                        detail_rows=detail_rows,
                        documents=inspection.get_documents(),
                        error_message=error_message,
                    ),
                    status=400,
                )

            inspection.district = request.POST.get("district")
            inspection.taluka = request.POST.get("taluka")
            inspection.village = request.POST.get("village")
            inspection.gut_number = request.POST.get("survey")
            inspection.inspection_asset_type = request.POST.get("inspection_asset_type") or None
            inspection.officer = request.POST.get("officer")
            inspection.date = inspection_date
            inspection.latitude = get_inspection_latitude(request)
            inspection.longitude = get_inspection_longitude(request)
            inspection.remark = request.POST.get("remark")
            inspection.user = request.user
            inspection.save()

            if inspection_request_has_uploads(request, detail_rows):
                clear_inspection_attachments(inspection)

            inspection_details.delete()
            save_asset_detail_rows(inspection, detail_rows, request)

            return redirect('inspection_list')
        
        documents = inspection.get_documents()
        return render(
            request,
            "inspection_form.html",
            build_inspection_form_context(
                inspection=inspection,
                detail_rows=serialize_asset_detail_rows(inspection_details),
                documents=documents,
            ),
        )

    except Inspection.DoesNotExist:
        return HttpResponse("Record not found")

@login_required
def download_all_inspections_csv(request):
    inspections = Inspection.objects.all().order_by('id')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="all_inspections.csv"'
    response.write('\ufeff')  # Excel UTF-8 BOM fix

    writer = csv.writer(response)

    # Collect all unique asset parameter keys across all inspections
    all_param_keys = set()
    inspection_data = []

    for inspection in inspections:
        inspection_details = AssetDetail.objects.filter(inspection=inspection)
        
        if inspection_details.exists():
            for detail in inspection_details:
                # Collect parameter keys
                if detail.asset_parameter:
                    for key in detail.asset_parameter.keys():
                        if key != '_documents':  # Skip internal document field
                            all_param_keys.add(key)
                
                # Store data for later writing
                inspection_data.append({
                    'inspection': inspection,
                    'detail': detail
                })
        else:
            inspection_data.append({
                'inspection': inspection,
                'detail': None
            })

    # Sort parameter keys for consistent column order
    param_keys = sorted(all_param_keys)

    # Build header with dynamic parameter columns
    header = [
        'Inspection ID',
        'District',
        'Taluka',
        'Village',
        'Gut Number',
        'Asset Type',
        'Officer',
        'Date',
        'Latitude',
        'Longitude',
        'Remark',
        'Plot',
        'Asset Name',
        'Valuation'
    ]
    
    # Add parameter columns with labels
    for key in param_keys:
        header.append(f'Param_{key}')
    
    writer.writerow(header)

    # Write data rows
    for data in inspection_data:
        inspection = data['inspection']
        detail = data['detail']
        
        if detail:
            # Base row data
            row = [
                inspection.id,
                inspection.district,
                inspection.taluka,
                inspection.village,
                inspection.gut_number,
                inspection.inspection_asset_type or '',
                inspection.officer,
                inspection.date,
                inspection.latitude or '',
                inspection.longitude or '',
                inspection.remark or '',
                detail.plot,
                detail.name,
                detail.valuation or ''
            ]
            
            # Add parameter values
            for key in param_keys:
                if detail.asset_parameter and key in detail.asset_parameter:
                    param_data = detail.asset_parameter[key]
                    if isinstance(param_data, dict):
                        value = param_data.get('value', '')
                        unit = param_data.get('unit', '')
                        if value and unit:
                            row.append(f"{value} {unit}")
                        else:
                            row.append(value or '')
                    else:
                        row.append(str(param_data) if param_data else '')
                else:
                    row.append('')
        else:
            # Empty row for inspection without details
            row = [
                inspection.id,
                inspection.district,
                inspection.taluka,
                inspection.village,
                inspection.gut_number,
                inspection.inspection_asset_type or '',
                inspection.officer,
                inspection.date,
                inspection.latitude or '',
                inspection.longitude or '',
                inspection.remark or '',
                '',
                '',
                ''
            ]
            
            # Add empty parameter columns
            for _ in param_keys:
                row.append('')
        
        writer.writerow(row)

    return response

@login_required
def get_tree_master_list(request):
    try:
        trees = TreeMaster.objects.all().values("id", "tree_name_marathi")
        return JsonResponse({"trees": list(trees)})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

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
def doc_upload(request):
    if request.method == "POST":
        doc_type = request.POST.get('document_type')
        files = request.FILES.getlist('documents')
        
        # Get or create the Document Management tool
        tool, _ = ToolMaster.objects.get_or_create(
            tool_name='Document Management'
        )

        for file in files:
            file_name = os.path.basename(getattr(file, 'name', '') or 'document')

            doc = Document.objects.create(
                user=request.user,
                document_type=doc_type,
                document_level=request.POST.get('document_level'),
                district=request.POST.get('district'),
                taluka=request.POST.get('taluka') or None,
                village=request.POST.get('village') or None,
                gut_number=request.POST.get('gut_number') or None,
                document_name=file_name,
                description=request.POST.get('description') or None,
                document_date=request.POST.get('document_date') or None,
                court_date=request.POST.get('court_date') or None,
                owner_name=request.POST.get('owner_name') or None,
                matter_type=request.POST.get('matter_type') or None,
            )

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
        doc.description = request.POST.get('description') or None
        doc.document_date = request.POST.get('document_date') or None
        doc.court_date = request.POST.get('court_date') or None
        doc.owner_name = request.POST.get('owner_name') or None
        doc.matter_type = request.POST.get('matter_type') or None
        
        # Handle new file upload
        if request.FILES.get('document'):
            uploaded_file = request.FILES.get('document')
            doc.document_name = os.path.basename(getattr(uploaded_file, 'name', '') or doc.document_name)
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
                file=uploaded_file
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
    doc_type = request.GET.get('type', 'general')
    district = request.GET.get('district') or None
    taluka   = request.GET.get('taluka')   or None
    village  = request.GET.get('village')  or None
    gut      = request.GET.get('gut')      or None
    file_name = request.GET.get('file_name') or None

    base_qs = Document.objects.filter(user=request.user, document_type=doc_type)

    if district and gut and village and taluka:
        numeric = _re.search(r'\d+', gut)
        if numeric:
            num = numeric.group()
            qs = base_qs.filter(
                document_level='gut',
                district__iexact=district,
                taluka__iexact=taluka,
                village__iexact=village,
                gut_number__iregex=r'(^|[^0-9])' + num + r'([^0-9]|$)'
            ).order_by('-uploaded_at')
        else:
            qs = base_qs.filter(
                document_level='gut',
                district__iexact=district, taluka__iexact=taluka,
                village__iexact=village, gut_number__iexact=gut
            ).order_by('-uploaded_at')

    elif village and taluka and district:
        qs = base_qs.filter(
            document_level='village',
            district__iexact=district,
            taluka__iexact=taluka,
            village__iexact=village
        ).order_by('-uploaded_at')

    elif taluka and district:
        qs = base_qs.filter(
            document_level='taluka',
            district__iexact=district,
            taluka__iexact=taluka
        ).order_by('-uploaded_at')

    elif district:
        qs = base_qs.filter(
            document_level='district',
            district__iexact=district
        ).order_by('-uploaded_at')

    else:
        qs = base_qs.order_by('-uploaded_at')

    if file_name:
        qs = qs.filter(document_name__istartswith=file_name)

    matter_labels = dict(Document.MATTER_TYPE_CHOICES)
    data = []
    for d in qs:
        doc_masters = d.get_documents()
        if not doc_masters.exists():
            continue

        first_doc_master = doc_masters.first()
        first_attachment = first_doc_master.attachments.first() if first_doc_master else None
        if not first_attachment or not first_attachment.file:
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
            'file_url': first_attachment.file.url,
            'ext': first_attachment.file.name.rsplit('.', 1)[-1].lower() if '.' in first_attachment.file.name else '',
        })

    return JsonResponse({'documents': data})
@login_required
def asset_list(request):
    assets = Asset.objects.all().order_by('-id')
    for asset in assets:
        asset.documents_list = DocumentMaster.objects.filter(asset=asset).prefetch_related('attachments')
        asset.village_mr = get_marathi_name('village', asset.district, asset.taluka, asset.village)
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
        asset.user = request.user
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
    village_mr = get_marathi_name('village', asset.district, asset.taluka, asset.village)
    return render(request, 'edit_asset.html', {'asset': asset, 'documents': documents, 'village_mr': village_mr})

@login_required
def download_all_assets_csv(request):
    assets = Asset.objects.all().order_by('-id')
    
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="asset_records.csv"'
    response.write('\ufeff')  # Excel UTF-8 BOM fix
    
    writer = csv.writer(response)
    
    # CSV Header
    header = [
        'ID',
        'मालमत्ता नाव (Asset Name)',
        'जिल्हा (District)',
        'तालुका (Taluka)',
        'गाव (Village)',
        'गट क्रमांक (Gut Number)',
        'मालमत्ता प्रकार (Asset Type)',
        'सर्वेक्षण दिनांक (Survey Date)',
        'दर (Rate)',
        'सरकारी अंदाजित दर (Government Rate)',
        'एकूण मोजमाप (Total Measurement)',
        'अंतिम गणना (Final Calculation)',
        'अंतिम रक्कम (Final Amount)',
        'सरकारी अंतिम रक्कम (Government Final Amount)',
        'टिप्पणी (Remarks)',
        'Created Date',
        'Updated Date',
        'Updated By'
    ]
    writer.writerow(header)
    
    # Write data rows
    for asset in assets:
        # Get Marathi names
        district_mr = get_marathi_name('district', asset.district)
        taluka_mr = get_marathi_name('taluka', asset.district, asset.taluka)
        village_mr = get_marathi_name('village', asset.district, asset.taluka, asset.village)
        
        row = [
            asset.id,
            asset.asset_name or '',
            district_mr,
            taluka_mr,
            village_mr,
            asset.gut_number or '',
            asset.asset_type or '',
            asset.survey_date.strftime('%d/%m/%Y') if asset.survey_date else '',
            asset.rate or '',
            asset.government_estimated_rate or '',
            asset.total_measurement or '',
            asset.final_calculation or '',
            asset.final_amount or '',
            asset.government_final_amount or '',
            asset.remarks or '',
            asset.created_at.strftime('%d/%m/%Y %H:%M') if asset.created_at else '',
            asset.updated_at.strftime('%d/%m/%Y %H:%M') if asset.updated_at else '',
            asset.user.username if asset.user else ''
        ]
        writer.writerow(row)
    
    return response





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
            edit_entry_id = request.GET.get('edit_id')
            documents = []
            if edit_entry_id:
                edit_entry = get_object_or_404(Entry, id=edit_entry_id)
                documents = DocumentMaster.objects.filter(entry=edit_entry).prefetch_related('attachments')
            return render(request, 'add_entries.html', {
                'documents': documents,
                'active_tab': 'rate-calculator',
            })

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

        entry.is_with_consent = str(data.get('is_with_consent', '')).lower() in ('1', 'true', 'on', 'yes')

        if entry.committee_market_rate_12 is not None:
            multiplier = Decimal('1')
            if entry.land_type_13 and 'à¤¬à¤¾à¤—à¤¾à¤¯à¤¤' in entry.land_type_13 and 'à¤¹à¤‚à¤—à¤¾à¤®à¥€' in entry.land_type_13:
                multiplier = Decimal('1.10')
            elif entry.land_type_13 and 'à¤¬à¤¾à¤—à¤¾à¤¯à¤¤' in entry.land_type_13:
                multiplier = Decimal('1.20')
            entry.considered_market_rate_14 = entry.committee_market_rate_12 * multiplier
        else:
            entry.considered_market_rate_14 = None

        if entry.considered_market_rate_14 is not None and entry.to_create_09 is not None:
            market15a = entry.considered_market_rate_14 * entry.to_create_09  # full decimal
            entry.market_value_15a = _round0(market15a)
        else:
            market15a = None
            entry.market_value_15a = None

        if market15a is not None and entry.coefficient_15c is not None:
            total15d = market15a * entry.coefficient_15c  # full decimal
            entry.total_market_value_15d = _round0(total15d)
        else:
            total15d = None
            entry.total_market_value_15d = None

        assets_total = (
            (entry.fruit_trees_16a or Decimal('0')) +
            (entry.forest_trees_16b or Decimal('0')) +
            (entry.construction_16c or Decimal('0')) +
            (entry.other_assets_16d or Decimal('0'))
        )  # full decimal
        entry.total_assets_16e = _round0(assets_total)

        if total15d is not None:
            comp17 = total15d + assets_total  # full decimal, no round yet
            entry.determined_compensation_17 = _round0(comp17)
            entry.solatium_amount_18 = _round0(comp17)
        else:
            comp17 = None
            entry.determined_compensation_17 = None
            entry.solatium_amount_18 = None

        entry.notification_date = data.get('notification_date') or None
        entry.award_date = data.get('award_date') or None
        entry.days_difference = int(data.get('days_difference') or 0)

        if comp17 is not None:
            # col 19: Excel ROUND((total15d*0.12)/365*days, 0)
            entry.additional_12_percent_19 = _round0(
                total15d * Decimal('0.12') / Decimal('365') * Decimal(str(entry.days_difference or 0))
            )
            # col 20 = 17 + 18 + 19
            entry.non_consent_compensation_20 = _round0(
                entry.determined_compensation_17 + entry.solatium_amount_18 + entry.additional_12_percent_19
            )
            # col 23 = ROUND(20 * 0.25)
            entry.consent_bonus_23 = _round0(entry.non_consent_compensation_20 * Decimal('0.25'))
        else:
            entry.consent_bonus_23 = None
            entry.additional_12_percent_19 = None
            entry.non_consent_compensation_20 = None

        if entry.non_consent_compensation_20 is not None:
            entry.class2_deduction_21 = _round0(entry.non_consent_compensation_20 * Decimal('0.10')) if entry.land_class_04 == "2" else Decimal('0')
            base_non_consent = entry.non_consent_compensation_20 - entry.class2_deduction_21
            entry.payable_non_consent_22 = _round0(base_non_consent)

            # col 24 = 20 + 23
            entry.consent_total_24 = _round0(entry.non_consent_compensation_20 + entry.consent_bonus_23)
            entry.class2_deduction_consent_25 = _round0(entry.consent_total_24 * Decimal('0.10')) if entry.land_class_04 == "2" else Decimal('0')

            base_consent = entry.consent_total_24 - entry.class2_deduction_consent_25
            entry.payable_consent_26 = _round0(base_consent)
        else:
            entry.class2_deduction_21 = None
            entry.payable_non_consent_22 = None
            entry.consent_total_24 = None
            entry.class2_deduction_consent_25 = None
            entry.payable_consent_26 = None

        entry.save()

        files = request.FILES.getlist('documents')
        if files:
            handle_document_upload(
                user=request.user,
                tool_name='Rate Calculator',
                entry=entry,
                files=files,
                district=entry.district,
                taluka=entry.taluka,
                village=entry.village,
                gut_number=entry.sr_no_02
            )

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
        }
        message = '???? ???????????? ????? ????!' if entry_id else '???? ???????????? ??? ????!'

        if is_json_request:
            return JsonResponse({
                'success': True,
                'entry_id': entry.id,
                'message': message,
                'calculations': calculations,
            })

        return redirect(f"{reverse('entry_list')}?saved=1")
    except Exception as e:
        if is_json_request:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
        return render(request, 'add_entries.html', {'error': str(e), 'active_tab': 'rate-calculator'})


# All _files field keys that accept file uploads in VillageData
_VILLAGE_FILE_KEYS = [
    'sec1_files', 'sec2_files', 'sec2_paper1_files', 'sec2_paper2_files',
    'sec3_files', 'sec5_files',
    'sec6_parishisht16_files', 'sec6_nakasha_files', 'sec7_files',
    'sec9_paper1_files', 'sec9_paper2_files', 'sec10_files', 'sec11_files',
    'sec12_files', 'sec13_files', 'sec14_files', 'sec16_files', 'sec17_files',
    'sec18_files', 'sec19_files', 'sec20_files', 'sec21_prastaav_files',
    'sec21_karyavrutant_files', 'sec23_files', 'sec24_files', 'sec25_files',
]

_VILLAGE_SCALAR_FIELDS = [
    'sec1_adesh_kramank', 'sec1_date',
    'sec2_adhisuchana_kramank', 'sec2_date',
    'sec2_paper1_name', 'sec2_paper1_date',
    'sec2_paper2_name', 'sec2_paper2_date',
    'sec3_adhisuchana_kramank', 'sec3_date',
    'sec5_prastaav_kramank', 'sec5_date',
    'sec6_register_number', 'sec6_date',
    'sec7_aakshep_details',
    'sec9_paper1_name', 'sec9_paper1_date',
    'sec9_paper2_name', 'sec9_paper2_date',
    'sec10_prastaav_kramank', 'sec10_date',
    'sec11_date',
    'sec12_zone_details', 'sec12_date',
    'sec13_kharedi_vikri_details',
    'sec14_meeting_details', 'sec14_date',
    'sec16_letter_details', 'sec16_date',
    'sec17_letter_details', 'sec17_date',
    'sec18_letter_details', 'sec18_date',
    'sec19_letter_details', 'sec19_date',
    'sec20_letter_details', 'sec20_date',
    'sec21_prastaav', 'sec21_prastaav_date',
    'sec21_karyavrutant', 'sec21_karyavrutant_date',
    'sec23_kramank', 'sec23_date',
    'sec24_court_details',
    'sec25_kramank', 'sec25_date',
]


@login_required
def village_info_list(request):
    if request.method == "POST":
        return village_info(request)
    return render(request, 'village_info.html', {'active_tab': 'village-info', 'show_form': False})


@login_required
def village_info_form(request):
    if request.method == "POST":
        return village_info(request)
    return render(request, 'village_info.html', {'active_tab': 'village-info', 'show_form': True})


@login_required
def process_chart_form(request):
    return render(request, 'process_chart_form.html', {'active_tab': 'process-chart'})


@login_required
def village_info(request):
    if request.method == "POST":
        district = (request.POST.get('district') or '').strip()
        taluka = (request.POST.get('taluka') or '').strip()
        village = (request.POST.get('village') or '').strip()
        final_submit = str(request.POST.get('final_submit', '')).strip().lower() in ('1', 'true', 'yes', 'on')

        if not district or not taluka or not village:
            return JsonResponse({'success': False, 'error': 'District, Taluka and Village are required.'}, status=400)

        village_data = VillageData.objects.filter(
            district__iexact=district,
            taluka__iexact=taluka,
            village__iexact=village
        ).order_by('-updated_at', '-id').first()
        if not village_data:
            village_data = VillageData.objects.create(
                user=request.user,
                district=district,
                taluka=taluka,
                village=village
            )
        else:
            village_data.district = district
            village_data.taluka = taluka
            village_data.village = village
            village_data.user = request.user

        def _norm_name(name):
            from django.utils.text import get_valid_filename
            base = os.path.basename((name or '').strip())
            return get_valid_filename(base).lower()

        # Validate duplicate-name uploads before saving file rows.
        duplicate_conflicts = []

        for field_key in _VILLAGE_FILE_KEYS:
            uploaded_files = request.FILES.getlist(field_key)
            if not uploaded_files:
                continue
            existing_names = {
                _norm_name(vf.file.name)
                for vf in VillageDataFile.objects.filter(village_data=village_data, field_key=field_key)
                if getattr(vf, 'file', None) and vf.file.name
            }
            for f in uploaded_files:
                incoming_name = _norm_name(getattr(f, 'name', ''))
                if incoming_name and incoming_name in existing_names:
                    duplicate_conflicts.append(f"{field_key}: {os.path.basename(f.name)}")
                elif incoming_name:
                    existing_names.add(incoming_name)

        # Validate duplicate-name uploads before saving file rows.
        duplicate_conflicts = []

        for field_key in _VILLAGE_FILE_KEYS:
            uploaded_files = request.FILES.getlist(field_key)
            if not uploaded_files:
                continue
            existing_names = {
                _norm_name(vf.file.name)
                for vf in VillageDataFile.objects.filter(village_data=village_data, field_key=field_key)
                if getattr(vf, 'file', None) and vf.file.name
            }
            for f in uploaded_files:
                incoming_name = _norm_name(getattr(f, 'name', ''))
                if incoming_name and incoming_name in existing_names:
                    duplicate_conflicts.append(f"{field_key}: {os.path.basename(f.name)}")
                elif incoming_name:
                    existing_names.add(incoming_name)

        try:
            sec26_count = int(request.POST.get('sec26_count') or 0)
        except (TypeError, ValueError):
            sec26_count = 0
        existing_8a = list(village_data.sec26_8a_records.prefetch_related('files_8a').all())
        try:
            sec4_row_count = int(request.POST.get('sec4_row_count') or 0)
        except (TypeError, ValueError):
            sec4_row_count = 0
        existing_sec4_rows = list(village_data.sec4_rows.prefetch_related('files_15_2').order_by('id'))
        try:
            sec8_row_count = int(request.POST.get('sec8_row_count') or 0)
        except (TypeError, ValueError):
            sec8_row_count = 0
        existing_sec8_rows = list(village_data.sec8_rows.prefetch_related('files_18_1').order_by('id'))

        for i in range(sec26_count):
            if i >= len(existing_8a):
                continue
            row = existing_8a[i]
            uploaded_8a_files = request.FILES.getlist(f'sec26_files_{i}')
            if not uploaded_8a_files:
                continue
            existing_names = {
                _norm_name(f8.file.name)
                for f8 in row.files_8a.all()
                if getattr(f8, 'file', None) and f8.file.name
            }
            for f in uploaded_8a_files:
                incoming_name = _norm_name(getattr(f, 'name', ''))
                if incoming_name and incoming_name in existing_names:
                    duplicate_conflicts.append(f"sec26_row_{i + 1}: {os.path.basename(f.name)}")
                elif incoming_name:
                    existing_names.add(incoming_name)

        for i in range(sec4_row_count):
            if i >= len(existing_sec4_rows):
                continue
            row = existing_sec4_rows[i]
            for sec4_field_key, upload_key in (
                ('main', f'sec4_row_files_{i}'),
                ('paper1', f'sec4_row_paper1_files_{i}'),
                ('paper2', f'sec4_row_paper2_files_{i}'),
            ):
                uploaded_sec4_files = request.FILES.getlist(upload_key)
                if not uploaded_sec4_files:
                    continue
                existing_names = {
                    _norm_name(f15.file.name)
                    for f15 in row.files_15_2.filter(field_key=sec4_field_key)
                    if getattr(f15, 'file', None) and f15.file.name
                }
                for f in uploaded_sec4_files:
                    incoming_name = _norm_name(getattr(f, 'name', ''))
                    if incoming_name and incoming_name in existing_names:
                        duplicate_conflicts.append(f"sec4_row_{i + 1}_{sec4_field_key}: {os.path.basename(f.name)}")
                    elif incoming_name:
                        existing_names.add(incoming_name)

        for i in range(sec8_row_count):
            if i >= len(existing_sec8_rows):
                continue
            row = existing_sec8_rows[i]
            uploaded_sec8_files = request.FILES.getlist(f'sec8_row_files_{i}')
            if not uploaded_sec8_files:
                continue
            existing_names = {
                _norm_name(f18.file.name)
                for f18 in row.files_18_1.all()
                if getattr(f18, 'file', None) and f18.file.name
            }
            for f in uploaded_sec8_files:
                incoming_name = _norm_name(getattr(f, 'name', ''))
                if incoming_name and incoming_name in existing_names:
                    duplicate_conflicts.append(f"sec8_row_{i + 1}: {os.path.basename(f.name)}")
                elif incoming_name:
                    existing_names.add(incoming_name)

        if duplicate_conflicts:
            return JsonResponse({
                'success': False,
                'error': (
                    "File with this name already exists. "
                    "Please delete the existing same-name file first, then upload again. "
                    f"Conflicts: {', '.join(duplicate_conflicts)}"
                )
            }, status=400)

        for i in range(sec26_count):
            if i >= len(existing_8a):
                continue
            row = existing_8a[i]
            uploaded_8a_files = request.FILES.getlist(f'sec26_files_{i}')
            if not uploaded_8a_files:
                continue
            existing_names = {
                _norm_name(f8.file.name)
                for f8 in row.files_8a.all()
                if getattr(f8, 'file', None) and f8.file.name
            }
            for f in uploaded_8a_files:
                incoming_name = _norm_name(getattr(f, 'name', ''))
                if incoming_name and incoming_name in existing_names:
                    duplicate_conflicts.append(f"sec26_row_{i + 1}: {os.path.basename(f.name)}")
                elif incoming_name:
                    existing_names.add(incoming_name)

        for i in range(sec4_row_count):
            if i >= len(existing_sec4_rows):
                continue
            row = existing_sec4_rows[i]
            for sec4_field_key, upload_key in (
                ('main', f'sec4_row_files_{i}'),
                ('paper1', f'sec4_row_paper1_files_{i}'),
                ('paper2', f'sec4_row_paper2_files_{i}'),
            ):
                uploaded_sec4_files = request.FILES.getlist(upload_key)
                if not uploaded_sec4_files:
                    continue
                existing_names = {
                    _norm_name(f15.file.name)
                    for f15 in row.files_15_2.filter(field_key=sec4_field_key)
                    if getattr(f15, 'file', None) and f15.file.name
                }
                for f in uploaded_sec4_files:
                    incoming_name = _norm_name(getattr(f, 'name', ''))
                    if incoming_name and incoming_name in existing_names:
                        duplicate_conflicts.append(f"sec4_row_{i + 1}_{sec4_field_key}: {os.path.basename(f.name)}")
                    elif incoming_name:
                        existing_names.add(incoming_name)

        for i in range(sec8_row_count):
            if i >= len(existing_sec8_rows):
                continue
            row = existing_sec8_rows[i]
            uploaded_sec8_files = request.FILES.getlist(f'sec8_row_files_{i}')
            if not uploaded_sec8_files:
                continue
            existing_names = {
                _norm_name(f18.file.name)
                for f18 in row.files_18_1.all()
                if getattr(f18, 'file', None) and f18.file.name
            }
            for f in uploaded_sec8_files:
                incoming_name = _norm_name(getattr(f, 'name', ''))
                if incoming_name and incoming_name in existing_names:
                    duplicate_conflicts.append(f"sec8_row_{i + 1}: {os.path.basename(f.name)}")
                elif incoming_name:
                    existing_names.add(incoming_name)

        if duplicate_conflicts:
            return JsonResponse({
                'success': False,
                'error': (
                    "File with this name already exists. "
                    "Please delete the existing same-name file first, then upload again. "
                    f"Conflicts: {', '.join(duplicate_conflicts)}"
                )
            }, status=400)

        for field in _VILLAGE_SCALAR_FIELDS:
            raw_val = request.POST.get(field)
            if field.endswith('_date'):
                setattr(village_data, field, parse_date(raw_val) if raw_val else None)
            else:
                setattr(village_data, field, (raw_val.strip() if raw_val else ''))
        if final_submit:
            village_data.is_final_submitted = True
        village_data.save()

        # Save uploaded files per field_key (append mode; duplicates already blocked above).
        for field_key in _VILLAGE_FILE_KEYS:
            for f in request.FILES.getlist(field_key):
                VillageDataFile.objects.create(village_data=village_data, field_key=field_key, file=f)

        # sec4 15(2) rows - rebuild rows; keep existing files and append new unique-name uploads
        for old_row in existing_sec4_rows[sec4_row_count:]:
            old_row.delete()

        for i in range(sec4_row_count):
            adhisuchana_kramank = (request.POST.get(f'sec4_row_adhisuchana_{i}') or '').strip()
            adhisuchana_date_raw = request.POST.get(f'sec4_row_date_{i}')
            paper1_name = (request.POST.get(f'sec4_row_paper1_name_{i}') or '').strip()
            paper1_date_raw = request.POST.get(f'sec4_row_paper1_date_{i}')
            paper2_name = (request.POST.get(f'sec4_row_paper2_name_{i}') or '').strip()
            paper2_date_raw = request.POST.get(f'sec4_row_paper2_date_{i}')

            if i < len(existing_sec4_rows):
                row = existing_sec4_rows[i]
                row.adhisuchana_kramank = adhisuchana_kramank
                row.adhisuchana_date = parse_date(adhisuchana_date_raw) if adhisuchana_date_raw else None
                row.paper1_name = paper1_name
                row.paper1_date = parse_date(paper1_date_raw) if paper1_date_raw else None
                row.paper2_name = paper2_name
                row.paper2_date = parse_date(paper2_date_raw) if paper2_date_raw else None
                row.save()
            else:
                row = VillageData15_2Row.objects.create(
                    village_data=village_data,
                    adhisuchana_kramank=adhisuchana_kramank,
                    adhisuchana_date=parse_date(adhisuchana_date_raw) if adhisuchana_date_raw else None,
                    paper1_name=paper1_name,
                    paper1_date=parse_date(paper1_date_raw) if paper1_date_raw else None,
                    paper2_name=paper2_name,
                    paper2_date=parse_date(paper2_date_raw) if paper2_date_raw else None,
                )

            for f in request.FILES.getlist(f'sec4_row_files_{i}'):
                VillageData15_2RowFile.objects.create(row_15_2=row, field_key='main', file=f)
            for f in request.FILES.getlist(f'sec4_row_paper1_files_{i}'):
                VillageData15_2RowFile.objects.create(row_15_2=row, field_key='paper1', file=f)
            for f in request.FILES.getlist(f'sec4_row_paper2_files_{i}'):
                VillageData15_2RowFile.objects.create(row_15_2=row, field_key='paper2', file=f)

        # sec8 18/1 rows - rebuild rows; keep existing files and append new unique-name uploads
        for old_row in existing_sec8_rows[sec8_row_count:]:
            old_row.delete()

        for i in range(sec8_row_count):
            adhisuchana_kramank = (request.POST.get(f'sec8_row_adhisuchana_{i}') or '').strip()
            adhisuchana_date_raw = request.POST.get(f'sec8_row_date_{i}')

            if i < len(existing_sec8_rows):
                row = existing_sec8_rows[i]
                row.adhisuchana_kramank = adhisuchana_kramank
                row.adhisuchana_date = parse_date(adhisuchana_date_raw) if adhisuchana_date_raw else None
                row.save()
            else:
                row = VillageData18_1Row.objects.create(
                    village_data=village_data,
                    adhisuchana_kramank=adhisuchana_kramank,
                    adhisuchana_date=parse_date(adhisuchana_date_raw) if adhisuchana_date_raw else None,
                )

            for f in request.FILES.getlist(f'sec8_row_files_{i}'):
                VillageData18_1RowFile.objects.create(row_18_1=row, file=f)

        # sec26 8A records - rebuild rows; keep existing files and append new unique-name uploads
        # Delete rows that were removed (count shrank)
        for old_row in existing_8a[sec26_count:]:
            old_row.delete()

        for i in range(sec26_count):
            khate_kramank = (request.POST.get(f'sec26_khate_{i}') or '').strip()
            navavar_kshetra = (request.POST.get(f'sec26_navavar_{i}') or '').strip()
            ferfar_kramank = (request.POST.get(f'sec26_ferfar_{i}') or '').strip()
            ferfar_date_raw = request.POST.get(f'sec26_date_{i}')

            if i < len(existing_8a):
                row = existing_8a[i]
                row.khate_kramank = khate_kramank
                row.navavar_kshetra = navavar_kshetra
                row.ferfar_kramank = ferfar_kramank
                row.ferfar_date = parse_date(ferfar_date_raw) if ferfar_date_raw else None
                row.save()
            else:
                row = VillageData8ARecord.objects.create(
                    village_data=village_data,
                    khate_kramank=khate_kramank,
                    navavar_kshetra=navavar_kshetra,
                    ferfar_kramank=ferfar_kramank,
                    ferfar_date=parse_date(ferfar_date_raw) if ferfar_date_raw else None,
                )

            for f in request.FILES.getlist(f'sec26_files_{i}'):
                VillageData8AFile.objects.create(record_8a=row, file=f)

        # sec15 rates
        VillageDataSec15Rate.objects.filter(village_data=village_data).delete()
        try:
            sec15_count = int(request.POST.get('sec15_count') or 0)
        except (TypeError, ValueError):
            sec15_count = 0
        for i in range(sec15_count):
            rr_rate_id = request.POST.get(f'sec15_rr_rate_id_{i}')
            if not rr_rate_id:
                continue
            approved_raw = request.POST.get(f'sec15_approved_{i}')
            approved_rate = None
            if approved_raw not in (None, ''):
                try:
                    approved_rate = Decimal(str(approved_raw))
                except Exception:
                    pass
            rr_rate = ReadyReckonerRate.objects.filter(id=rr_rate_id).first()
            if rr_rate:
                VillageDataSec15Rate.objects.create(
                    village_data=village_data, rr_rate=rr_rate, approved_rate=approved_rate
                )

        return JsonResponse({'success': True, 'id': village_data.id, 'message': 'Village info saved successfully.'})

    return render(request, 'village_info.html', {'active_tab': 'village-info'})

@login_required
@require_http_methods(["POST"])
def delete_village_file(request, file_id):
    vf = get_object_or_404(VillageDataFile, id=file_id)
    vf.file.delete(save=False)
    vf.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def delete_village_8a_file(request, file_id):
    vf = get_object_or_404(VillageData8AFile, id=file_id)
    vf.file.delete(save=False)
    vf.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def delete_village_sec4_row_file(request, file_id):
    vf = get_object_or_404(VillageData15_2RowFile, id=file_id)
    vf.file.delete(save=False)
    vf.delete()
    return JsonResponse({'success': True})


@login_required
@require_http_methods(["POST"])
def delete_village_sec8_row_file(request, file_id):
    vf = get_object_or_404(VillageData18_1RowFile, id=file_id)
    vf.file.delete(save=False)
    vf.delete()
    return JsonResponse({'success': True})


@login_required
def get_village_info_list(request):
    try:
        rows = VillageData.objects.all().order_by('-updated_at').values(
            'id', 'district', 'taluka', 'village', 'is_final_submitted', 'created_at', 'updated_at', 'user__username'
        )
        payload = []
        for row in rows:
            created_at = row.get('created_at')
            updated_at = row.get('updated_at')
            district_en = row.get('district') or ''
            taluka_en = row.get('taluka') or ''
            village_en = row.get('village') or ''
            district_mr = get_marathi_name('district', district_en) if district_en else ''
            taluka_mr = get_marathi_name('taluka', district_en, taluka_en) if district_en and taluka_en else ''
            village_mr = get_marathi_name('village', district_en, taluka_en, village_en) if district_en and taluka_en and village_en else ''
            payload.append({
                'id': row['id'],
                'district': district_mr or district_en,
                'taluka': taluka_mr or taluka_en,
                'village': village_mr or village_en,
                'district_en': district_en,
                'taluka_en': taluka_en,
                'village_en': village_en,
                'is_final_submitted': bool(row.get('is_final_submitted')),
                'updated_by': row.get('user__username') or '',
                'created_at': created_at.isoformat() if hasattr(created_at, 'isoformat') else '',
                'updated_at': updated_at.isoformat() if hasattr(updated_at, 'isoformat') else '',
            })
        return JsonResponse({'success': True, 'rows': payload})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def delete_village_info_record(request, record_id):
    record = get_object_or_404(VillageData, id=record_id)
    record.delete()
    return JsonResponse({'success': True})


@login_required
def check_village_info_exists(request):
    try:
        district = (request.GET.get('district') or '').strip()
        taluka = (request.GET.get('taluka') or '').strip()
        village = (request.GET.get('village') or '').strip()

        if not district or not taluka or not village:
            return JsonResponse({'exists': False, 'error': 'district, taluka and village are required'}, status=400)

        exists = VillageData.objects.filter(
            district__iexact=district,
            taluka__iexact=taluka,
            village__iexact=village
        ).exists()
        
        return JsonResponse({
            'exists': exists,
            'message': 'या गावासाठी गावाची माहिती नोंद आधीच अस्तित्वात आहे.' if exists else ''
        })
    except Exception as e:
        return JsonResponse({'exists': False, 'error': str(e)}, status=500)


@login_required
def entry_list(request):
    entries = Entry.objects.all().prefetch_related('documents__attachments').order_by('-id')
    for entry in entries:
        entry.files_count = sum(doc.attachments.count() for doc in entry.documents.all())
    return render(request, 'entry_list.html', {'entries': entries})


@login_required
def delete_entry(request, id):
    entry = get_object_or_404(Entry, id=id)
    entry.delete()
    return redirect('entry_list')


@api_login_required
def get_rr_rate_by_village(request, village):
    """Return all assessment types with full rate ranges for a village (latest year)."""
    base_qs = ReadyReckonerInfo.objects.filter(village__iexact=village)
    latest_year = base_qs.order_by('-year').values_list('year', flat=True).first()
    if not latest_year:
        return JsonResponse({'found': False, 'assessment_types': []})
    qs = base_qs.filter(year=latest_year).prefetch_related('rates').order_by('assessment_type')
    types = []
    for info in qs:
        rates = [{'min': float(r.assessment_range_min), 'max': float(r.assessment_range_max), 'rate': float(r.rate)}
                 for r in info.rates.order_by('assessment_range_min')]
        if rates:
            types.append({'assessment_type': info.assessment_type, 'unit': info.unit, 'year': info.year, 'rates': rates})
    return JsonResponse({'found': bool(types), 'assessment_types': types})


@login_required
def get_village_info_data(request):
    district = (request.GET.get('district') or '').strip()
    taluka = (request.GET.get('taluka') or '').strip()
    village = (request.GET.get('village') or '').strip()

    if not district or not taluka or not village:
        return JsonResponse({'found': False, 'error': 'district, taluka and village are required'}, status=400)

    village_data = VillageData.objects.filter(
        district__iexact=district,
        taluka__iexact=taluka,
        village__iexact=village
    ).order_by('-updated_at').first()

    if not village_data:
        return JsonResponse({'found': False, 'data': None})

    data = {}
    for f in _VILLAGE_SCALAR_FIELDS:
        val = getattr(village_data, f)
        data[f] = val.isoformat() if hasattr(val, 'isoformat') and val else (val or '')

    # files per field_key
    files_map = {}
    for vf in village_data.village_files.all():
        files_map.setdefault(vf.field_key, []).append({'id': vf.id, 'url': vf.file.url, 'name': vf.file.name.split('/')[-1]})

    sec26 = []
    for row in village_data.sec26_8a_records.prefetch_related('files_8a').all():
        sec26.append({
            'id': row.id,
            'khate_kramank': row.khate_kramank,
            'navavar_kshetra': row.navavar_kshetra,
            'ferfar_kramank': row.ferfar_kramank,
            'ferfar_date': row.ferfar_date.isoformat() if row.ferfar_date else '',
            'files': [{'id': f.id, 'url': f.file.url, 'name': f.file.name.split('/')[-1]} for f in row.files_8a.all()],
        })

    sec4_rows = []
    for row in village_data.sec4_rows.prefetch_related('files_15_2').order_by('id'):
        files_by_key = {'main': [], 'paper1': [], 'paper2': []}
        for f in row.files_15_2.all():
            key = (getattr(f, 'field_key', '') or 'main').strip() or 'main'
            if key not in files_by_key:
                key = 'main'
            files_by_key[key].append({'id': f.id, 'url': f.file.url, 'name': f.file.name.split('/')[-1]})
        sec4_rows.append({
            'id': row.id,
            'adhisuchana_kramank': row.adhisuchana_kramank,
            'adhisuchana_date': row.adhisuchana_date.isoformat() if row.adhisuchana_date else '',
            'paper1_name': row.paper1_name,
            'paper1_date': row.paper1_date.isoformat() if row.paper1_date else '',
            'paper2_name': row.paper2_name,
            'paper2_date': row.paper2_date.isoformat() if row.paper2_date else '',
            'files': files_by_key,
        })

    sec8_rows = []
    for row in village_data.sec8_rows.prefetch_related('files_18_1').order_by('id'):
        sec8_rows.append({
            'id': row.id,
            'adhisuchana_kramank': row.adhisuchana_kramank,
            'adhisuchana_date': row.adhisuchana_date.isoformat() if row.adhisuchana_date else '',
            'files': [{'id': f.id, 'url': f.file.url, 'name': f.file.name.split('/')[-1]} for f in row.files_18_1.all()],
        })

    sec15 = []
    for r in village_data.sec15_rates.select_related('rr_rate').all():
        sec15.append({
            'rr_rate_id': r.rr_rate_id,
            'approved_rate': float(r.approved_rate) if r.approved_rate is not None else None
        })

    return JsonResponse({
        'found': True,
        'data': data,
        'files_map': files_map,
        'sec4_rows': sec4_rows,
        'sec8_rows': sec8_rows,
        'sec26_8a_records': sec26,
        'sec15_rates': sec15
    })


@login_required
def get_village_sec15_rates(request):
    district = (request.GET.get('district') or '').strip()
    taluka = (request.GET.get('taluka') or '').strip()
    village = (request.GET.get('village') or '').strip()

    if not village:
        return JsonResponse({'found': False, 'rates': [], 'message': 'village is required'}, status=400)

    base_qs = ReadyReckonerInfo.objects.filter(village__iexact=village)
    if district:
        base_qs = base_qs.filter(district__iexact=district)
    if taluka:
        base_qs = base_qs.filter(taluka__iexact=taluka)

    latest_year = base_qs.order_by('-year').values_list('year', flat=True).first()
    if not latest_year:
        return JsonResponse({'found': False, 'rates': [], 'message': 'No ready reckoner data found for selected village'})

    village_data = VillageData.objects.filter(
        district__iexact=district,
        taluka__iexact=taluka,
        village__iexact=village
    ).order_by('-updated_at').first()
    approved_map = {}
    if village_data:
        approved_map = {
            item.rr_rate_id: float(item.approved_rate) if item.approved_rate is not None else None
            for item in village_data.sec15_rates.all()
        }

    rates_payload = []
    infos = base_qs.filter(year=latest_year).prefetch_related('rates').order_by('assessment_type')
    for info in infos:
        for rate in info.rates.order_by('assessment_range_min', 'assessment_range_max'):
            rates_payload.append({
                'rr_rate_id': rate.id,
                'assessment_type': info.assessment_type,
                'village_type': rate.village_type or 'gramin',
                'assessment_range': f"{rate.assessment_range_min} - {rate.assessment_range_max}",
                'shighrasiddha_vibhag': rate.shighrasiddha_vibhag or '',
                'ready_reckoner_rate': float(rate.rate),
                'unit': info.unit,
                'approved_rate': approved_map.get(rate.id)
            })

    return JsonResponse({
        'found': bool(rates_payload),
        'year': latest_year,
        'rates': rates_payload,
        'message': '' if rates_payload else 'No ready reckoner rates found for selected village'
    })
