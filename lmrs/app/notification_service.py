import csv
import io
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime

from django.db import connection
from django.http import HttpResponse
from django.utils import timezone

from app.models import Notification, NotificationCommonInfo, NotificationFile, RorDistrict


logger = logging.getLogger(__name__)


HISSA_TRANSLITERATION = str.maketrans({
    "अ": "a",
    "आ": "a",
    "ब": "b",
    "क": "k",
    "ड": "d",
    "c": "k",
    "C": "k",
})


def clean_text(value):
    return str(value or "").strip()


def parse_display_date(value):
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def format_display_date(value):
    if not value:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    parsed = parse_display_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else clean_text(value)


def _truthy(value):
    return clean_text(value).lower() in {"1", "true", "yes", "on"}


def _safe_file_payload(file_record):
    file_obj = file_record.file
    try:
        url = file_obj.url
    except Exception:
        url = ""
    try:
        size = file_obj.size
    except Exception:
        size = 0
    return {
        "id": file_record.id,
        "url": url,
        "name": file_record.original_name or getattr(file_obj, "name", ""),
        "size": size,
        "date": timezone.localtime(file_record.uploaded_at).strftime("%d/%m/%Y %H:%M") if file_record.uploaded_at else "",
    }


def notification_files_map(notification):
    files_map = defaultdict(list)
    seen = set()
    for file_record in notification.files.all():
        payload = _safe_file_payload(file_record)
        key = (file_record.field_key, payload["name"], payload["size"])
        if key in seen:
            continue
        seen.add(key)
        files_map[file_record.field_key].append(payload)
    return dict(files_map)


NOTIFICATION_FILE_SLOTS = [
    "land_plan_file",
    "land_autocad_file",
    "area_excel_file",
    "sec3_file",
    "sec152_file",
    "sec154_file",
    "sec154_notif_file",
    "joint_survey_saksh_naksha",
    "joint_survey_autocad",
    "joint_survey_sanyukta_naksha",
    "joint_survey_parishisht16",
    "sec181_file",
    "shuddhipatrak_file",
]


def save_notification_files(notification, request_files, extra_slots=None):
    existing = set()
    for file_record in notification.files.all():
        payload = _safe_file_payload(file_record)
        existing.add((file_record.field_key, payload["name"], payload["size"]))
    all_slots = list(NOTIFICATION_FILE_SLOTS) + list(extra_slots or [])
    if request_files:
        all_slots.extend(list(request_files.keys()))
    seen_slots = set()
    for slot in all_slots:
        if not slot or slot in seen_slots:
            continue
        seen_slots.add(slot)
        for uploaded_file in request_files.getlist(slot):
            signature = (slot, getattr(uploaded_file, "name", ""), getattr(uploaded_file, "size", 0))
            if signature in existing:
                continue
            NotificationFile.objects.create(
                notification=notification,
                field_key=slot,
                file=uploaded_file,
                original_name=getattr(uploaded_file, "name", ""),
            )
            existing.add(signature)


def delete_notification_file(file_id):
    deleted, _ = NotificationFile.objects.filter(id=file_id).delete()
    return bool(deleted)


CPI_FIELDS = [
    "project_name",
    "project_purpose",
    "approval_no",
    "approval_date",
    "agency_name",
    "special_project_name",
    "officer1_name",
    "officer1_post",
    "officer2_name",
    "officer2_post",
    "officer3_name",
    "officer3_post",
    "officer3_email",
    "officer3_phone",
    "officer4_name",
    "officer4_post",
]


def fixed_cpi_values(schema_name=""):
    return {}


def fixed_cpi_model_values(schema_name=""):
    return {}


def _location_key(value):
    text = clean_text(value).translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    text = text.translate(str.maketrans({"ळ": "ल", "ऱ": "र"})).casefold()
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def _scope_payload(data):
    scope_type = clean_text(data.get("scope_type")) or NotificationCommonInfo.SCOPE_GLOBAL
    if scope_type not in {
        NotificationCommonInfo.SCOPE_GLOBAL,
        NotificationCommonInfo.SCOPE_DIVISION,
        NotificationCommonInfo.SCOPE_DISTRICT,
    }:
        scope_type = NotificationCommonInfo.SCOPE_GLOBAL
    division_code = clean_text(data.get("division_code"))
    division_name = clean_text(data.get("division_name"))
    district_code = clean_text(data.get("district_code"))
    district_name = clean_text(data.get("district_name") or data.get("district"))
    if scope_type == NotificationCommonInfo.SCOPE_GLOBAL:
        division_code = division_name = district_code = district_name = ""
    elif scope_type == NotificationCommonInfo.SCOPE_DIVISION:
        district_code = district_name = ""
    return {
        "scope_type": scope_type,
        "division_code": division_code,
        "division_name": division_name,
        "district_code": district_code,
        "district_name": district_name,
    }


def _global_cpi():
    return (
        NotificationCommonInfo.objects
        .filter(scope_type=NotificationCommonInfo.SCOPE_GLOBAL)
        .order_by("-updated_at")
        .first()
        or NotificationCommonInfo.objects.order_by("-updated_at").first()
    )


def _find_ror_district(district_name="", district_code=""):
    if district_code:
        found = RorDistrict.objects.select_related("division").filter(code=district_code).first()
        if found:
            return found
    wanted_key = _location_key(district_name)
    if not wanted_key:
        return None
    for district in RorDistrict.objects.select_related("division").all():
        values = [district.name, *(district.aliases or [])]
        if wanted_key in {_location_key(value) for value in values if clean_text(value)}:
            return district
    return None


def _cpi_for_division(division_code="", division_name=""):
    qs = NotificationCommonInfo.objects.filter(scope_type=NotificationCommonInfo.SCOPE_DIVISION)
    if division_code:
        found = qs.filter(division_code=division_code).order_by("-updated_at").first()
        if found:
            return found
    wanted_key = _location_key(division_name)
    if wanted_key:
        for cpi in qs.order_by("-updated_at"):
            if _location_key(cpi.division_name) == wanted_key:
                return cpi
    return None


def _cpi_for_district(district_code="", district_name=""):
    qs = NotificationCommonInfo.objects.filter(scope_type=NotificationCommonInfo.SCOPE_DISTRICT)
    if district_code:
        found = qs.filter(district_code=district_code).order_by("-updated_at").first()
        if found:
            return found
    wanted_key = _location_key(district_name)
    if wanted_key:
        for cpi in qs.order_by("-updated_at"):
            if _location_key(cpi.district_name) == wanted_key:
                return cpi
    return None


def get_latest_cpi(*, scope_type="", division_code="", division_name="", district_code="", district_name="", district=""):
    if scope_type:
        scope = _scope_payload({
            "scope_type": scope_type,
            "division_code": division_code,
            "division_name": division_name,
            "district_code": district_code,
            "district_name": district_name or district,
        })
        if scope["scope_type"] == NotificationCommonInfo.SCOPE_GLOBAL:
            return _global_cpi()
        if scope["scope_type"] == NotificationCommonInfo.SCOPE_DIVISION:
            return _cpi_for_division(scope["division_code"], scope["division_name"])
        return _cpi_for_district(scope["district_code"], scope["district_name"])

    district_obj = _find_ror_district(district_name or district, district_code)
    district_cpi = _cpi_for_district(
        district_code or getattr(district_obj, "code", ""),
        district_name or district or getattr(district_obj, "name", ""),
    )
    if district_cpi:
        return district_cpi
    division_obj = getattr(district_obj, "division", None)
    division_cpi = _cpi_for_division(
        division_code or getattr(district_obj, "div_code", ""),
        division_name or getattr(division_obj, "name", ""),
    )
    if division_cpi:
        return division_cpi
    return _global_cpi()


def cpi_payload(cpi):
    payload = {
        "scope_type": NotificationCommonInfo.SCOPE_GLOBAL,
        "division_code": "",
        "division_name": "",
        "district_code": "",
        "district_name": "",
    }
    if not cpi:
        payload.update({field: "" for field in CPI_FIELDS})
    else:
        payload.update({
            "scope_type": cpi.scope_type or NotificationCommonInfo.SCOPE_GLOBAL,
            "division_code": cpi.division_code or "",
            "division_name": cpi.division_name or "",
            "district_code": cpi.district_code or "",
            "district_name": cpi.district_name or "",
        })
        for field in CPI_FIELDS:
            value = getattr(cpi, field)
            payload[field] = format_display_date(value) if field == "approval_date" else (value or "")
        payload["officer3_order_file_url"] = cpi.officer3_order_file.url if cpi.officer3_order_file else ""
        payload["officer3_order_file_name"] = cpi.officer3_order_original_name or (
            cpi.officer3_order_file.name.rsplit("/", 1)[-1] if cpi.officer3_order_file else ""
        )
    fixed = fixed_cpi_values()
    payload.update(fixed)
    payload["fixed_fields"] = sorted(fixed)
    return payload


def save_cpi(user, post_data, request_files=None):
    scope = _scope_payload(post_data)
    lookup = {"scope_type": scope["scope_type"]}
    if scope["scope_type"] == NotificationCommonInfo.SCOPE_DIVISION:
        lookup["division_code"] = scope["division_code"]
    elif scope["scope_type"] == NotificationCommonInfo.SCOPE_DISTRICT:
        lookup["district_code"] = scope["district_code"]
    user_id = user.id if user and user.is_authenticated else 1
    cpi = (
        NotificationCommonInfo.objects
        .filter(**lookup)
        .order_by("-updated_at")
        .first()
        or NotificationCommonInfo(created_by_user_id=user_id)
    )
    for field, value in scope.items():
        setattr(cpi, field, value)
    for field in CPI_FIELDS:
        value = clean_text(post_data.get(field))
        if field == "approval_date":
            setattr(cpi, field, parse_display_date(value))
        else:
            setattr(cpi, field, value)
    for field, value in fixed_cpi_model_values().items():
        setattr(cpi, field, value)
    delete_order = clean_text(post_data.get("officer3_order_delete")) in {"1", "true", "True", "on"}
    uploaded_order = request_files.get("officer3_order_file") if request_files else None
    if (delete_order or uploaded_order) and cpi.officer3_order_file:
        cpi.officer3_order_file.delete(save=False)
        cpi.officer3_order_original_name = ""
    if uploaded_order:
        cpi.officer3_order_file = uploaded_order
        cpi.officer3_order_original_name = getattr(uploaded_order, "name", "")
    elif delete_order:
        cpi.officer3_order_file = ""
    cpi.save()
    return cpi


def _area_rows(post_data, prefix):
    rows = []
    count = int(post_data.get(f"{prefix}_count") or 0)
    for idx in range(count):
        row = {
            "gut_number": clean_text(post_data.get(f"{prefix}_gut_{idx}")),
            "hissa_number": clean_text(post_data.get(f"{prefix}_hissa_{idx}")),
            "district": clean_text(post_data.get(f"{prefix}_district_{idx}")),
            "taluka": clean_text(post_data.get(f"{prefix}_taluka_{idx}")),
            "village": clean_text(post_data.get(f"{prefix}_village_{idx}")),
            "area_712": clean_text(post_data.get(f"{prefix}_area712_{idx}")),
            "proposed_area": clean_text(post_data.get(f"{prefix}_proposed_{idx}")),
            "remark": clean_text(post_data.get(f"{prefix}_remark_{idx}")),
        }
        if row["gut_number"]:
            rows.append(row)
    return rows


def _puravani_blocks(post_data):
    if not _truthy(post_data.get("has_puravani")):
        return []
    blocks = []
    count = int(post_data.get("puravani_block_count") or 0)
    for idx in range(count):
        prefix = f"puravani_block_{idx}"
        display_idx = idx + 1
        sec3_has_pub = _truthy(post_data.get(f"{prefix}_sec3_has_pub") or post_data.get(f"puravani_sec3_{display_idx}_has_pub"))
        sec152_has_pub = _truthy(post_data.get(f"{prefix}_sec152_has_pub") or post_data.get(f"puravani_sec152_{display_idx}_has_pub"))
        sec154_has_pub = _truthy(post_data.get(f"{prefix}_sec154_has_pub") or post_data.get(f"puravani_sec154_{display_idx}_has_pub"))
        sec181_has_pub = _truthy(post_data.get(f"{prefix}_sec181_has_pub") or post_data.get(f"puravani_sec181_{display_idx}_has_pub"))
        block = {
            "sec3_has_pub": "1" if sec3_has_pub else "",
            "sec152_has_pub": "1" if sec152_has_pub else "",
            "sec154_has_pub": "1" if sec154_has_pub else "",
            "sec181_has_pub": "1" if sec181_has_pub else "",
            "pub_no": clean_text(post_data.get(f"{prefix}_sec3_pub_no") or post_data.get(f"puravani_sec3_{display_idx}_pub_no") or post_data.get(f"{prefix}_pub_no")) if sec3_has_pub else "",
            "pub_date": clean_text(post_data.get(f"{prefix}_sec3_pub_date") or post_data.get(f"puravani_sec3_{display_idx}_pub_date") or post_data.get(f"{prefix}_pub_date")) if sec3_has_pub else "",
            "sec3_pub_no": clean_text(post_data.get(f"{prefix}_sec3_pub_no") or post_data.get(f"puravani_sec3_{display_idx}_pub_no") or post_data.get(f"{prefix}_pub_no")) if sec3_has_pub else "",
            "sec3_pub_date": clean_text(post_data.get(f"{prefix}_sec3_pub_date") or post_data.get(f"puravani_sec3_{display_idx}_pub_date") or post_data.get(f"{prefix}_pub_date")) if sec3_has_pub else "",
            "sec152_pub_no": clean_text(post_data.get(f"{prefix}_sec152_pub_no") or post_data.get(f"puravani_sec152_{display_idx}_pub_no")) if sec152_has_pub else "",
            "sec152_pub_date": clean_text(post_data.get(f"{prefix}_sec152_pub_date") or post_data.get(f"puravani_sec152_{display_idx}_pub_date")) if sec152_has_pub else "",
            "sec154_pub_no": clean_text(post_data.get(f"{prefix}_sec154_pub_no") or post_data.get(f"puravani_sec154_{display_idx}_pub_no")) if sec154_has_pub else "",
            "sec154_pub_date": clean_text(post_data.get(f"{prefix}_sec154_pub_date") or post_data.get(f"puravani_sec154_{display_idx}_pub_date")) if sec154_has_pub else "",
            "sec181_pub_no": clean_text(post_data.get(f"{prefix}_sec181_pub_no") or post_data.get(f"puravani_sec181_{display_idx}_pub_no")) if sec181_has_pub else "",
            "sec181_pub_date": clean_text(post_data.get(f"{prefix}_sec181_pub_date") or post_data.get(f"puravani_sec181_{display_idx}_pub_no")) if sec181_has_pub else "",
            "area_rows": _area_rows(post_data, f"{prefix}_area"),
        }
        if (
            block["pub_no"]
            or block["pub_date"]
            or block["sec152_pub_no"]
            or block["sec152_pub_date"]
            or block["sec154_pub_no"]
            or block["sec154_pub_date"]
            or block["sec181_pub_no"]
            or block["sec181_pub_date"]
            or block["area_rows"]
        ):
            blocks.append(block)
    return blocks


def _paper_fields(post_data, prefix):
    return {
        f"{prefix}_paper{index}_{field}": clean_text(post_data.get(f"{prefix}_paper{index}_{field}"))
        for index in (1, 2)
        for field in ("name", "date")
    }


def _sdo_rows(post_data):
    rows = []
    count = int(post_data.get("sdo_count") or 0)
    for idx in range(count):
        row = {
            "sdo_name": clean_text(post_data.get(f"sdo_name_{idx}")),
            "sdo_subdivision": clean_text(post_data.get(f"sdo_subdivision_{idx}")),
            "sdo_officer_name": clean_text(post_data.get(f"sdo_officer_name_{idx}")),
            "sdo_address": clean_text(post_data.get(f"sdo_address_{idx}")),
            "sdo_taluka": clean_text(post_data.get(f"sdo_taluka_{idx}")),
        }
        if any(row.values()):
            rows.append(row)
    return rows


def _ghatak_entries(post_data, prefix):
    entries = []
    count = int(post_data.get(f"{prefix}_ghatak_count") or 0)
    for idx in range(count):
        entry = {
            "kabjedar": clean_text(post_data.get(f"{prefix}_ghatak_kabjedar_{idx}")),
            "type": clean_text(post_data.get(f"{prefix}_ghatak_type_{idx}")),
            "detail": clean_text(post_data.get(f"{prefix}_ghatak_detail_{idx}")),
            "count": clean_text(post_data.get(f"{prefix}_ghatak_count_value_{idx}")),
            "number": clean_text(post_data.get(f"{prefix}_ghatak_number_{idx}")),
            "valuation": clean_text(post_data.get(f"{prefix}_ghatak_valuation_{idx}")),
        }
        if any(entry.values()):
            entries.append(entry)
    return entries


def _joint_survey(post_data):
    row_count = int(post_data.get("js_row_count") or 0)
    rows = []
    for idx in range(row_count):
        prefix = f"js_row_{idx}"
        row = {
            "gut_number": clean_text(post_data.get(f"{prefix}_gut")),
            "hissa_number": clean_text(post_data.get(f"{prefix}_hissa")),
            "land_class": clean_text(post_data.get(f"{prefix}_class")),
            "total_area_712": clean_text(post_data.get(f"{prefix}_total_area_712")),
            "cultivable_area": clean_text(post_data.get(f"{prefix}_cultivable_area")),
            "potkharaba_area": clean_text(post_data.get(f"{prefix}_potkharaba_area")),
            "aakar_712": clean_text(post_data.get(f"{prefix}_aakar_712")),
            "acquired_total_area": clean_text(post_data.get(f"{prefix}_acquired_total_area")),
            "kharaba": clean_text(post_data.get(f"{prefix}_kharaba")),
            "lagan": clean_text(post_data.get(f"{prefix}_lagan")),
            "aakar_acquired": clean_text(post_data.get(f"{prefix}_aakar_acquired")),
            "holder_name": clean_text(post_data.get(f"{prefix}_holder_name")),
            "building": clean_text(post_data.get(f"{prefix}_building")),
            "well": clean_text(post_data.get(f"{prefix}_well")),
            "trees": clean_text(post_data.get(f"{prefix}_trees")),
            "tree_numbers": clean_text(post_data.get(f"{prefix}_tree_numbers")),
            "remark": clean_text(post_data.get(f"{prefix}_remark")),
            "ghatak": _ghatak_entries(post_data, prefix),
        }
        if any(value for key, value in row.items() if key != "ghatak") or row["ghatak"]:
            rows.append(row)
    return {
        "mo_r_no": clean_text(post_data.get("js_mo_r_no")),
        "survey_date": clean_text(post_data.get("js_survey_date")),
        "surveyor_name": clean_text(post_data.get("js_surveyor_name")),
        "rows": rows,
    }


def _shuddhipatrak_rows(post_data):
    rows = []
    count = int(post_data.get("shuddhipatrak_row_count") or 0)
    for idx in range(count):
        row = {
            "subject": clean_text(post_data.get(f"shuddhipatrak_subject_{idx}")),
            "notification_no": clean_text(post_data.get(f"shuddhipatrak_notification_no_{idx}")),
            "gut_number": clean_text(post_data.get(f"shuddhipatrak_gut_{idx}")),
            "column_no": clean_text(post_data.get(f"shuddhipatrak_column_{idx}")),
            "area_old": clean_text(post_data.get(f"shuddhipatrak_area_old_{idx}")),
            "area_new": clean_text(post_data.get(f"shuddhipatrak_area_new_{idx}")),
        }
        if any(row.values()):
            rows.append(row)
    return rows


def _cascade_edit_rows(post_data, prefix, acquired=False):
    rows = []
    count = int(post_data.get(f"{prefix}_count") or 0)
    area_key = "acquired_area" if acquired else "proposed_area"
    post_area_key = "acquired" if acquired else "proposed"
    for idx in range(count):
        row = {
            "gut_number": clean_text(post_data.get(f"{prefix}_gut_{idx}")),
            "hissa_number": clean_text(post_data.get(f"{prefix}_hissa_{idx}")),
            "district": clean_text(post_data.get(f"{prefix}_district_{idx}")),
            "taluka": clean_text(post_data.get(f"{prefix}_taluka_{idx}")),
            "village": clean_text(post_data.get(f"{prefix}_village_{idx}")),
            "area_712": clean_text(post_data.get(f"{prefix}_area712_{idx}")),
            area_key: clean_text(post_data.get(f"{prefix}_{post_area_key}_{idx}")),
        }
        if acquired:
            row["proposed_area"] = row["acquired_area"]
        if row["gut_number"] or row["hissa_number"] or row["area_712"] or row[area_key]:
            row["is_edited"] = True
            rows.append(row)
    return rows


def _cascade_deleted_rows(post_data, prefix):
    rows = []
    count = int(post_data.get(f"{prefix}_deleted_count") or 0)
    for idx in range(count):
        row = {
            "gut_number": clean_text(post_data.get(f"{prefix}_deleted_gut_{idx}")),
            "hissa_number": clean_text(post_data.get(f"{prefix}_deleted_hissa_{idx}")),
            "area_712": clean_text(post_data.get(f"{prefix}_deleted_area712_{idx}")),
            "proposed_area": clean_text(post_data.get(f"{prefix}_deleted_proposed_{idx}")),
        }
        if any(row.values()):
            rows.append(row)
    return rows


def parse_notification_sections(post_data):
    has_sec3_pub = _truthy(post_data.get("has_sec3_pub"))
    has_sec152_pub = _truthy(post_data.get("has_sec152_pub"))
    has_sec154_pub = _truthy(post_data.get("has_sec154_pub"))
    has_sec154_notif_pub = _truthy(post_data.get("has_sec154_notif_pub"))
    has_sec181_pub = _truthy(post_data.get("has_sec181_pub"))
    has_puravani = _truthy(post_data.get("has_puravani"))
    shuddhipatrak_done = _truthy(post_data.get("shuddhipatrak_done"))
    cascade_edits = {
        "sec3_rows": _cascade_edit_rows(post_data, "cascade_sec3"),
        "sec152_rows": _cascade_edit_rows(post_data, "cascade_sec152"),
        "sec154_bhusampadan_rows": _cascade_edit_rows(post_data, "cascade_sec154"),
        "sec181_rows": _cascade_edit_rows(post_data, "cascade_sec181", acquired=True),
    }
    sections = {
        "required_areas": _area_rows(post_data, "area"),
        "has_sec3_pub": "1" if has_sec3_pub else "",
        "sec3_pub_no": clean_text(post_data.get("sec3_pub_no")) if has_sec3_pub else "",
        "sec3_pub_date": clean_text(post_data.get("sec3_pub_date")) if has_sec3_pub else "",
        **(_paper_fields(post_data, "sec3") if has_sec3_pub else {
            f"sec3_paper{index}_{field}": ""
            for index in (1, 2)
            for field in ("name", "date")
        }),
        "has_puravani": "1" if has_puravani else "",
        "puravani_blocks": _puravani_blocks(post_data),
        "has_sec152_pub": "1" if has_sec152_pub else "",
        "sec152_pub_no": clean_text(post_data.get("sec152_pub_no")) if has_sec152_pub else "",
        "sec152_pub_date": clean_text(post_data.get("sec152_pub_date")) if has_sec152_pub else "",
        **(_paper_fields(post_data, "sec152") if has_sec152_pub else {
            f"sec152_paper{index}_{field}": ""
            for index in (1, 2)
            for field in ("name", "date")
        }),
        "has_sec154_pub": "1" if has_sec154_pub else "",
        "sec154_pub_no": clean_text(post_data.get("sec154_pub_no")) if has_sec154_pub else "",
        "sec154_pub_date": clean_text(post_data.get("sec154_pub_date")) if has_sec154_pub else "",
        "has_sec154_notif_pub": "1" if has_sec154_notif_pub else "",
        "sec154_notif_pub_no": clean_text(post_data.get("sec154_notif_pub_no")) if has_sec154_notif_pub else "",
        "sec154_notif_pub_date": clean_text(post_data.get("sec154_notif_pub_date")) if has_sec154_notif_pub else "",
        "sdo_rows": _sdo_rows(post_data),
        "joint_survey": _joint_survey(post_data),
        "has_sec181_pub": "1" if has_sec181_pub else "",
        "sec181_pub_no": clean_text(post_data.get("sec181_pub_no")) if has_sec181_pub else "",
        "sec181_pub_date": clean_text(post_data.get("sec181_pub_date")) if has_sec181_pub else "",
        "sec17_decision_details": clean_text(post_data.get("sec17_decision_details")),
        **_paper_fields(post_data, "sec19b"),
        "shuddhipatrak_done": "1" if shuddhipatrak_done else "",
        "shuddhipatrak_no": clean_text(post_data.get("shuddhipatrak_no")) if shuddhipatrak_done else "",
        "shuddhipatrak_date": clean_text(post_data.get("shuddhipatrak_date")) if shuddhipatrak_done else "",
        "shuddhipatrak_pub_no": clean_text(post_data.get("shuddhipatrak_pub_no")) if shuddhipatrak_done else "",
        "shuddhipatrak_pub_date": clean_text(post_data.get("shuddhipatrak_pub_date")) if shuddhipatrak_done else "",
        "shuddhipatrak_rows": _shuddhipatrak_rows(post_data) if shuddhipatrak_done else [],
        "cascade_edits": {key: value for key, value in cascade_edits.items() if value},
        "cascade_deleted": {
            "sec3_rows": _cascade_deleted_rows(post_data, "cascade_sec3"),
            "sec152_rows": _cascade_deleted_rows(post_data, "cascade_sec152"),
            "sec154_bhusampadan_rows": _cascade_deleted_rows(post_data, "cascade_sec154"),
            "sec181_rows": _cascade_deleted_rows(post_data, "cascade_sec181"),
        },
    }
    return sections


def _normalize_gut(value):
    devanagari_digits = str.maketrans("०१२३४५६७८९", "0123456789")
    text = clean_text(value).translate(devanagari_digits).lower()
    if not text:
        return ""
    numeric = re.findall(r"\d+[a-z]?", text)
    if numeric:
        return "/".join(numeric)
    return re.sub(r"[^\w]+", "", text)


def _normalize_hissa(value):
    text = clean_text(value).translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    text = text.translate(HISSA_TRANSLITERATION).casefold()
    text = text.replace("\\", "/").replace("-", "/")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"/+", "/", text)
    return text.strip("/")


def compute_cascade(sections, notification_location=None):
    required_areas = sections.get("required_areas") or []
    notification_location = notification_location or {}

    def project_area_rows(rows):
        return [
            {
                "gut_number": row.get("gut_number", ""),
                "hissa_number": row.get("hissa_number", ""),
                "district": row.get("district") or notification_location.get("district", ""),
                "taluka": row.get("taluka") or notification_location.get("taluka", ""),
                "village": row.get("village") or notification_location.get("village", ""),
                "area_712": row.get("area_712", ""),
                "proposed_area": row.get("proposed_area", ""),
                "remark": row.get("remark", ""),
            }
            for row in rows
        ]

    def row_lookup_key(row):
        base = _normalize_gut(row.get("gut_number"))
        hissa = _normalize_hissa(row.get("hissa_number"))
        return f"{base}/{hissa}" if base and hissa else base

    def merge_cascade_edits(generated_rows, edited_rows):
        if not edited_rows:
            return generated_rows
        edited_by_key = {row_lookup_key(row): row for row in edited_rows if row_lookup_key(row)}
        merged_rows = []
        seen = set()
        for generated in generated_rows:
            key = row_lookup_key(generated)
            edited = edited_by_key.get(key)
            if edited:
                merged_rows.append({**generated, **edited, "is_edited": True})
                seen.add(key)
            else:
                merged_rows.append(generated)
        for edited in edited_rows:
            key = row_lookup_key(edited)
            if not key:
                merged_rows.append(edited)
            elif key not in seen:
                merged_rows.append(edited)
        return merged_rows

    gut_lookup = {row_lookup_key(row): row for row in required_areas if row_lookup_key(row)}
    joint_survey = sections.get("joint_survey") or {}
    survey_rows = joint_survey.get("rows") or []

    def survey_acquired_area(row):
        return row.get("acquired_total_area") or row.get("acquired_area") or row.get("proposed_area") or ""

    # संयुक्त मोजणी rows indexed both गट/हिस्सा-wise and गट-wise.
    survey_by_key = {}
    survey_by_gut = {}
    for row in survey_rows:
        key = row_lookup_key(row)
        if key:
            survey_by_key.setdefault(key, row)
        gut = _normalize_gut(row.get("gut_number"))
        if gut:
            survey_by_gut.setdefault(gut, []).append(row)

    sec181_area_by_key = {}

    def sec181_row(area_row, acquired_area, survey_row=None):
        key = row_lookup_key(area_row)
        if key:
            sec181_area_by_key[key] = acquired_area
        return {
            "gut_number": area_row.get("gut_number", ""),
            "hissa_number": area_row.get("hissa_number", ""),
            "district": area_row.get("district") or notification_location.get("district", ""),
            "taluka": area_row.get("taluka") or notification_location.get("taluka", ""),
            "village": area_row.get("village") or notification_location.get("village", ""),
            "area_712": area_row.get("area_712") or (survey_row or {}).get("total_area_712", ""),
            "proposed_area": acquired_area,
            "acquired_area": acquired_area,
            "remark": area_row.get("remark", ""),
        }

    sec181_rows = []
    if survey_rows:
        # कलम १८(१) carries only the गट that कलम १५(२) *and* संयुक्त मोजणी both hold —
        # a गट added to संयुक्त मोजणी alone never reaches १८(१) — and it lists them
        # हिस्सा-wise the way कलम १५(२) does, not one row per गट.
        area_rows_per_gut = Counter(
            _normalize_gut(row.get("gut_number")) for row in required_areas if row.get("gut_number")
        )
        for area_row in required_areas:
            key = row_lookup_key(area_row)
            gut = _normalize_gut(area_row.get("gut_number"))
            hissa_survey = survey_by_key.get(key)
            if hissa_survey is not None:
                sec181_rows.append(sec181_row(area_row, survey_acquired_area(hissa_survey) or area_row.get("proposed_area", ""), hissa_survey))
                continue
            gut_survey_rows = survey_by_gut.get(gut) or []
            if not gut_survey_rows:
                continue
            gut_survey = gut_survey_rows[0]
            # A गट-level संयुक्त मोजणी figure is this row's area only when the गट has a
            # single हिस्सा; otherwise it is the गट total and must not be repeated on
            # every हिस्सा, so each keeps its own कलम १५(२) area.
            acquired_area = (
                survey_acquired_area(gut_survey)
                if area_rows_per_gut.get(gut, 0) <= 1
                else area_row.get("proposed_area", "")
            )
            sec181_rows.append(sec181_row(area_row, acquired_area, gut_survey))
    else:
        # No संयुक्त मोजणी yet — keep showing the कलम १५(२) rows so the step is not blank.
        for area_row in required_areas:
            sec181_rows.append(sec181_row(area_row, area_row.get("proposed_area", "")))

    cascade = {
        "sec3_rows": project_area_rows(required_areas),
        "sec152_rows": project_area_rows(required_areas),
        "sec154_bhusampadan_rows": project_area_rows(required_areas),
        "sec181_rows": sec181_rows,
    }
    cascade_deleted = sections.get("cascade_deleted") or {}
    for key, deleted_rows in cascade_deleted.items():
        deleted_keys = {row_lookup_key(row) for row in deleted_rows if row_lookup_key(row)}
        if deleted_keys and key in cascade:
            cascade[key] = [row for row in cascade[key] if row_lookup_key(row) not in deleted_keys]
    cascade_edits = sections.get("cascade_edits") or {}
    for key, rows in cascade_edits.items():
        if rows:
            cascade[key] = merge_cascade_edits(cascade.get(key, []), rows)

    # संयुक्त मोजणीप्रमाणे संपादन क्षेत्र always mirrors that हिस्सा's एकूण क्षेत्र from
    # संयुक्त मोजणी, so an older manual edit cannot keep overriding it. Every other
    # column of कलम १८(१) still honours the edit.
    for row in cascade.get("sec181_rows") or []:
        computed_area = sec181_area_by_key.get(row_lookup_key(row))
        if computed_area:
            row["acquired_area"] = computed_area
            row["proposed_area"] = computed_area
    return cascade


def save_notification(*, user, district, taluka, village, sections, status, current_step, request_files, notification=None, common_info=None):
    user_id = user.id if user and user.is_authenticated else 1
    if notification is None:
        notification = Notification(created_by_user_id=user_id)
    notification.district = district
    notification.taluka = taluka
    notification.village = village
    notification.sections = sections
    notification.status = status
    notification.current_step = current_step
    if common_info is not None:
        notification.common_info = common_info
    else:
        notification.common_info = get_latest_cpi(district_name=district)
    notification.save()
    puravani_count = len(sections.get("puravani_blocks") or [])
    extra_slots = [f"puravani_block_{i}_file" for i in range(puravani_count)]
    extra_slots.extend(f"puravani_block_{i}_pdf_file" for i in range(puravani_count))
    extra_slots.extend(f"puravani_block_{i}_autocad_file" for i in range(puravani_count))
    extra_slots.extend(f"puravani_sec3_{i}_file" for i in range(1, puravani_count + 1))
    extra_slots.extend(f"puravani_sec152_{i}_file" for i in range(1, puravani_count + 1))
    extra_slots.extend(f"puravani_sec154_{i}_file" for i in range(1, puravani_count + 1))
    extra_slots.extend(f"puravani_sec181_{i}_file" for i in range(1, puravani_count + 1))
    save_notification_files(notification, request_files, extra_slots=extra_slots)
    return notification


def _legacy_puravani_blocks(sections):
    if not _truthy(sections.get("has_puravani")):
        return []
    legacy_rows = sections.get("puravani_areas") or []
    pub_no = sections.get("puravani_sec3_pub_no", "")
    pub_date = sections.get("puravani_sec3_pub_date", "")
    if not legacy_rows and not pub_no and not pub_date:
        return []
    return [{"pub_no": pub_no, "pub_date": pub_date, "area_rows": legacy_rows}]


def notification_detail_payload(notification):
    sections = dict(notification.sections or {})
    if not sections.get("puravani_blocks"):
        sections["puravani_blocks"] = _legacy_puravani_blocks(sections)
    cascade = compute_cascade(sections, {
        "district": notification.district,
        "taluka": notification.taluka,
        "village": notification.village,
    })
    return {
        "id": notification.id,
        "district": notification.district,
        "taluka": notification.taluka,
        "village": notification.village,
        "status": notification.status,
        "current_step": notification.current_step,
        "sections": sections,
        "cascade": cascade,
        "files_map": notification_files_map(notification),
        "cpi": cpi_payload(notification.common_info) if notification.common_info_id else cpi_payload(get_latest_cpi(district_name=notification.district)),
    }


def export_notifications_csv(queryset):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = 'attachment; filename="notification_records.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "ID", "District", "Taluka", "Village", "Status", "Current Step",
        "Verified", "Sec3 Pub No", "Sec3 Pub Date", "Created At", "Updated At"
    ])
    for obj in queryset:
        sec = obj.sections or {}
        writer.writerow([
            obj.id, obj.district, obj.taluka, obj.village, obj.status, obj.current_step,
            "Yes" if obj.is_verified else "No",
            sec.get("sec3_pub_no", ""), sec.get("sec3_pub_date", ""),
            obj.created_at.strftime("%Y-%m-%d %H:%M"), obj.updated_at.strftime("%Y-%m-%d %H:%M")
        ])
    return response
