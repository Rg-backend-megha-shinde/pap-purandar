"""
7/12 API (ROR SOAP) integration.

Talks to the Maharashtra ROR "Record of Rights" SOAP web service to resolve
division/district/taluka/village codes, list survey numbers under a gut, and
pull 7/12 owner rows.

Credentials come from the environment (see ROR_* keys in .env):

    ROR_SOAP_URL, ROR_WEBSERVICE_ID, ROR_WSUSER_ID, ROR_PASSWORD,
    ROR_FORMAT_CODE, ROR_SOAP_TIMEOUT_SECONDS, ROR_DIV_CODES,
    ROR_ALLOWED_DIV_CODES

ROR_ALLOWED_DIV_CODES limits which divisions the dropdowns and the sync work
with; it defaults to ROR_DEFAULT_DIV_CODE ("01" = पुणे विभाग), so the project
only ever pulls Pune division masters. Set it to "" to allow all divisions.

Fetching already-saved rows out of the local DB works without any of these;
only "Sync SOAP to DB" needs ROR_PASSWORD.
"""

import json
import os
import re
from difflib import SequenceMatcher
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape as xml_escape

import requests
from django.conf import settings
from django.db import connection
from django.db.models import Q

from .models import RorDistrict, RorDivision, RorSurveyNumber, RorTaluka, RorVillage

ROR_SOAP_URL = os.getenv("ROR_SOAP_URL", "http://115.124.110.79/WS_ROR_Bank/WebService_ROR.asmx")
ROR_TEMPURI = "http://tempuri.org/"


def clean_text(value):
    return str(value or "").strip()


DEVANAGARI_TO_ASCII_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def ror_numeric_pin(value):
    """
    Reduce a project gut label to the numeric pin ROR expects.

    prj_gut_bd.gut_no stores display text ("गट नं. 13", "ला. गट नं. 60",
    "ग.नं.315", "गट नं.12 पै."), but GetSurveyNoByNumericPin only accepts the
    bare number. Labels with no digits at all ("रस्ता", "ओढा") have no pin.
    """
    numbers = re.findall(r"\d+", clean_text(value).translate(DEVANAGARI_TO_ASCII_DIGITS))
    return numbers[0] if numbers else ""


# ---------------------------------------------------------------------------
# SOAP plumbing
# ---------------------------------------------------------------------------

def _ror_setting(name, default=""):
    return clean_text(getattr(settings, name, "") or os.getenv(name, default))


def _ror_base_params():
    password = _ror_setting("ROR_PASSWORD")
    if not password:
        raise ValueError(
            "ROR_PASSWORD is not configured. Add ROR_PASSWORD in .env/server environment "
            "and restart the Django server. Fetch from saved DB works without it; "
            "SOAP sync needs it."
        )
    return {
        "webservice_id": _ror_setting("ROR_WEBSERVICE_ID", "45"),
        "wsuser_id": _ror_setting("ROR_WSUSER_ID", "MSRDC_Admin"),
        "password": password,
        "Format_code": _ror_setting("ROR_FORMAT_CODE", "JSON"),
    }


def _ror_envelope(operation, params):
    lines = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        'xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">',
        "  <soap:Body>",
        f'    <{operation} xmlns="{ROR_TEMPURI}">',
    ]
    for key, value in params.items():
        lines.append(f"      <{key}>{xml_escape(clean_text(value))}</{key}>")
    lines.extend([f"    </{operation}>", "  </soap:Body>", "</soap:Envelope>"])
    return "\n".join(lines)


def _ror_extract_json(xml_text):
    root = ET.fromstring(xml_text)
    result_text = ""
    for element in root.iter():
        if element.tag.split("}")[-1].endswith("Result"):
            result_text = element.text or ""
            break
    result_text = clean_text(result_text)
    if not result_text:
        return []
    if not result_text.startswith(("[", "{")):
        # "No such survey/gut" comes back as plain Marathi text, not JSON.
        if "उपलब्ध नाही" in result_text:
            raise ValueError(
                "या गट/सर्व्हे क्रमांकाची माहिती ROR मध्ये उपलब्ध नाही अथवा बंद केली आहे."
            )
        preview = result_text[:180]
        raise ValueError(f"ROR API did not return JSON. Response starts with: {preview}")
    # The service occasionally emits trailing commas, so retry on a cleaned copy.
    candidates = [
        result_text,
        re.sub(r",\s*([}\]])", r"\1", result_text),
    ]
    if result_text.startswith("{") and result_text.endswith(","):
        candidates.append(result_text[:-1] + "}")
    if result_text.startswith("[") and result_text.endswith(","):
        candidates.append(result_text[:-1] + "]")
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    raise ValueError(f"ROR API returned invalid JSON. Response starts with: {result_text[:180]}")


def _ror_call(operation, params):
    body = _ror_envelope(operation, params)
    response = requests.post(
        _ror_setting("ROR_SOAP_URL", ROR_SOAP_URL),
        data=body.encode("utf-8"),
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{ROR_TEMPURI}{operation}"',
        },
        timeout=int(_ror_setting("ROR_SOAP_TIMEOUT_SECONDS", "30") or 30),
    )
    response.raise_for_status()
    return _ror_extract_json(response.text)


def _ror_rows(payload):
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = []
        for value in payload.values():
            if isinstance(value, list):
                rows.extend(row for row in value if isinstance(row, dict))
        return rows
    return []


def _ror_first(row, keys):
    for key in keys:
        value = clean_text(row.get(key))
        if value:
            return value
    return ""


# ---------------------------------------------------------------------------
# Name matching
# ---------------------------------------------------------------------------

ROR_LOCATION_TRANSLITERATION = str.maketrans({
    "ळ": "ल",
    "ऱ": "र",
})

ROR_LOCATION_ALIAS_MAP = {
    "ahilyanagar": ["अहिल्यानगर", "ahmednagar", "अहमदनगर"],
    "ahmednagar": ["अहिल्यानगर", "अहमदनगर", "ahilyanagar"],
    "bid": ["बीड", "beed"],
    "beed": ["बीड", "bid"],
    "dharashiv": ["धाराशिव", "osmanabad", "उस्मानाबाद"],
    "osmanabad": ["धाराशिव", "उस्मानाबाद", "dharashiv"],
    "latur": ["लातूर"],
    "pune": ["पुणे"],
    "raigad": ["रायगड"],
    "thane": ["ठाणे"],
    "akole": ["अकोले"],
    "alibag": ["अलिबाग"],
    "ambajogai": ["अंबाजोगाई", "अंबेजोगाई"],
    "ambegaon": ["आंबेगाव", "अंबेगाव"],
    "ambernath": ["अंबरनाथ"],
    "ashti": ["आष्टी", "अष्टी"],
    "ausa": ["औसा"],
    "baramati": ["बारामती"],
    "bhiwandi": ["भिवंडी"],
    "bhor": ["भोर"],
    "bhum": ["भूम"],
    "chakur": ["चाकूर"],
    "daund": ["दौंड"],
    "deoni": ["देवणी"],
    "dharur": ["धारूर", "धारुर"],
    "georai": ["गेवराई"],
    "haveli": ["हवेली"],
    "indapur": ["इंदापूर", "इंदापुर"],
    "jalkot": ["जळकोट"],
    "jamkhed": ["जामखेड"],
    "junnar": ["जुन्नर"],
    "kaij": ["केज"],
    "kalamb": ["कळंब", "कलंब"],
    "kalyan": ["कल्याण"],
    "karjat": ["कर्जत"],
    "khalapur": ["खालापूर", "खालापुर"],
    "khed": ["खेड"],
    "kopargaon": ["कोपरगाव"],
    "lohara": ["लोहारा"],
    "mahad": ["महाड"],
    "majalgaon": ["माजलगाव"],
    "mangaon": ["माणगाव", "मांगाव"],
    "mawal": ["मावळ", "मावल"],
    "mhasla": ["म्हसळा", "म्हसला"],
    "mulshi": ["मुळशी", "मुलशी"],
    "murbad": ["मुरबाड"],
    "murud": ["मुरुड"],
    "nevasa": ["नेवासा"],
    "nilanga": ["निलंगा"],
    "omarga": ["उमरगा", "ओमरगा"],
    "panvel": ["पनवेल"],
    "paranda": ["परंडा"],
    "parli": ["परळी", "परली"],
    "patoda": ["पाटोदा"],
    "pathardi": ["पाथर्डी"],
    "pen": ["पेण", "पेन"],
    "purandar": ["पुरंदर", "purandar", "purandhar"],
    "purandhar": ["पुरंदर", "purandar", "purandhar"],
    "rahata": ["राहाता"],
    "rahuri": ["राहुरी"],
    "renapur": ["रेणापूर", "रेणापुर"],
    "roha": ["रोहा"],
    "sangamner": ["संगमनेर"],
    "shahapur": ["शहापूर", "शहापुर"],
    "shevgaon": ["शेवगाव"],
    "shirur": ["शिरूर", "शिरुर"],
    "shirurkasar": ["शिरूर कासार", "शिरुर कासार", "शिरूर (कासार)", "शिरुर (कासार)"],
    "shiruranantpal": ["शिरूर अनंतपाळ", "शिरुर अनंतपाळ", "शिरूर अनंतपाल"],
    "shrigonda": ["श्रीगोंदा"],
    "shrirampur": ["श्रीरामपूर", "श्रीरामपुर"],
    "shrivardhan": ["श्रीवर्धन"],
    "sudhagad": ["सुधागड"],
    "tala": ["तळा", "तला"],
    "tuljapur": ["तुळजापूर", "तुलजापूर"],
    "udgir": ["उदगीर"],
    "ulhasnagar": ["उल्हासनगर"],
    "uran": ["उरण"],
    "velhe": ["वेल्हे"],
    "wadwani": ["वडवणी"],
    "washi": ["वाशी"],
}

ROR_DIVISION_NAMES = {
    "01": "पुणे विभाग",
    "1": "पुणे विभाग",
    "02": "नागपूर विभाग",
    "2": "नागपूर विभाग",
    "03": "नाशिक विभाग",
    "3": "नाशिक विभाग",
    "04": "छत्रपती संभाजीनगर विभाग",
    "4": "छत्रपती संभाजीनगर विभाग",
    "05": "कोकण विभाग",
    "5": "कोकण विभाग",
    "06": "अमरावती विभाग",
    "6": "अमरावती विभाग",
}


def _ror_normalize_div_code(value):
    """ROR sends "01" in some responses and "1" in others; compare on "01"."""
    code = clean_text(value).lstrip("0")
    return code.zfill(2) if code else ""


def ror_allowed_div_codes():
    """Division codes the project works with; empty set means "no limit"."""
    raw = _ror_setting("ROR_ALLOWED_DIV_CODES", _ror_setting("ROR_DEFAULT_DIV_CODE", "01"))
    return {
        code
        for item in raw.split(",")
        if (code := _ror_normalize_div_code(item))
    }


def ror_div_code_allowed(code):
    allowed = ror_allowed_div_codes()
    return not allowed or _ror_normalize_div_code(code) in allowed


def _ror_division_display_name(code="", raw_data=None, current_name=""):
    raw_data = raw_data or {}
    raw_name = _ror_first(raw_data, ["div_desc", "div_name", "division_name", "division_desc", "division"])
    name = clean_text(raw_name or current_name)
    code = clean_text(code)
    canonical = ROR_DIVISION_NAMES.get(code, "")
    if canonical:
        return canonical
    if not name or name == code:
        return name or code
    return name


def _ror_location_key(value):
    text = clean_text(value).translate(str.maketrans("०१२३४५६७८९", "0123456789"))
    text = text.translate(ROR_LOCATION_TRANSLITERATION).casefold()
    return re.sub(r"[\s\W_]+", "", text, flags=re.UNICODE)


def _ror_location_values(value):
    text = clean_text(value)
    if not text:
        return []
    values = [text]
    stripped = re.sub(r"^\d+[_\-\s]+", "", text).strip()
    if stripped and stripped != text:
        values.append(stripped)
    for item in list(values):
        values.extend(ROR_LOCATION_ALIAS_MAP.get(_ror_location_key(item), []))
    keys = {_ror_location_key(item) for item in values if clean_text(item)}
    for alias_key, aliases in ROR_LOCATION_ALIAS_MAP.items():
        alias_keys = {_ror_location_key(alias) for alias in aliases}
        if alias_key in keys or keys.intersection(alias_keys):
            values.append(alias_key)
            values.extend(aliases)
    return _ror_aliases(*values)


def _ror_location_keys(value):
    return {
        key
        for candidate in _ror_location_values(value)
        if (key := _ror_location_key(candidate))
    }


def ror_location_filter_q(field_name, value, allow_contains=False):
    """Build a Q() matching a location column against every known alias."""
    candidates = _ror_location_values(value)
    query = Q()
    for candidate in candidates:
        query |= Q(**{f"{field_name}__iexact": candidate})
        if allow_contains and len(candidate) > 2:
            query |= Q(**{f"{field_name}__icontains": candidate})
    return query or Q(**{f"{field_name}__iexact": clean_text(value)})


def _ror_aliases(*values):
    aliases = []
    seen = set()
    for value in values:
        text = clean_text(value)
        key = text.casefold()
        if text and key not in seen:
            aliases.append(text)
            seen.add(key)
    return aliases


def _ror_cache_alias(obj, alias):
    """Remember the spelling the caller used so the next lookup hits exactly."""
    alias = clean_text(alias)
    if not obj or not alias:
        return
    aliases = _ror_aliases(*(obj.aliases or []), alias)
    if aliases != (obj.aliases or []):
        obj.aliases = aliases
        obj.save(update_fields=["aliases", "updated_at"])


def _ror_best_cached_match(queryset, wanted):
    wanted_keys = _ror_location_keys(wanted)
    if not wanted_keys:
        return None
    best = None
    best_score = 0.0
    for obj in queryset:
        candidates = [obj.name, *(obj.aliases or [])]
        candidate_keys = [_ror_location_key(value) for value in candidates if clean_text(value)]
        if wanted_keys.intersection(candidate_keys):
            return obj
        for candidate_key in candidate_keys:
            if not candidate_key:
                continue
            score = max(SequenceMatcher(None, wanted_key, candidate_key).ratio() for wanted_key in wanted_keys)
            if score > best_score:
                best = obj
                best_score = score
    return best if best_score >= 0.72 else None


def _ror_best_row_match(rows, wanted, name_keys):
    wanted_keys = _ror_location_keys(wanted)
    if not wanted_keys:
        return None
    best_row = None
    best_score = 0.0
    for row in rows:
        for key in name_keys:
            name = _ror_first(row, [key])
            name_key = _ror_location_key(name)
            if not name_key:
                continue
            if name_key in wanted_keys:
                return row
            score = max(SequenceMatcher(None, wanted_key, name_key).ratio() for wanted_key in wanted_keys)
            if score > best_score:
                best_row = row
                best_score = score
    return best_row if best_score >= 0.72 else None


def _ror_close_names(rows, wanted, name_keys, limit=5):
    """Nearest ROR spellings, used to make "not found" errors actionable."""
    wanted_keys = _ror_location_keys(wanted) or {_ror_location_key(wanted)}
    scored = []
    for row in rows:
        name = _ror_first(row, name_keys)
        name_key = _ror_location_key(name)
        if not name_key:
            continue
        scored.append((max(SequenceMatcher(None, wanted_key, name_key).ratio() for wanted_key in wanted_keys), name))
    return [name for _score, name in sorted(scored, reverse=True)[:limit] if name]


# ---------------------------------------------------------------------------
# Master data upserts
# ---------------------------------------------------------------------------

def _ror_upsert_division(row):
    code = _ror_first(row, ["div_code", "division_code", "code"])
    name = _ror_division_display_name(
        code,
        row,
        _ror_first(row, ["div_desc", "div_name", "division_name", "division_desc", "division", "name"]),
    )
    if not code:
        return None
    obj, _created = RorDivision.objects.update_or_create(
        code=code,
        defaults={"name": name, "raw_data": row},
    )
    return obj


def _ror_upsert_districts(rows, div_code="", division_obj=None):
    records = []
    for row in rows:
        code = _ror_first(row, ["dist_code", "district_code", "district_cd", "code"])
        name = _ror_first(row, ["dist_desc", "district_name", "district_desc", "dist_name", "name"])
        if not code or not name:
            continue
        obj, _created = RorDistrict.objects.update_or_create(
            code=code,
            defaults={"division": division_obj, "div_code": div_code, "name": name, "raw_data": row},
        )
        records.append(obj)
    return records


def _ror_upsert_talukas(district_obj, rows):
    records = []
    for row in rows:
        code = _ror_first(row, ["tah_code", "taluka_code", "tal_code", "code"])
        name = _ror_first(row, ["tah_desc", "taluka_name", "taluka_desc", "tal_name", "name"])
        if not code or not name:
            continue
        obj, _created = RorTaluka.objects.update_or_create(
            district=district_obj,
            code=code,
            defaults={"name": name, "raw_data": row},
        )
        records.append(obj)
    return records


def _ror_upsert_villages(taluka_obj, rows):
    records = []
    for row in rows:
        code = _ror_first(row, [
            "ccode", "c_code", "village_code", "village_cd", "vill_code",
            "vil_code", "v_code", "census_code", "lgd_code", "code",
        ])
        name = _ror_first(row, [
            "village_name", "village_desc", "village", "vill_name",
            "vill_desc", "cname", "name",
        ])
        if not code or not name:
            continue
        obj, _created = RorVillage.objects.update_or_create(
            taluka=taluka_obj,
            code=code,
            defaults={"name": name, "raw_data": row},
        )
        records.append(obj)
    return records


def _ror_division_rows(location_base):
    rows = _ror_rows(_ror_call("GetDistricts_Taluka_Village", {
        **location_base,
        "opr": "1",
        "div_code": "",
        "dist_code": "",
        "tah_code": "",
    }))
    if not rows:
        fallback_codes = [
            code.strip()
            for code in _ror_setting("ROR_DIV_CODES", "01,02,03,04,05,06").split(",")
            if code.strip()
        ]
        rows = [{"div_code": code, "div_desc": code} for code in fallback_codes]
    return [
        row for row in rows
        if ror_div_code_allowed(_ror_first(row, ["div_code", "division_code", "code"]))
    ]


def ror_fetch_all_districts(location_base):
    all_rows = []
    for division in _ror_division_rows(location_base):
        div_code = _ror_first(division, ["div_code", "division_code", "code"])
        if not div_code:
            continue
        division_obj = _ror_upsert_division(division)
        rows = _ror_rows(_ror_call("GetDistricts_Taluka_Village", {
            **location_base,
            "opr": "2",
            "div_code": div_code,
            "dist_code": "",
            "tah_code": "",
        }))
        _ror_upsert_districts(rows, div_code=div_code, division_obj=division_obj)
        all_rows.extend(rows)
    return all_rows


def ror_ensure_location_cache(force=False):
    """
    Warm the division/district cache the 7/12 dropdowns read from.
    """
    allowed = ror_allowed_div_codes()
    cached = RorDistrict.objects.all()
    if allowed:
        cached = cached.filter(div_code__in=allowed | {code.lstrip("0") for code in allowed})
    if not force and cached.exists():
        return False, ""
    try:
        base = _ror_base_params()
        location_base = {key: value for key, value in base.items() if key != "Format_code"}
        ror_fetch_all_districts(location_base)
        return True, ""
    except Exception as exc:
        return False, str(exc)


def _ror_survey_cached_villages(district_obj, taluka_obj):
    """Fall back to villages we have only seen via survey-number lookups."""
    district_values = _ror_location_values(getattr(district_obj, "name", "")) + list(getattr(district_obj, "aliases", []) or [])
    taluka_values = _ror_location_values(getattr(taluka_obj, "name", "")) + list(getattr(taluka_obj, "aliases", []) or [])
    district_query = Q()
    for value in _ror_aliases(*district_values):
        district_query |= Q(district__iexact=value)
    taluka_query = Q()
    for value in _ror_aliases(*taluka_values):
        taluka_query |= Q(taluka__iexact=value)
    if not district_query or not taluka_query:
        return []
    names = (
        RorSurveyNumber.objects
        .filter(district_query, taluka_query)
        .exclude(village="")
        .values_list("village", flat=True)
        .distinct()
        .order_by("village")
    )
    return [
        {
            "code": "",
            "value": name,
            "label": name,
            "name": name,
            "aliases": _ror_aliases(*_ror_location_values(name)),
            "taluka_code": taluka_obj.code,
            "taluka_name": taluka_obj.name,
        }
        for name in names
    ]


def _project_village_marathi_names(taluka, village):
    """
    Marathi spellings for a project village.

    The dropdowns send English village names (purandar_airport.prj_village), but
    ROR only knows the Marathi ones, so pull them from village_master before
    falling back to fuzzy matching.
    """
    village = clean_text(village)
    if not village:
        return []

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT vm.village_name_m
                FROM purandar_airport.prj_village d
                JOIN purandar_airport.prj_taluka t ON t.taluka_id = d.taluka_id
                JOIN public.village_master vm ON d.village_id = vm.id
                WHERE UPPER(TRIM(d.village)) = UPPER(TRIM(%s))
                  AND (%s = '' OR UPPER(TRIM(t.taluka)) = UPPER(TRIM(%s)))
                  AND COALESCE(vm.village_name_m, '') <> ''
                """,
                [village, clean_text(taluka), clean_text(taluka)],
            )
            return [clean_text(row[0]) for row in cursor.fetchall() if clean_text(row[0])]
    except Exception:
        return []


def _ror_village_candidates(taluka, village):
    marathi_names = _project_village_marathi_names(taluka, village)
    if not marathi_names:
        marathi_names = _project_village_marathi_names("", village)
    return _ror_aliases(village, *marathi_names)


def ror_location_codes(district, taluka, village):
    """
    Resolve project location names to ROR dist_code / tah_code / ccode,
    fetching and caching each level from SOAP only when the cache misses.
    """
    base = _ror_base_params()
    location_base = {key: value for key, value in base.items() if key != "Format_code"}

    district_rows = []
    district_obj = _ror_best_cached_match(RorDistrict.objects.all(), district)
    if not district_obj:
        district_rows = ror_fetch_all_districts(location_base)
        district_obj = _ror_best_cached_match(RorDistrict.objects.all(), district)
        if not district_obj:
            district_match = _ror_best_row_match(
                district_rows, district,
                ["dist_desc", "district_name", "district_desc", "dist_name", "name"],
            )
            if district_match:
                district_code = _ror_first(district_match, ["dist_code", "district_code", "district_cd", "code"])
                district_obj = RorDistrict.objects.filter(code=district_code).first()
    if not district_obj:
        close_names = _ror_close_names(
            district_rows, district,
            ["dist_desc", "district_name", "district_desc", "dist_name", "name"],
        )
        suffix = f" Close ROR names: {', '.join(close_names)}." if close_names else ""
        raise ValueError(f"ROR district code not found for {district}.{suffix}")
    _ror_cache_alias(district_obj, district)
    dist_code = district_obj.code
    div_code = district_obj.div_code
    if not div_code:
        ror_fetch_all_districts(location_base)
        fresh_obj = RorDistrict.objects.filter(code=dist_code).first()
        if fresh_obj:
            district_obj = fresh_obj
            div_code = district_obj.div_code

    taluka_rows = []
    taluka_candidates = _ror_aliases(taluka, *ROR_LOCATION_ALIAS_MAP.get(_ror_location_key(taluka), [])) or [taluka]

    def _match_cached_taluka():
        for candidate in taluka_candidates:
            match = _ror_best_cached_match(district_obj.talukas.all(), candidate)
            if match:
                return match
        return None

    taluka_obj = _match_cached_taluka()
    if not taluka_obj:
        taluka_rows = _ror_rows(_ror_call("GetDistricts_Taluka_Village", {
            **location_base,
            "opr": "3",
            "div_code": div_code,
            "dist_code": dist_code,
            "tah_code": "",
        }))
        _ror_upsert_talukas(district_obj, taluka_rows)
        taluka_obj = _match_cached_taluka()
        if not taluka_obj:
            for candidate in taluka_candidates:
                taluka_match = _ror_best_row_match(
                    taluka_rows, candidate,
                    ["tah_desc", "taluka_name", "taluka_desc", "tal_name", "name"],
                )
                if taluka_match:
                    taluka_code = _ror_first(taluka_match, ["tah_code", "taluka_code", "tal_code", "code"])
                    taluka_obj = district_obj.talukas.filter(code=taluka_code).first()
                    if taluka_obj:
                        break
    if not taluka_obj:
        close_names = _ror_close_names(
            taluka_rows, taluka,
            ["tah_desc", "taluka_name", "taluka_desc", "tal_name", "name"],
        )
        suffix = f" Close ROR names: {', '.join(close_names)}." if close_names else ""
        raise ValueError(f"ROR taluka code not found for {district} / {taluka}.{suffix}")
    _ror_cache_alias(taluka_obj, taluka)
    tah_code = taluka_obj.code

    village_rows = []
    village_candidates = _ror_village_candidates(taluka, village) or [village]
    village_names = ["village_name", "village_desc", "vill_name", "vill_desc", "name"]

    def _match_cached_village():
        for candidate in village_candidates:
            match = _ror_best_cached_match(taluka_obj.villages.all(), candidate)
            if match:
                return match
        return None

    village_obj = _match_cached_village()
    if not village_obj:
        village_rows = _ror_rows(_ror_call("GetDistricts_Taluka_Village", {
            **location_base,
            "opr": "4",
            "div_code": div_code,
            "dist_code": dist_code,
            "tah_code": tah_code,
        }))
        _ror_upsert_villages(taluka_obj, village_rows)
        village_obj = _match_cached_village()
        if not village_obj:
            for candidate in village_candidates:
                village_match = _ror_best_row_match(village_rows, candidate, village_names)
                if not village_match:
                    continue
                village_code = _ror_first(village_match, ["ccode", "c_code", "village_code", "village_cd", "code"])
                village_obj = taluka_obj.villages.filter(code=village_code).first()
                if village_obj:
                    break
    if not village_obj:
        close_names = _ror_close_names(
            village_rows, village,
            ["village_name", "village_desc", "vill_name", "vill_desc", "name"],
        )
        suffix = f" Close ROR names: {', '.join(close_names)}." if close_names else ""
        raise ValueError(f"ROR village ccode not found for {district} / {taluka} / {village}.{suffix}")
    _ror_cache_alias(village_obj, village)

    return {
        "district": district_obj.name,
        "taluka": taluka_obj.name,
        "village": village_obj.name,
        "div_code": div_code,
        "dist_code": dist_code,
        "tah_code": tah_code,
        "ccode": village_obj.code,
    }


# ---------------------------------------------------------------------------
# Survey numbers
# ---------------------------------------------------------------------------

def _ror_survey_number_from_row(gut_number, row):
    base = clean_text(row.get("pin") or row.get("survey_no") or row.get("surveyno") or gut_number)
    parts = [base]
    for index in range(1, 9):
        value = clean_text(row.get(f"pin{index}"))
        if value:
            parts.append(value)
    return "/".join(part for part in parts if part)


def _ror_pin_params_from_parts(parts):
    return {
        f"pin{index}": part
        for index, part in enumerate(parts, start=1)
        if clean_text(part)
    }


def _ror_pin_params_from_survey_number(value, fallback_gut=""):
    text = clean_text(value)
    parts = [clean_text(part) for part in re.split(r"[\\/]+", text) if clean_text(part)]
    gut = clean_text(fallback_gut)
    if not parts:
        return gut, {}
    if gut and parts[0] == gut:
        return gut, _ror_pin_params_from_parts(parts[1:])
    if gut:
        return gut, _ror_pin_params_from_parts(parts)
    return parts[0], _ror_pin_params_from_parts(parts[1:])


def _ror_pin_params_from_survey_row(survey_row):
    return {
        f"pin{index}": value
        for index in range(1, 9)
        if (value := clean_text(survey_row.get(f"pin{index}")))
    }


def _ror_filter_survey_rows(survey_rows, gut_number, survey_number):
    selected = clean_text(survey_number)
    if not selected:
        return survey_rows
    selected_key = selected.casefold()
    filtered = [
        row for row in survey_rows
        if _ror_survey_number_from_row(gut_number, row).casefold() == selected_key
    ]
    if filtered:
        return filtered
    _selected_gut, pin_params = _ror_pin_params_from_survey_number(selected, gut_number)
    return [{"pin": gut_number, "survey_no": selected, **pin_params}]


def split_ror_survey_no(value, fallback_gut=""):
    """Split "259/1/2" into ("259", "1/2")."""
    text = clean_text(value)
    parts = [part for part in re.split(r"[\\/]+", text) if clean_text(part)]
    if len(parts) >= 2:
        return parts[0], "/".join(parts[1:])
    return clean_text(fallback_gut or text), ""


def _ror_survey_cache_rows(district, taluka, village, gut_number):
    return list(
        RorSurveyNumber.objects
        .filter(
            district__iexact=district,
            taluka__iexact=taluka,
            village__iexact=village,
            gut_number__iexact=gut_number,
        )
        .order_by("survey_number")
    )


def _ror_survey_options_from_cache(rows):
    return [
        {
            "value": row.survey_number,
            "label": row.survey_number,
            "hissa_number": row.hissa_number,
        }
        for row in rows
    ]


def ror_fetch_survey_numbers(district, taluka, village, gut_number):
    """Return (options, from_cache) for the Survey Number dropdown."""
    cached_rows = _ror_survey_cache_rows(district, taluka, village, gut_number)
    if cached_rows:
        return _ror_survey_options_from_cache(cached_rows), True

    gut_pin = ror_numeric_pin(gut_number)
    if not gut_pin:
        raise ValueError(
            f"गट क्रमांक \"{clean_text(gut_number)}\" मध्ये अंक नाही, त्यामुळे ROR कडून "
            "सर्व्हे क्रमांक मिळू शकत नाहीत."
        )

    codes = ror_location_codes(district, taluka, village)
    base = _ror_base_params()
    common = {
        **base,
        "dist_code": codes["dist_code"],
        "tah_code": codes["tah_code"],
        "ccode": codes["ccode"],
        "pin": gut_pin,
    }
    survey_rows = _ror_rows(_ror_call("GetSurveyNoByNumericPin", common))
    objects = []
    seen = set()
    for row in survey_rows:
        survey_number = _ror_survey_number_from_row(gut_pin, row)
        if not survey_number or survey_number in seen:
            continue
        seen.add(survey_number)
        _survey_gut, hissa_number = split_ror_survey_no(survey_number, gut_pin)
        objects.append(
            RorSurveyNumber(
                district=district,
                taluka=taluka,
                village=village,
                gut_number=gut_number,
                survey_number=survey_number,
                hissa_number=hissa_number,
                raw_data=row,
            )
        )
    if objects:
        RorSurveyNumber.objects.bulk_create(objects, ignore_conflicts=True, batch_size=200)
    cached_rows = _ror_survey_cache_rows(district, taluka, village, gut_number)
    return _ror_survey_options_from_cache(cached_rows), False


# ---------------------------------------------------------------------------
# 7/12 preview
# ---------------------------------------------------------------------------

def _format_ror_area(value, default="0"):
    """ROR sends areas as H.AASS (e.g. 1.6500); store them as H.AA.SS."""
    text = clean_text(value)
    if not text:
        return default
    match = re.match(r"^(\d+)\.(\d{4})$", text)
    if match:
        return f"{match.group(1)}.{match.group(2)[:2]}.{match.group(2)[2:]}"
    return text


def _ror_normalize_712_rows(district, taluka, village, gut_number, survey_rows, owner_rows):
    rows = []
    owner_like_rows = [
        row for row in owner_rows
        if clean_text(row.get("owner") or row.get("holder_name") or row.get("farmer_name") or row.get("khata_no"))
    ]
    source_rows = owner_like_rows or survey_rows or [{"pin": gut_number}]
    for source in source_rows:
        survey_no = _ror_first(source, ["survey_no", "surveyno", "pin"]) or gut_number
        base_gut, hissa = split_ror_survey_no(survey_no, gut_number)
        if not hissa:
            hissa = _ror_first(source, ["hissa_number", "pin1"])
        rows.append({
            "district": _ror_first(source, ["district_name"]) or district,
            "taluka": _ror_first(source, ["taluka_name"]) or taluka,
            "village": _ror_first(source, ["village_name"]) or village,
            "gut_number": base_gut,
            "survey_number": survey_no,
            "hissa_number": hissa,
            "khata_number": _ror_first(source, ["khata_no", "khata_number"]),
            "khata_area": _format_ror_area(_ror_first(source, ["khata_area", "total_area_h"])),
            "jirayit": _format_ror_area(_ror_first(source, ["jirayit", "jirayat", "jirayat_area_h"]), "0"),
            "bagayat": _format_ror_area(_ror_first(source, ["bagayat", "bagayat_area_h"]), "0"),
            "potkharaba": _format_ror_area(_ror_first(source, ["potkharaba", "potkharaba_a"]), "0"),
            "total_area": _format_ror_area(_ror_first(source, ["total_area_h", "total_area"])),
            "aakarni": _ror_first(source, ["aakarni", "assessment"]) or "0",
            "aakar": _ror_first(source, ["aakar"]) or "0",
            "holder_name": _ror_first(source, ["owner", "holder_name", "farmer_name"]),
            "kul_khand_other_rights": _ror_first(source, ["kul_khand_other_rights", "other_rights"]),
        })
    return rows


def ror_fetch_712_preview(district, taluka, village, gut_number, survey_number=""):
    """Pull survey + owner rows from SOAP and normalise them into 7/12 rows."""
    if not clean_text(gut_number):
        raise ValueError("Please select a valid gut number.")
    gut_pin = ror_numeric_pin(gut_number)
    if not gut_pin:
        raise ValueError(
            f"गट क्रमांक \"{clean_text(gut_number)}\" मध्ये अंक नाही, त्यामुळे ROR कडून "
            "७/१२ माहिती मिळू शकत नाही."
        )
    codes = ror_location_codes(district, taluka, village)
    base = _ror_base_params()
    common = {
        **base,
        "dist_code": codes["dist_code"],
        "tah_code": codes["tah_code"],
        "ccode": codes["ccode"],
    }
    survey_rows = _ror_rows(_ror_call("GetSurveyNoByNumericPin", {**common, "pin": gut_pin}))
    if not survey_rows:
        survey_rows = [{"pin": gut_pin}]

    owner_rows = []
    warnings = []
    _selected_gut, requested_pin_params = _ror_pin_params_from_survey_number(survey_number, gut_pin)
    preview_survey_rows = _ror_filter_survey_rows(survey_rows, gut_pin, survey_number)
    if requested_pin_params:
        try:
            owner_rows.extend(_ror_rows(_ror_call(
                "GetLandDetailsBySurveyNoNew",
                {**common, "pin": gut_pin, **requested_pin_params},
            )))
        except Exception as exc:
            warnings.append(f"Owner endpoint did not return data: {exc}")
    else:
        for survey_row in survey_rows:
            try:
                params = {**common, "pin": gut_pin, **_ror_pin_params_from_survey_row(survey_row)}
                owner_rows.extend(_ror_rows(_ror_call("GetLandDetailsBySurveyNoNew", params)))
            except Exception as exc:
                if not warnings:
                    warnings.append(f"Owner endpoint did not return data: {exc}")

    return {
        "rows": _ror_normalize_712_rows(district, taluka, village, gut_pin, preview_survey_rows, owner_rows),
        "codes": codes,
        "survey_rows": preview_survey_rows,
        "owner_rows": owner_rows,
        "warnings": warnings,
    }


ror_base_params = _ror_base_params
ror_normalize_div_code = _ror_normalize_div_code
ror_location_key = _ror_location_key
ror_division_display_name = _ror_division_display_name
ror_location_values = _ror_location_values
ror_aliases = _ror_aliases
