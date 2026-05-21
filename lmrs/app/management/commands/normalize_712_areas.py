import re

from django.core.management.base import BaseCommand
from django.db import transaction

from lmrs.app.models import LandRecord712


def _parse_area_to_sqm(value):
    text = str(value or "").strip()
    if not text or text in ("-", "None", "none", "NULL", "null"):
        return 0

    if any(sep in text for sep in (".", "-", "/")):
        parts = [p for p in re.split(r"[.\-\/\s]+", text) if p is not None]
        nums = []
        for part in parts:
            raw = re.sub(r"[^0-9]", "", str(part))
            nums.append(int(raw) if raw.isdigit() else 0)
        if len(nums) >= 3:
            h, a, s = nums[0], nums[1], nums[2]
            return (h * 10000) + (a * 100) + s
        if len(nums) == 2:
            h, a = nums[0], nums[1]
            return (h * 10000) + (a * 100)

    return 0


def _normalize_712_area(value):
    raw = str(value or "").strip()
    if not raw or raw in ("-", "None", "none", "NULL", "null"):
        return ""

    text = re.sub(r"[^0-9.\-\/\s]", " ", raw)
    parts = [p for p in re.split(r"[.\-\/\s]+", text) if p]
    if not parts:
        return ""

    nums = [int(re.sub(r"\D", "", p) or "0") for p in parts[:3]]
    if len(nums) == 1:
        # Can't infer whether it's H, AA, or something else. Keep as-is.
        return raw
    if len(nums) == 2:
        hectare, aar = nums
        sqm = 0
    else:
        hectare, aar, sqm = nums
    return f"{hectare}.{str(aar).zfill(2)}.{str(sqm).zfill(2)}"


def _should_clear_potkharaba(total_area, jirayit, bagayat, potkharaba):
    total_sqm = _parse_area_to_sqm(total_area)
    pot_sqm = _parse_area_to_sqm(potkharaba)
    jir_bag_sqm = _parse_area_to_sqm(jirayit) + _parse_area_to_sqm(bagayat)

    if total_sqm <= 0 or pot_sqm <= 0:
        return False

    # If total is exactly (jirayit + bagayat), potkharaba must be zero.
    if jir_bag_sqm == total_sqm:
        return True

    # If jirayit/bagayat missing but potkharaba almost equals total, it's likely bogus.
    if jir_bag_sqm == 0:
        ratio = pot_sqm / total_sqm if total_sqm else 0
        return ratio >= 0.9

    return False


class Command(BaseCommand):
    help = "Normalize 7/12 area fields to H.AA.SS format and clear suspicious potkharaba values."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without saving.")
        parser.add_argument("--limit", type=int, default=0, help="Limit number of LandRecord712 rows to process.")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        limit = int(options["limit"] or 0)

        qs = LandRecord712.objects.all().prefetch_related("farmers").order_by("id")
        if limit > 0:
            qs = qs[:limit]

        changed_records = 0
        changed_farmers = 0

        with transaction.atomic():
            for rec in qs:
                before = {
                    "jirayit": rec.jirayit or "",
                    "bagayat": rec.bagayat or "",
                    "potkharaba": rec.potkharaba or "",
                    "total_area": rec.total_area or "",
                    "khata_area": rec.khata_area or "",
                }

                rec.jirayit = _normalize_712_area(rec.jirayit)
                rec.bagayat = _normalize_712_area(rec.bagayat)
                rec.total_area = _normalize_712_area(rec.total_area)
                rec.khata_area = _normalize_712_area(rec.khata_area)
                rec.potkharaba = _normalize_712_area(rec.potkharaba)

                if _should_clear_potkharaba(rec.total_area, rec.jirayit, rec.bagayat, rec.potkharaba):
                    rec.potkharaba = ""

                after = {
                    "jirayit": rec.jirayit or "",
                    "bagayat": rec.bagayat or "",
                    "potkharaba": rec.potkharaba or "",
                    "total_area": rec.total_area or "",
                    "khata_area": rec.khata_area or "",
                }

                rec_changed = before != after
                if rec_changed:
                    changed_records += 1
                    if not dry_run:
                        rec.save(update_fields=["jirayit", "bagayat", "potkharaba", "total_area", "khata_area"])

                for farmer in rec.farmers.all():
                    f_before_total = farmer.total_area or ""
                    f_before_pot = farmer.potkharaba or ""
                    farmer.total_area = _normalize_712_area(farmer.total_area)
                    farmer.potkharaba = _normalize_712_area(farmer.potkharaba)
                    # apply same suspicious clear rule at farmer-level when totals look broken
                    if _should_clear_potkharaba(farmer.total_area, "", "", farmer.potkharaba):
                        farmer.potkharaba = ""

                    if f_before_total != (farmer.total_area or "") or f_before_pot != (farmer.potkharaba or ""):
                        changed_farmers += 1
                        if not dry_run:
                            farmer.save(update_fields=["total_area", "potkharaba"])

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Changed LandRecord712: {changed_records}, Farmers: {changed_farmers}, dry_run={dry_run}"
            )
        )

