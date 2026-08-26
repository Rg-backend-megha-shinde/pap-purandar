import logging
import re
from django.core.files.base import ContentFile
from django.contrib.auth.models import User

from app.models import (
    VillageData,
    VillageDataFile,
    VillageData32_2Row,
    VillageData32_2RowFile,
    VillageData32_1Row,
    VillageData32_1RowFile,
)
from app.notification_service import parse_display_date

logger = logging.getLogger(__name__)


def _normalize_match_text(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().casefold()


def _find_existing_village_data(district, taluka, village):
    try:
        from app.views import find_village_data_record
        return find_village_data_record(district, taluka, village)
    except Exception:
        return VillageData.objects.filter(
            district__iexact=district,
            taluka__iexact=taluka,
            village__iexact=village
        ).first()



def is_village_data_manually_filled(vd, notification=None):
    """
    Returns True if a VillageData record has been manually filled/submitted by a user
    in the Village Info module (e.g. manual sections 10-25 or marked final submitted).
    Auto-created notification shells and partially synced records return False.
    """
    if not vd:
        return False

    if getattr(vd, 'is_final_submitted', False):
        return True

    manual_text_fields = [
        getattr(vd, 'collector_name', ''),
        getattr(vd, 'collector_office_name', ''),
        getattr(vd, 'collector_office_address', ''),
        getattr(vd, 'sec10_prastaav_kramank', ''),
        getattr(vd, 'sec11_patra_kramank', ''),
        getattr(vd, 'sec12_zone_details', ''),
        getattr(vd, 'sec13_kharedi_vikri_details', ''),
        getattr(vd, 'sec14_meeting_details', ''),
        getattr(vd, 'sec16_letter_details', ''),
        getattr(vd, 'sec17_letter_details', ''),
        getattr(vd, 'sec18_letter_details', ''),
        getattr(vd, 'sec19_letter_details', ''),
        getattr(vd, 'sec20_letter_details', ''),
        getattr(vd, 'sec21_prastaav', ''),
        getattr(vd, 'sec21_karyavrutant', ''),
        getattr(vd, 'sec23_kramank', ''),
        getattr(vd, 'sec24_court_details', ''),
        getattr(vd, 'sec25_kramank', ''),
    ]
    if any(str(f or "").strip() for f in manual_text_fields):
        return True

    manual_json_fields = [
        getattr(vd, 'sec13_rows', []),
        getattr(vd, 'sec14_rows', []),
        getattr(vd, 'sec16_rows', []),
        getattr(vd, 'sec17_rows', []),
        getattr(vd, 'sec18_rows', []),
        getattr(vd, 'sec19_rows', []),
        getattr(vd, 'sec20_rows', []),
        getattr(vd, 'sec21_rows', []),
        getattr(vd, 'sec24_account_rows', []),
        getattr(vd, 'sec25_map_rows', []),
    ]
    for row_list in manual_json_fields:
        if isinstance(row_list, list) and len(row_list) > 0:
            for item in row_list:
                if isinstance(item, dict) and any(str(sv or "").strip() for sv in item.values()):
                    return True

    return False


def is_village_data_empty(vd):
    return not is_village_data_manually_filled(vd)


def sync_village_data_from_notification(notification, user_id=None):
    """
    Syncs Notification data into a VillageData record.
    CRITICAL RULE: Existing VillageData records with manual user data MUST NOT BE OVERWRITTEN!
    VillageData forms will auto-create or update for notification-synced/shell forms.
    """
    if not notification or not notification.district or not notification.taluka or not notification.village:
        return None

    district = notification.district.strip()
    taluka = notification.taluka.strip()
    village = notification.village.strip()

    # Safeguard: Check if VillageData already exists for this district, taluka, village
    existing_village_data = _find_existing_village_data(district, taluka, village)

    if existing_village_data is not None and getattr(existing_village_data, 'is_final_submitted', False):
        logger.info(
            f"[Notification Sync] VillageData for village '{village}' is marked final submitted "
            f"(ID: {existing_village_data.id}). Skipping sync."
        )
        return None

    # Fetch user
    user = None
    if user_id:
        user = User.objects.filter(id=user_id).first()
    if not user and notification.created_by_user_id:
        user = User.objects.filter(id=notification.created_by_user_id).first()
    if not user:
        user = User.objects.filter(is_superuser=True).first() or User.objects.first()

    sections = notification.sections or {}
    common_info = notification.common_info

    # 1. Basic info & Purpose
    purpose = (common_info.project_purpose if common_info else "") or ""
    sec1_adesh = (common_info.approval_no if common_info else "") or ""
    sec1_date_val = common_info.approval_date if common_info else None

    # 2. Section 1 (प्रशासकीय मान्यता & अधिसूचना क्षेत्र)
    block_rows = []
    total_area = 0
    required_areas = sections.get("required_areas") or []
    for row in required_areas:
        gut = (row.get("gut_number") or "").strip()
        hissa = (row.get("hissa_number") or "").strip()
        full_gut = f"{gut}/{hissa}" if gut and hissa else (gut or hissa)
        area_str = str(row.get("proposed_area") or row.get("area_712") or "0").strip()
        try:
            val = float(area_str)
        except (ValueError, TypeError):
            val = 0.0
        total_area += val
        block_rows.append({
            "gut_mode": "other" if not gut else "listed",
            "gut_number": full_gut,
            "other_gut": full_gut,
            "notified_area": area_str,
        })

    active_rows = block_rows if block_rows else [{}]
    notified_area_rows = [
        {
            "block_index": 0,
            "section_key": "sec1",
            "rows": active_rows,
        },
        {
            "block_index": 1,
            "section_key": "sec3",
            "rows": active_rows,
        },
        {
            "block_index": 2,
            "section_key": "sec4",
            "rows": active_rows,
        },
        {
            "block_index": 3,
            "section_key": "sec6",
            "rows": active_rows,
        },
    ]

    sec1_admin_approvals = []
    if sec1_adesh or sec1_date_val:
        date_str = (
            sec1_date_val.strftime("%Y-%m-%d")
            if hasattr(sec1_date_val, "strftime")
            else str(sec1_date_val or "")
        )
        sec1_admin_approvals.append({
            "adhisuchana_kramank": sec1_adesh,
            "date": date_str,
            "files": [],
        })

    # 3. Section 2 / Kalam 32(2) (अधिसूचना व वर्तमानपत्रे)
    sec152_no = str(sections.get("sec152_pub_no") or sections.get("sec3_pub_no") or "").strip()
    sec152_date_val = parse_display_date(sections.get("sec152_pub_date") or sections.get("sec3_pub_date"))
    sec152_p1_name = str(sections.get("sec152_paper1_name") or sections.get("sec3_paper1_name") or "").strip()
    sec152_p1_date_val = parse_display_date(sections.get("sec152_paper1_date") or sections.get("sec3_paper1_date"))
    sec152_p2_name = str(sections.get("sec152_paper2_name") or sections.get("sec3_paper2_name") or "").strip()
    sec152_p2_date_val = parse_display_date(sections.get("sec152_paper2_date") or sections.get("sec3_paper2_date"))

    # 4. Section 3 (प्राधिकृत भूसंपादन अधिकारी नियुक्ती)
    sec154_pub_no = str(sections.get("sec154_pub_no") or "").strip()
    sec154_pub_date = parse_display_date(sections.get("sec154_pub_date"))
    sec154_date_str = (
        sec154_pub_date.strftime("%Y-%m-%d")
        if hasattr(sec154_pub_date, "strftime") and sec154_pub_date
        else str(sections.get("sec154_pub_date") or "")
    )
    sdo_rows_notif = sections.get("sdo_rows") or []
    sec3_rows_v = []
    for r in sdo_rows_notif:
        sec3_rows_v.append({
            "upvibhag_name": str(r.get("sdo_subdivision") or r.get("subdivision_name") or "").strip(),
            "officer_name": str(r.get("sdo_officer_name") or r.get("officer_name") or "").strip(),
            "address": str(r.get("sdo_address") or r.get("address") or "").strip(),
            "adhisuchana_kramank": sec154_pub_no,
            "date": sec154_date_str,
            "files": [],
        })
    if not sec3_rows_v and (sec154_pub_no or sec154_date_str):
        sec3_rows_v = [{
            "upvibhag_name": "",
            "officer_name": "",
            "address": "",
            "adhisuchana_kramank": sec154_pub_no,
            "date": sec154_date_str,
            "files": [],
        }]

    sec3_upvibhag = sec3_rows_v[0].get("upvibhag_name", "") if sec3_rows_v else ""

    # 5. Section 5 (भूसंपादन प्रस्ताव)
    sec5_no = str(
        sections.get("sec154_notif_pub_no")
        or sections.get("sec154_pub_no")
        or sections.get("sec5_prastaav_kramank")
        or sections.get("prastaav_kramank")
        or ""
    ).strip()
    sec5_date_val = parse_display_date(
        sections.get("sec154_notif_pub_date")
        or sections.get("sec154_pub_date")
        or sections.get("sec5_date")
        or sections.get("prastaav_date")
    )

    # 6. Section 6 (संयुक्त मोजणी)
    js = sections.get("joint_survey") or {}
    sec6_reg = str(
        js.get("mo_r_no")
        or js.get("register_number")
        or sections.get("sec6_register_number")
        or sections.get("mo_r_no")
        or ""
    ).strip()
    sec6_date_val = parse_display_date(
        js.get("survey_date")
        or js.get("date")
        or sections.get("sec6_date")
        or sections.get("survey_date")
    )
    sec6_date_str = (
        sec6_date_val.strftime("%Y-%m-%d")
        if hasattr(sec6_date_val, "strftime") and sec6_date_val
        else str(js.get("survey_date") or js.get("date") or "")
    )
    sec6_rows_v = [{
        "register_number": sec6_reg,
        "date": sec6_date_str,
        "files": {"parishisht16_files": [], "nakasha_files": []}
    }] if (sec6_reg or sec6_date_str) else []

    # 7. Section 7 (कलम 17 सुनावणी निर्णय)
    sec7_details = str(sections.get("sec17_decision_details") or "").strip()

    # 8. Section 8 / Kalam 32(1) (कलम १८(१) / कलम ३२(१) अंतिम अधिसूचना)
    sec181_no = str(sections.get("sec181_pub_no") or "").strip()
    sec181_date_val = parse_display_date(sections.get("sec181_pub_date"))
    sec181_p1_name = str(sections.get("sec181_paper1_name") or sections.get("sec19b_paper1_name") or "").strip()
    sec181_p1_date_val = parse_display_date(sections.get("sec181_paper1_date") or sections.get("sec19b_paper1_date"))
    sec181_p2_name = str(sections.get("sec181_paper2_name") or sections.get("sec19b_paper2_name") or "").strip()
    sec181_p2_date_val = parse_display_date(sections.get("sec181_paper2_date") or sections.get("sec19b_paper2_date"))

    if existing_village_data is not None:
        village_data = existing_village_data
        village_data.user = user
        is_manual = is_village_data_manually_filled(village_data, notification=notification)
        if not is_manual:
            if purpose:
                village_data.land_acquisition_purpose = purpose
            if sec1_adesh:
                village_data.sec1_adesh_kramank = sec1_adesh
            if sec1_date_val:
                village_data.sec1_date = sec1_date_val
            if sec1_admin_approvals:
                village_data.sec1_admin_approvals = sec1_admin_approvals
            if notified_area_rows:
                village_data.notified_area_rows = notified_area_rows
            if total_area:
                village_data.sec1_total_notified_area = total_area
            if sec152_no:
                village_data.sec2_adhisuchana_kramank = sec152_no
            if sec152_date_val:
                village_data.sec2_date = sec152_date_val
            if sec152_p1_name:
                village_data.sec2_paper1_name = sec152_p1_name
            if sec152_p1_date_val:
                village_data.sec2_paper1_date = sec152_p1_date_val
            if sec152_p2_name:
                village_data.sec2_paper2_name = sec152_p2_name
            if sec152_p2_date_val:
                village_data.sec2_paper2_date = sec152_p2_date_val
            if sec3_upvibhag:
                village_data.sec3_upvibhag_name = sec3_upvibhag
            if sec3_rows_v:
                village_data.sec3_rows = sec3_rows_v
            if sec154_pub_no:
                village_data.sec3_adhisuchana_kramank = sec154_pub_no
            if sec154_pub_date:
                village_data.sec3_date = sec154_pub_date
            if sec5_no:
                village_data.sec5_prastaav_kramank = sec5_no
            if sec5_date_val:
                village_data.sec5_date = sec5_date_val
            if sec6_reg:
                village_data.sec6_register_number = sec6_reg
            if sec6_date_val:
                village_data.sec6_date = sec6_date_val
            if sec6_rows_v:
                village_data.sec6_rows = sec6_rows_v
            if sec7_details:
                village_data.sec7_aakshep_details = sec7_details
            if sec181_p1_name:
                village_data.sec9_paper1_name = sec181_p1_name
            if sec181_p1_date_val:
                village_data.sec9_paper1_date = sec181_p1_date_val
            if sec181_p2_name:
                village_data.sec9_paper2_name = sec181_p2_name
            if sec181_p2_date_val:
                village_data.sec9_paper2_date = sec181_p2_date_val
            village_data.save()
    else:
        village_data = VillageData.objects.create(
            user=user,
            district=district,
            taluka=taluka,
            village=village,
            land_acquisition_purpose=purpose,
            sec1_adesh_kramank=sec1_adesh,
            sec1_date=sec1_date_val,
            sec1_admin_approvals=sec1_admin_approvals,
            notified_area_rows=notified_area_rows,
            sec1_total_notified_area=total_area,
            sec2_adhisuchana_kramank=sec152_no,
            sec2_date=sec152_date_val,
            sec2_paper1_name=sec152_p1_name,
            sec2_paper1_date=sec152_p1_date_val,
            sec2_paper2_name=sec152_p2_name,
            sec2_paper2_date=sec152_p2_date_val,
            sec3_upvibhag_name=sec3_upvibhag,
            sec3_rows=sec3_rows_v,
            sec3_adhisuchana_kramank=sec154_pub_no,
            sec3_date=sec154_pub_date,
            sec5_prastaav_kramank=sec5_no,
            sec5_date=sec5_date_val,
            sec6_register_number=sec6_reg,
            sec6_date=sec6_date_val,
            sec6_rows=sec6_rows_v,
            sec7_aakshep_details=sec7_details,
            sec9_paper1_name=sec181_p1_name,
            sec9_paper1_date=sec181_p1_date_val,
            sec9_paper2_name=sec181_p2_name,
            sec9_paper2_date=sec181_p2_date_val,
        )

    # 4. Create/Update VillageData32_2Row (Sec 4 - कलम १५(२) / कलम ३२(२) प्राथमिक अधिसूचना)
    row_15_2 = village_data.sec4_rows.first()
    if not row_15_2:
        row_15_2 = VillageData32_2Row.objects.create(
            village_data=village_data,
            adhisuchana_kramank=sec152_no,
            adhisuchana_date=sec152_date_val,
            paper1_name=sec152_p1_name,
            paper1_date=sec152_p1_date_val,
            paper2_name=sec152_p2_name,
            paper2_date=sec152_p2_date_val,
        )
    else:
        row_15_2.adhisuchana_kramank = sec152_no
        row_15_2.adhisuchana_date = sec152_date_val
        row_15_2.paper1_name = sec152_p1_name
        row_15_2.paper1_date = sec152_p1_date_val
        row_15_2.paper2_name = sec152_p2_name
        row_15_2.paper2_date = sec152_p2_date_val
        row_15_2.save()

    # 8. Create/Update VillageData32_1Row (Sec 8 - कलम १८(१) / कलम ३२(१) अंतिम अधिसूचना)
    row_18_1 = village_data.sec8_rows.first()
    if not row_18_1:
        row_18_1 = VillageData32_1Row.objects.create(
            village_data=village_data,
            adhisuchana_kramank=sec181_no,
            adhisuchana_date=sec181_date_val,
            paper1_name=sec181_p1_name,
            paper1_date=sec181_p1_date_val,
            paper2_name=sec181_p2_name,
            paper2_date=sec181_p2_date_val,
        )
    else:
        if sec181_no:
            row_18_1.adhisuchana_kramank = sec181_no
        if sec181_date_val:
            row_18_1.adhisuchana_date = sec181_date_val
        if sec181_p1_name:
            row_18_1.paper1_name = sec181_p1_name
        if sec181_p1_date_val:
            row_18_1.paper1_date = sec181_p1_date_val
        if sec181_p2_name:
            row_18_1.paper2_name = sec181_p2_name
        if sec181_p2_date_val:
            row_18_1.paper2_date = sec181_p2_date_val
        row_18_1.save()

    # 9. Copy files from NotificationFile to VillageDataFile / child file models
    _copy_notification_files(notification, village_data, row_15_2, row_18_1)

    logger.info(
        f"[Notification Sync] Successfully synced VillageData record (ID: {village_data.id}) "
        f"for village '{village}'."
    )
    return village_data


def _copy_notification_files(notification, village_data, row_15_2=None, row_18_1=None):
    slot_mapping = {
        "land_plan_file": ["sec1_files", "sec1_admin_row_0"],
        "land_autocad_file": ["sec1_files", "sec1_admin_row_0"],
        "area_excel_file": ["sec1_files", "sec1_admin_row_0"],
        "sec3_file": ["sec2_files", "sec1_files", "sec1_admin_row_0"],
        "sec154_file": ["sec3_row_0", "sec1_files", "sec1_admin_row_0"],
        "sec154_notif_file": ["sec5_files"],
        "joint_survey_parishisht16": ["sec6_parishisht16_files", "sec6_row_0_parishisht16"],
        "joint_survey_saksh_naksha": ["sec6_nakasha_files", "sec6_row_0_nakasha"],
        "joint_survey_sanyukta_naksha": ["sec6_nakasha_files", "sec6_row_0_nakasha"],
        "joint_survey_autocad": ["sec6_nakasha_files", "sec6_row_0_nakasha"],
        "shuddhipatrak_file": ["sec8_shuddhipatrak_files"],
        "sec152_file": ["sec2_files", "sec4_row_0_main"],
        "sec152_paper1_file": ["sec2_paper1_files", "sec4_row_0_paper1"],
        "sec152_paper2_file": ["sec2_paper2_files", "sec4_row_0_paper2"],
        "sec181_file": ["sec8_row_0_main", "sec9_files"],
        "sec181_paper1_file": ["sec8_row_0_paper1", "sec9_paper1_files"],
        "sec181_paper2_file": ["sec8_row_0_paper2", "sec9_paper2_files"],
    }

    for file_rec in notification.files.all():
        if not file_rec.file:
            continue
        try:
            field_key = file_rec.field_key
            original_filename = file_rec.original_name or file_rec.file.name.rsplit("/", 1)[-1]

            file_rec.file.open("rb")
            file_content = file_rec.file.read()
            file_rec.file.close()

            if field_key in slot_mapping:
                target_keys = slot_mapping[field_key]
                for tk in target_keys:
                    if not VillageDataFile.objects.filter(village_data=village_data, field_key=tk, file__endswith=original_filename).exists():
                        vdf = VillageDataFile(village_data=village_data, field_key=tk)
                        vdf.file.save(original_filename, ContentFile(file_content), save=True)

            if field_key.startswith("sec152_") or field_key == "sec3_file":
                sub_key = "main"
                if "paper1" in field_key:
                    sub_key = "paper1"
                elif "paper2" in field_key:
                    sub_key = "paper2"
                if row_15_2 and not VillageData32_2RowFile.objects.filter(row_15_2=row_15_2, field_key=sub_key, file__endswith=original_filename).exists():
                    rf = VillageData32_2RowFile(row_15_2=row_15_2, field_key=sub_key)
                    rf.file.save(original_filename, ContentFile(file_content), save=True)

            if field_key.startswith("sec181_"):
                sub_key = "main"
                if "paper1" in field_key:
                    sub_key = "paper1"
                elif "paper2" in field_key:
                    sub_key = "paper2"
                if row_18_1 and not VillageData32_1RowFile.objects.filter(row_18_1=row_18_1, field_key=sub_key, file__endswith=original_filename).exists():
                    rf = VillageData32_1RowFile(row_18_1=row_18_1, field_key=sub_key)
                    rf.file.save(original_filename, ContentFile(file_content), save=True)

        except Exception as e:
            logger.error(f"[Notification Sync] Error copying file {file_rec}: {e}")
