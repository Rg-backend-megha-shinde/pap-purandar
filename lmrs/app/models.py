from django.core.exceptions import SuspiciousFileOperation
from django.db import models
from django.contrib.auth.models import User
from django.utils.text import get_valid_filename


class ActiveUserSession(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="active_session",
    )
    session_key = models.CharField(max_length=40, unique=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} -> {self.session_key}"


# =========================================================
# 🔹 Inspection Tool
# =========================================================

class ToolMaster(models.Model):

    tool_id = models.AutoField(primary_key=True)

    tool_name = models.CharField(max_length=200)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.tool_name
    

class DocumentMaster(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    tool = models.ForeignKey(ToolMaster, on_delete=models.CASCADE)

    inspection = models.ForeignKey('Inspection', on_delete=models.SET_NULL, null=True, blank=True)
    rr_info = models.ForeignKey('ReadyReckonerInfo',on_delete=models.SET_NULL,null=True,blank=True,related_name="documents")
    land_record = models.ForeignKey('LandRecord712', on_delete=models.SET_NULL, null=True, blank=True)
    asset = models.ForeignKey('Asset', on_delete=models.SET_NULL, null=True, blank=True)
    entry = models.ForeignKey('Entry', on_delete=models.SET_NULL, null=True, blank=True, related_name="documents")
    document_tool_record = models.ForeignKey('Document', on_delete=models.SET_NULL, null=True, blank=True)

    # ⭐ ADD THIS
    DOCUMENT_TYPE_CHOICES = [
        ('general', 'General Document'),
        ('court', 'Court Matter Document'),
    ]

    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES,
        default='general'
    )

    MATTER_TYPE_CHOICES = [
        ('arbitration', 'Arbitration'),
        ('civil_dispute', 'Civil Dispute'),
    ]

    matter_type = models.CharField(
        max_length=20,
        choices=MATTER_TYPE_CHOICES,
        null=True,
        blank=True
    )

    district = models.CharField(max_length=100, null=True, blank=True)
    taluka = models.CharField(max_length=100, null=True, blank=True)
    village = models.CharField(max_length=150, null=True, blank=True)
    gut_number = models.CharField(max_length=50, null=True, blank=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)
    


class DocumentAttachment(models.Model):

    document_master = models.ForeignKey(
        DocumentMaster,
        on_delete=models.CASCADE,
        related_name="attachments"
    )

    file = models.FileField(
        upload_to='documents/files/',
        max_length=1000
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document_master.tool.tool_name}"

    @property
    def safe_file_size(self):
        if not self.file:
            return 0
        try:
            return self.file.size
        except (FileNotFoundError, OSError, ValueError, SuspiciousFileOperation):
            return 0

    



class Inspection(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="inspections"
    )

    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=100)
    gut_number = models.CharField(max_length=50)
    inspection_asset_type = models.CharField(max_length=100, blank=True, null=True)

    officer = models.CharField(max_length=200)
    date = models.DateField()
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    remark = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} - {self.gut_number}"
    
    def get_documents(self):
        """Get all documents associated with this inspection"""
        return DocumentMaster.objects.filter(inspection=self)
    
    def get_total_attachment_count(self):
        """Get total count of all attachments across all document masters"""
        from django.db.models import Count, Sum
        return DocumentMaster.objects.filter(inspection=self).annotate(
            attachment_count=Count('attachments')
        ).aggregate(total=Sum('attachment_count'))['total'] or 0


class AssetDetail(models.Model):
    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="details"
    )

    plot = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=100, blank=True)
    asset_parameter = models.JSONField(default=dict, blank=True)
    valuation = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.name or "Asset Detail"


# =========================================================
# 🔹 Ready Reckoner Rate Tool
# =========================================================

class ReadyReckonerInfo(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="rr_records"
    )

    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=100)

    year = models.CharField(max_length=20, default='2024-2025')

    # 👉 Parent (ONE)
    assessment_type = models.CharField(max_length=200)

    UNIT_CHOICES = [
        ('हेक्टर', 'हेक्टर'),
        ('प्रति चौरस मीटर', 'प्रति चौरस मीटर'),
    ]
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} | {self.assessment_type}"

    def get_rates(self):
        return self.rates.all()

    def get_documents(self):
        """Get all documents associated with this ready reckoner record"""
        return DocumentMaster.objects.filter(rr_info=self)


class ReadyReckonerRate(models.Model):
    # 👉 Child (MANY)
    rr = models.ForeignKey(
        ReadyReckonerInfo,
        on_delete=models.CASCADE,
        related_name="rates"
    )

    shighrasiddha_vibhag = models.TextField(
        null=True,
        blank=True,
        verbose_name='शिघ्रसिध्द गणकातील विभाग'
    )

    VILLAGE_TYPE_CHOICES = [
        ('gramin', 'ग्रामीण'),
        ('prabhav', 'प्रभाव'),
    ]
    village_type = models.CharField(
        max_length=20,
        choices=VILLAGE_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name='Village Type'
    )

    assessment_range_min = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    assessment_range_max = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    rate = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    def __str__(self):
        return (
            f"{self.rr.assessment_type} | "
            f"{self.assessment_range_min}-{self.assessment_range_max} | ₹{self.rate}"
        )


# =========================================================
# 🔹 7/12 Land Record Tool
# =========================================================

class LandRecord712(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="land_records")
    document_712 = models.FileField(upload_to="land_record_712/", null=True, blank=True)
    original_document_name = models.CharField(max_length=255, null=True, blank=True)

    # Already existing (DO NOT TOUCH)
    district = models.CharField(max_length=100)  # "जिल्हा"
    taluka = models.CharField(max_length=100)    # "तालुका"
    village = models.CharField(max_length=150)   # "गावाचे नाव"
    gut_number = models.CharField(max_length=50, help_text="स_नं_ग_न")  # "स_नं_ग_न"

    # JSON based fields
    puid_ulip_no = models.CharField(max_length=100, null=True, blank=True)  # "PUID_ULIP_No"
    hissa_number = models.CharField(max_length=50, null=True, blank=True)  # "स_नं_ग_न_हिस्सा"
    jirayit = models.CharField(max_length=50, null=True, blank=True)  # "जिरायत"
    bagayat = models.CharField(max_length=50, null=True, blank=True)  # "बागायत"
    potkharaba = models.CharField(max_length=50, null=True, blank=True)  # "पोटखराब"
    total_area = models.CharField(max_length=50, null=True, blank=True)  # "एकूण_क्षेत्र"
    aakarni = models.CharField(max_length=50, null=True, blank=True)  # "आकारणी"
    khata_number = models.CharField(max_length=50, null=True, blank=True)  # "खाता_नं"
    khata_area = models.CharField(max_length=50, null=True, blank=True)  # "खाता_क्षेत्र"
    aakar = models.CharField(max_length=50, null=True, blank=True)  # "आकार"
    holder_name = models.TextField(null=True, blank=True)  # "भोगवटदाराचे_नांव"
    kul_khand_other_rights = models.TextField(null=True, blank=True)  # "कुळ, खंड व इतर अधिकार"
    area_more_than_20guntha = models.CharField(max_length=10, null=True, blank=True)  # "क्षेत्र_20_गुंठे_पेक्षा_जास्त" (Yes/No)
    bagayat_more_than_10guntha = models.CharField(max_length=10, null=True, blank=True)  # "बागायत_10_गुंठे_पेक्षा_जास्त" (Yes/No)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['district'], name='app_landrec_distri_4bc4cd_idx'),
            models.Index(fields=['taluka'], name='app_landrec_taluka_5f3105_idx'),
            models.Index(fields=['village'], name='app_landrec_village_9ddc14_idx'),
            models.Index(fields=['gut_number'], name='app_landrec_gut_num_d2f6f3_idx'),
            models.Index(fields=['khata_number'], name='app_landrec_khata_n_845f95_idx'),
            models.Index(fields=['district', 'taluka', 'village'], name='app_landrec_distri_d8346b_idx'),
            models.Index(fields=['district', 'taluka', 'village', 'gut_number', 'khata_number'], name='app_landrec_distri_95b175_idx'),
        ]

    def __str__(self):
        return f"{self.village} - Gut {self.gut_number}"


class FarmerNames(models.Model):
    land_record = models.ForeignKey(
        LandRecord712,
        on_delete=models.CASCADE,
        related_name='farmers'
    )

    farmer_name = models.CharField(max_length=200)

    # 🔹 Total Area (Mul Kshetra) in Hectare-R format
    total_area = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Format: H-R (e.g. 1-65)"
    )

    # 🔹 Potkharaba Area in Hectare-R format
    potkharaba = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Format: H-R (e.g. 0-53)"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.farmer_name} - Gut {self.land_record.gut_number}"
    

class AssetTypeMaster(models.Model):
    asset_code = models.CharField(max_length=100, unique=True)
    asset_name_marathi = models.CharField(max_length=200)
    asset_name_english = models.CharField(max_length=200, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "asset_type_master"
        ordering = ["display_order", "asset_name_marathi"]

    def __str__(self):
        return self.asset_name_marathi


class AssetCategory(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name_marathi = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "asset_categories"
        ordering = ["display_order", "name_marathi"]

    def __str__(self):
        return self.name_marathi


class AssetList(models.Model):
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.CASCADE,
        related_name="asset_list"
    )
    code = models.CharField(max_length=100)
    name_marathi = models.CharField(max_length=200)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "asset_list"
        ordering = ["category__display_order", "display_order", "name_marathi"]
        unique_together = ("category", "code")

    def __str__(self):
        return f"{self.category.name_marathi} - {self.name_marathi}"


class AssetFieldMaster(models.Model):
    FIELD_TYPE_CHOICES = [
        ("number", "Number"),
        ("text", "Text"),
        ("select", "Select"),
    ]

    asset_type = models.ForeignKey(
        AssetTypeMaster,
        on_delete=models.CASCADE,
        related_name="fields"
    )

    field_name = models.CharField(max_length=100)
    field_label_marathi = models.CharField(max_length=200)
    field_label_english = models.CharField(max_length=200, blank=True, null=True)
    field_type = models.CharField(max_length=50, choices=FIELD_TYPE_CHOICES, default="number")
    unit = models.CharField(max_length=50, blank=True, null=True)
    is_required = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "asset_field_master"
        ordering = ["display_order", "id"]

    def __str__(self):
        return f"{self.asset_type.asset_name_marathi} - {self.field_label_marathi}"
    

class TreeMaster(models.Model):
    tree_name_marathi = models.CharField(max_length=200, unique=True)

    class Meta:
        db_table = "tree_master"
        ordering = ["tree_name_marathi"]

    def __str__(self):
        return self.tree_name_marathi


class Asset(models.Model):
    ASSET_TYPE_CHOICES = [
        ('building', 'इमारत'),
        ('wall', 'भिंत'),
        ('well', 'विहीर'),
        ('tree_asset', 'झाड / वनस्पती'),
        ('pipeline', 'पाईपलाईन'),
        ('road', 'रस्ता'),
        ('fencing', 'कंपाउंड / कुंपण'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='assets'
    )

    asset_type = models.CharField(max_length=100, choices=ASSET_TYPE_CHOICES)
    asset_name = models.CharField(max_length=255)

    district = models.CharField(max_length=100, blank=True, null=True)
    taluka = models.CharField(max_length=100, blank=True, null=True)
    village = models.CharField(max_length=150, blank=True, null=True)
    gut_number = models.CharField(max_length=100, blank=True, null=True)

    survey_date = models.DateField(blank=True, null=True)
    rate = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    government_estimated_rate = models.DecimalField(
    max_digits=15,
    decimal_places=2,
    null=True,
    blank=True
   )
    formula_text = models.TextField(blank=True, null=True)
    total_measurement = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    final_calculation = models.TextField(blank=True, null=True)
    final_amount = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    government_final_amount = models.DecimalField(
    max_digits=15,
    decimal_places=2,
    null=True,
    blank=True
)

    remarks = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.asset_name} ({self.get_asset_type_display()})"
    
    def get_documents(self):
        """Get all documents associated with this asset"""
        return DocumentMaster.objects.filter(asset=self).prefetch_related('attachments')


class AssetMeasurement(models.Model):
    asset = models.ForeignKey(
        Asset,
        on_delete=models.CASCADE,
        related_name='measurements'
    )

    field_name = models.CharField(max_length=100)
    field_label = models.CharField(max_length=255)
    field_value = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    unit = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"{self.asset.asset_name} - {self.field_label}"

class AssetFormulaMaster(models.Model):
    asset_type = models.OneToOneField(
        AssetTypeMaster,
        on_delete=models.CASCADE,
        related_name="formula"
    )
    formula_label_marathi = models.CharField(max_length=255)
    formula_label_english = models.CharField(max_length=255, blank=True, null=True)
    formula_expression = models.CharField(max_length=500)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "asset_formula_master"

    def __str__(self):
        return f"{self.asset_type.asset_name_marathi} - {self.formula_label_marathi}"



# =========================================================
# 🔹 Unified Document Model (General + Court)
# =========================================================

class Document(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    # ---------------- Document Type ----------------
    DOCUMENT_TYPE_CHOICES = [
        ('general', 'General Document'),
        ('court', 'Court Matter Document'),
    ]


    document_type = models.CharField(
        max_length=20,
        choices=DOCUMENT_TYPE_CHOICES
    )

    # ---------------- Court / Matter Type ----------------
    MATTER_TYPE_CHOICES = [
        ('arbitration', 'Arbitration'),
        ('civil_dispute', 'Civil Dispute'),
    ]

    matter_type = models.CharField(
        max_length=20,
        choices=MATTER_TYPE_CHOICES,
        null=True,
        blank=True
    )

    # ---------------- Owner / Farmer ----------------
    owner_name = models.CharField(
        max_length=200,
        null=True,
        blank=True,
        help_text="Name of land owner / farmer"
    )

    # ---------------- Location Level ----------------
    DOCUMENT_LEVEL_CHOICES = [
        ('district', 'District'),
        ('taluka', 'Taluka'),
        ('village', 'Village'),
        ('gut', 'Gut'),
    ]

    document_level = models.CharField(
        max_length=20,
        choices=DOCUMENT_LEVEL_CHOICES
    )

    # ---------------- Location Fields ----------------
    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100, null=True, blank=True)
    village = models.CharField(max_length=150, null=True, blank=True)
    gut_number = models.CharField(max_length=50, null=True, blank=True)

    # ---------------- Common Fields ----------------
    document_name = models.CharField(max_length=255)

    description = models.TextField(
        null=True,
        blank=True
    )

    # ---------------- Court Specific ----------------
    document_date = models.DateField(
        null=True,
        blank=True
    )

    court_date = models.DateField(
        null=True,
        blank=True
    )

    # ---------------- Timestamps ----------------
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.document_name} ({self.document_type})"
    
    def get_documents(self):
        """Get all documents associated with this document record"""
        return DocumentMaster.objects.filter(document_tool_record=self).prefetch_related('attachments')
    




class Entry(models.Model):

    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100, null=True, blank=True)
    village = models.CharField(max_length=150, null=True, blank=True)
    # -------- BASIC DETAILS --------
    sr_no_02 = models.CharField(max_length=50, null=True, blank=True)

    owner_name_03 = models.TextField(null=True, blank=True)

    LAND_CLASS_CHOICES = (
        ("1", "1"),
        ("2", "2"),
    )

    land_class_04 = models.CharField(
        max_length=1,
        choices=LAND_CLASS_CHOICES,
        null=True,
        blank=True
    )

    total_area_05 = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )

    total_assessment_06 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    per_hectare_assessment_07 = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    land_group_08 = models.CharField(max_length=50, null=True, blank=True)

    to_create_09 = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True
    )

    shighrasiddha_number_10 = models.CharField(max_length=50, null=True, blank=True)

    # Column 12
    committee_market_rate_12 = models.DecimalField(
    max_digits=15,
    decimal_places=2,
    null=True,
    blank=True
    )

    # Column 13 — assessment type comes from ReadyReckonerRate records, no fixed choices
    land_type_13 = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    # Column 14
    considered_market_rate_14 = models.DecimalField(
    max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )


    # -------- 2013 ACT MARKET VALUE --------
    market_value_15a = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    zone_15b = models.CharField(max_length=100, null=True, blank=True)

    coefficient_15c = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    total_market_value_15d = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    # -------- ASSET VALUATION --------
    fruit_trees_16a = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    forest_trees_16b = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    construction_16c = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    other_assets_16d = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True
    )

    total_assets_16e = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    # -------- COMPENSATION --------
    determined_compensation_17 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    solatium_amount_18 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    notification_date = models.DateField(
        null=True,
        blank=True,
        help_text="Notification/Valuation date"
    )

    award_date = models.DateField(
        null=True,
        blank=True,
        help_text="Award approval date"
    )

    days_difference = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of days between notification and award"
    )

    additional_12_percent_19 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    non_consent_compensation_20 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    class2_deduction_21 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    payable_non_consent_22 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    consent_bonus_23 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    consent_total_24 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    class2_deduction_consent_25 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    payable_consent_26 = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True
    )

    # Consent field
    is_with_consent = models.BooleanField(
        default=False,
        help_text="Is this record with consent or without consent"
    )

    def __str__(self):
        return f"{self.owner_name_03} - {self.sr_no_02}"

    def get_documents(self):
        return DocumentMaster.objects.filter(entry=self).prefetch_related('attachments')


# =========================================================
# 🔹 Village Data (Acquisition Process - Full Form)
# =========================================================

class VillageData(models.Model):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='village_data')

    # --- मूलभूत माहिती ---
    district = models.TextField()
    taluka = models.TextField()
    village = models.TextField()
    land_acquisition_purpose = models.TextField(blank=True)
    collector_name = models.TextField(blank=True)
    collector_office_name = models.TextField(blank=True)
    collector_office_address = models.TextField(blank=True)

    # --- १. प्रशासकीय मान्यता ---
    sec1_adesh_kramank = models.TextField(blank=True)
    sec1_date = models.DateField(null=True, blank=True)
    sec1_files = models.TextField(blank=True)
    sec1_admin_approvals = models.JSONField(default=list, blank=True)
    notified_area_rows = models.JSONField(default=list, blank=True)
    sec1_total_notified_area = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    notified_area_totals_by_section = models.JSONField(default=dict, blank=True)

    # --- २. कलम 3 अधिसूचना ---
    sec2_adhisuchana_kramank = models.TextField(blank=True)
    sec2_date = models.DateField(null=True, blank=True)
    sec2_files = models.TextField(blank=True)
    sec2_paper1_name = models.TextField(blank=True)
    sec2_paper1_date = models.DateField(null=True, blank=True)
    sec2_paper1_files = models.TextField(blank=True)
    sec2_paper2_name = models.TextField(blank=True)
    sec2_paper2_date = models.DateField(null=True, blank=True)
    sec2_paper2_files = models.TextField(blank=True)

    # --- ३. प्राधिकृत भूसंपादन अधिकारी नियुक्ती ---
    sec3_upvibhag_name = models.TextField(blank=True, default='')
    sec3_rows = models.JSONField(default=list, blank=True)
    sec3_adhisuchana_kramank = models.TextField(blank=True)
    sec3_date = models.DateField(null=True, blank=True)
    sec3_files = models.TextField(blank=True)

    # --- ५. भूसंपादन प्रस्ताव ---
    sec5_prastaav_kramank = models.TextField(blank=True)
    sec5_date = models.DateField(null=True, blank=True)
    sec5_files = models.TextField(blank=True)

    # --- ६. संयुक्त मोजणी ---
    sec6_register_number = models.TextField(blank=True)
    sec6_date = models.DateField(null=True, blank=True)
    sec6_parishisht16_files = models.TextField(blank=True)
    sec6_nakasha_files = models.TextField(blank=True)
    sec6_rows = models.JSONField(default=list, blank=True)

    # --- ७. कलम 17 सुनावणी निर्णय ---
    sec7_aakshep_details = models.TextField(blank=True)
    sec7_files = models.TextField(blank=True)

    # --- ९. कलम 19-ब जाहीर नोटीस ---
    sec9_paper1_name = models.TextField(blank=True)
    sec9_paper1_date = models.DateField(null=True, blank=True)
    sec9_paper1_files = models.TextField(blank=True)
    sec9_paper2_name = models.TextField(blank=True)
    sec9_paper2_date = models.DateField(null=True, blank=True)
    sec9_paper2_files = models.TextField(blank=True)

    # --- १०. जमीन मूल्यांकन (toggle: होय/नाही) ---
    sec7_toggle = models.CharField(max_length=10, blank=True, default='nahi')
    sec10_prastaav_kramank = models.TextField(blank=True)
    sec10_date = models.DateField(null=True, blank=True)
    sec10_files = models.TextField(blank=True)

    # --- ११. नगर रचना विभागाचे अभिप्राय (toggle: होय/नाही) ---
    sec8_toggle = models.CharField(max_length=10, blank=True, default='nahi')
    sec11_patra_kramank = models.TextField(blank=True)
    sec11_date = models.DateField(null=True, blank=True)
    sec11_files = models.TextField(blank=True)

    # --- १२. झोन दाखला माहिती (toggle: होय/नाही) ---
    sec9_toggle = models.CharField(max_length=10, blank=True, default='nahi')
    sec12_zone_details = models.TextField(blank=True)
    sec12_date = models.DateField(null=True, blank=True)
    sec12_files = models.TextField(blank=True)

    # --- १३. दर निश्चितीसाठी खरेदी विक्री तपशील (toggle: होय/नाही) ---
    sec10_toggle = models.CharField(max_length=10, blank=True, default='nahi')
    sec13_kharedi_vikri_details = models.TextField(blank=True)
    sec13_files = models.TextField(blank=True)
    sec13_rows = models.JSONField(default=list, blank=True)

    # --- १४. जिल्हास्तरीय समितीच्या बैठकीचा तपशील ---
    sec14_meeting_details = models.TextField(blank=True)
    sec14_date = models.DateField(null=True, blank=True)
    sec14_approved_rate_details = models.TextField(blank=True, default='')
    sec14_files = models.TextField(blank=True)
    sec14_rows = models.JSONField(default=list, blank=True)

    # --- १६. वन विभाग ---
    sec16_letter_details = models.TextField(blank=True)
    sec16_date = models.DateField(null=True, blank=True)
    sec16_files = models.TextField(blank=True)
    sec16_rows = models.JSONField(default=list, blank=True)

    # --- १७. पाणीपुरवठा ---
    sec17_letter_details = models.TextField(blank=True)
    sec17_date = models.DateField(null=True, blank=True)
    sec17_files = models.TextField(blank=True)
    sec17_rows = models.JSONField(default=list, blank=True)

    # --- १८. कृषी विभाग ---
    sec18_letter_details = models.TextField(blank=True)
    sec18_date = models.DateField(null=True, blank=True)
    sec18_files = models.TextField(blank=True)
    sec18_rows = models.JSONField(default=list, blank=True)

    # --- १९. बांधकाम विभाग ---
    sec19_letter_details = models.TextField(blank=True)
    sec19_date = models.DateField(null=True, blank=True)
    sec19_files = models.TextField(blank=True)
    sec19_rows = models.JSONField(default=list, blank=True)

    # --- २०. इतर विभाग ---
    sec20_letter_details = models.TextField(blank=True)
    sec20_date = models.DateField(null=True, blank=True)
    sec20_files = models.TextField(blank=True)
    sec20_rows = models.JSONField(default=list, blank=True)

    # --- २१. मोबदला निश्चिती ---
    sec21_prastaav = models.TextField(blank=True)
    sec21_prastaav_date = models.DateField(null=True, blank=True)
    sec21_prastaav_files = models.TextField(blank=True)
    sec21_karyavrutant = models.TextField(blank=True)
    sec21_karyavrutant_date = models.DateField(null=True, blank=True)
    sec21_karyavrutant_files = models.TextField(blank=True)
    sec21_rows = models.JSONField(default=list, blank=True)


    # --- २३. निवाडा ---
    sec23_kramank = models.TextField(blank=True)
    sec23_date = models.DateField(null=True, blank=True)
    sec23_files = models.TextField(blank=True)

    # --- २३. न्यायालयीन प्रकरण ---
    sec24_court_details = models.TextField(blank=True)
    sec24_files = models.TextField(blank=True)

    # --- २४. क.जा.प ---
    sec25_kramank = models.TextField(blank=True)
    sec25_date = models.DateField(null=True, blank=True)
    sec25_files = models.TextField(blank=True)
    sec24_account_rows = models.JSONField(default=list, blank=True)
    sec25_map_received = models.CharField(max_length=10, blank=True)
    sec25_not_received_reason = models.TextField(blank=True)
    sec25_map_rows = models.JSONField(default=list, blank=True)

    is_final_submitted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} - {self.taluka} - {self.district}"

    class Meta:
        verbose_name = "Village Data"
        verbose_name_plural = "Village Data"

class VillageData8ARecord(models.Model):
    # --- २५. संपादन संस्थेच्या नावावर झालेल्या ८ अ अभिलेखाचा तपशील ---
    village_data = models.ForeignKey(
        VillageData,
        on_delete=models.CASCADE,
        related_name='sec26_8a_records'
    )
    khate_kramank = models.TextField(blank=True)
    navavar_kshetra = models.TextField(blank=True)
    ferfar_kramank = models.TextField(blank=True)
    ferfar_date = models.DateField(null=True, blank=True)
    files = models.TextField(blank=True)

    def __str__(self):
        return f"{self.khate_kramank} - {self.ferfar_kramank}"

    # files → via VillageData8AFile (related_name='8a_files')

    class Meta:
        verbose_name = "8A Record"
        verbose_name_plural = "8A Records"


class VillageData32_2Row(models.Model):
    # --- ४. कलम 15(2) प्राथमिक अधिसूचना (repeatable rows) ---
    village_data = models.ForeignKey(
        VillageData,
        on_delete=models.CASCADE,
        related_name='sec4_rows'
    )
    adhisuchana_kramank = models.TextField(blank=True)
    adhisuchana_date = models.DateField(null=True, blank=True)
    paper1_name = models.TextField(blank=True)
    paper1_date = models.DateField(null=True, blank=True)
    paper2_name = models.TextField(blank=True)
    paper2_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.adhisuchana_kramank} ({self.adhisuchana_date or '-'})"

    class Meta:
        verbose_name = "VillageData15(2) Row"
        verbose_name_plural = "VillageData15(2) Rows"


class VillageData32_1Row(models.Model):
    # --- ८. कलम 18/1 अंतिम अधिसूचना (repeatable rows) ---
    village_data = models.ForeignKey(
        VillageData,
        on_delete=models.CASCADE,
        related_name='sec8_rows'
    )
    adhisuchana_kramank = models.TextField(blank=True)
    adhisuchana_date = models.DateField(null=True, blank=True)
    paper1_name = models.TextField(blank=True)
    paper1_date = models.DateField(null=True, blank=True)
    paper2_name = models.TextField(blank=True)
    paper2_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.adhisuchana_kramank} ({self.adhisuchana_date or '-'})"

    class Meta:
        verbose_name = "VillageData18(1) Row"
        verbose_name_plural = "VillageData18(1) Rows"


def _safe_village_folder_name(value, fallback):
    raw = (value or '').strip()
    if not raw:
        return fallback
    # Keep path deterministic and safe across OS/filesystems.
    raw = raw.replace('/', '-').replace('\\', '-').lower()
    safe = get_valid_filename(raw)
    return safe or fallback


def village_data_file_upload_to(instance, filename):
    village_data = instance.village_data
    district = _safe_village_folder_name(getattr(village_data, 'district', ''), 'unknown_district')
    taluka = _safe_village_folder_name(getattr(village_data, 'taluka', ''), 'unknown_taluka')
    village = _safe_village_folder_name(getattr(village_data, 'village', ''), 'unknown_village')
    field_key = _safe_village_folder_name(getattr(instance, 'field_key', ''), 'misc')
    safe_name = get_valid_filename(filename) or 'file'
    return f'village_documents/{district}/{taluka}/{village}/fields/{field_key}/{safe_name}'


def village_8a_file_upload_to(instance, filename):
    village_data = getattr(getattr(instance, 'record_8a', None), 'village_data', None)
    district = _safe_village_folder_name(getattr(village_data, 'district', ''), 'unknown_district')
    taluka = _safe_village_folder_name(getattr(village_data, 'taluka', ''), 'unknown_taluka')
    village = _safe_village_folder_name(getattr(village_data, 'village', ''), 'unknown_village')
    safe_name = get_valid_filename(filename) or 'file'
    return f'village_documents/{district}/{taluka}/{village}/8a_records/{safe_name}'


def village_15_2_row_file_upload_to(instance, filename):
    village_data = getattr(getattr(instance, 'row_15_2', None), 'village_data', None)
    district = _safe_village_folder_name(getattr(village_data, 'district', ''), 'unknown_district')
    taluka = _safe_village_folder_name(getattr(village_data, 'taluka', ''), 'unknown_taluka')
    village = _safe_village_folder_name(getattr(village_data, 'village', ''), 'unknown_village')
    safe_name = get_valid_filename(filename) or 'file'
    return f'village_documents/{district}/{taluka}/{village}/sec4_rows/{safe_name}'


def village_18_1_row_file_upload_to(instance, filename):
    village_data = getattr(getattr(instance, 'row_18_1', None), 'village_data', None)
    district = _safe_village_folder_name(getattr(village_data, 'district', ''), 'unknown_district')
    taluka = _safe_village_folder_name(getattr(village_data, 'taluka', ''), 'unknown_taluka')
    village = _safe_village_folder_name(getattr(village_data, 'village', ''), 'unknown_village')
    safe_name = get_valid_filename(filename) or 'file'
    return f'village_documents/{district}/{taluka}/{village}/sec8_rows/{safe_name}'


class VillageDataFile(models.Model):
    """Stores multiple uploaded files for any field_key in VillageData."""
    village_data = models.ForeignKey(
        VillageData,
        on_delete=models.CASCADE,
        related_name='village_files'
    )
    field_key = models.CharField(max_length=100)  # e.g. 'sec1_files', 'sec6_nakasha_files'
    file = models.FileField(upload_to=village_data_file_upload_to, max_length=1000)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.village_data.village} | {self.field_key} | {self.file.name}"

    class Meta:
        verbose_name = "Village Data File"
        verbose_name_plural = "Village Data Files"


class VillageData8AFile(models.Model):
    """Stores multiple uploaded files for a VillageData8ARecord."""
    record_8a = models.ForeignKey(
        VillageData8ARecord,
        on_delete=models.CASCADE,
        related_name='files_8a'
    )
    file = models.FileField(upload_to=village_8a_file_upload_to, max_length=1000)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.record_8a} | {self.file.name}"

    class Meta:
        verbose_name = "8A File"
        verbose_name_plural = "8A Files"


class VillageData32_2RowFile(models.Model):
    """Stores multiple uploaded files for a VillageData32_2Row."""
    row_15_2 = models.ForeignKey(
        VillageData32_2Row,
        on_delete=models.CASCADE,
        related_name='files_15_2'
    )
    field_key = models.CharField(max_length=40, default='main')
    file = models.FileField(upload_to=village_15_2_row_file_upload_to, max_length=1000)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.row_15_2} | {self.file.name}"

    class Meta:
        verbose_name = "VillageData15(2) Row File"
        verbose_name_plural = "VillageData15(2) Row Files"


class VillageData32_1RowFile(models.Model):
    """Stores multiple uploaded files for a VillageData32_1Row."""
    row_18_1 = models.ForeignKey(
        VillageData32_1Row,
        on_delete=models.CASCADE,
        related_name='files_18_1'
    )
    field_key = models.CharField(max_length=40, default='main')
    file = models.FileField(upload_to=village_18_1_row_file_upload_to, max_length=1000)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.row_18_1} | {self.file.name}"

    class Meta:
        verbose_name = "VillageData18(1) Row File"
        verbose_name_plural = "VillageData18(1) Row Files"


class VillageDataSec15Rate(models.Model):
    # --- १५. संपादनाखालील जमिनींसाठी जिल्हास्तरीय समितीने मंजूर केलेला अंतिम दर ---
    # मूल्य विभाग प्रकार, Assessment Range, रेडी रेकनर दर, एकक → from ReadyReckonerRate
    # जिल्हास्तरीय समितीने मंजूर केलेला दर → stored here (only new input)
    village_data = models.ForeignKey(
        VillageData,
        on_delete=models.CASCADE,
        related_name='sec15_rates'
    )
    rr_rate = models.ForeignKey(
        ReadyReckonerRate,
        on_delete=models.PROTECT,
        related_name='sec15_entries'
    )
    # only field the user fills in for sec15
    approved_rate = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.village_data.village} - {self.rr_rate}"

    class Meta:
        verbose_name = "Sec15 Approved Rate"
        verbose_name_plural = "Sec15 Approved Rates"
        unique_together = ('village_data', 'rr_rate')


class ProcessChartCase(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("approved", "Approved"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="process_chart_cases",
    )

    division = models.CharField(max_length=100, null=True, blank=True)
    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=150)
    gut_number = models.CharField(max_length=50)

    project_purpose = models.CharField(max_length=255, null=True, blank=True)
    acquisition_type = models.CharField(max_length=100, null=True, blank=True)

    land_record_id_ref = models.BigIntegerField(null=True, blank=True)
    village_data_id_ref = models.BigIntegerField(null=True, blank=True)
    rr_info_id_ref = models.BigIntegerField(null=True, blank=True)
    current_step = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    is_record_authenticated = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} - {self.gut_number}"


class ProcessChartStepData(models.Model):
    case = models.ForeignKey(
        ProcessChartCase,
        on_delete=models.CASCADE,
        related_name="step_data",
    )
    step_no = models.PositiveSmallIntegerField()
    section_code = models.CharField(max_length=100)
    data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("case", "step_no", "section_code")

    def __str__(self):
        return f"{self.case} | Step {self.step_no} | {self.section_code}"


class ProcessChartAuditLog(models.Model):
    case = models.ForeignKey(
        ProcessChartCase,
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    step_no = models.PositiveSmallIntegerField()
    section_code = models.CharField(max_length=100, blank=True, default="")
    field_path = models.CharField(max_length=255)
    field_label = models.CharField(max_length=255)
    old_value = models.TextField(blank=True, default="")
    new_value = models.TextField(blank=True, default="")
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="process_chart_audit_logs",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at", "-id")

    def __str__(self):
        return f"{self.case} | Step {self.step_no} | {self.field_label}"


class ProcessChartDocument(models.Model):
    case = models.ForeignKey(
        ProcessChartCase,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    step_no = models.PositiveSmallIntegerField()
    section_code = models.CharField(max_length=100)
    document_type = models.CharField(max_length=100)
    file = models.FileField(upload_to="process_chart/files/", max_length=1000)
    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.case} | {self.document_type}"


class ProcessChartOwnerNotice(models.Model):
    NOTICE_TYPE_CHOICES = [
        ("personal_notice", "Personal Notice"),
        ("public_notice", "Public Notice"),
        ("award_notice", "Award Notice"),
        ("sample_6", "Sample 6"),
        ("forced_notice", "Forced Notice"),
        ("possession_notice", "Possession Notice"),
    ]

    case = models.ForeignKey(
        ProcessChartCase,
        on_delete=models.CASCADE,
        related_name="owner_notices",
    )
    source_farmer_id_ref = models.BigIntegerField(null=True, blank=True)

    owner_name = models.CharField(max_length=255)
    area = models.CharField(max_length=50, null=True, blank=True)
    notice_type = models.CharField(max_length=30, choices=NOTICE_TYPE_CHOICES)
    notice_number = models.CharField(max_length=100, null=True, blank=True)
    notice_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.owner_name} - {self.notice_type}"


class ProcessChartDepartmentRow(models.Model):
    DEPARTMENT_CHOICES = [
        ("panipurvatha", "पाणीपुरवठा"),
        ("krushi", "कृषी विभाग"),
        ("bandhakam", "बांधकाम विभाग"),
        ("van", "वन विभाग"),
        ("itar", "इतर विभाग"),
    ]

    case = models.ForeignKey(
        ProcessChartCase,
        on_delete=models.CASCADE,
        related_name="department_rows",
    )
    department_type = models.CharField(max_length=30, choices=DEPARTMENT_CHOICES)
    owner_name = models.CharField(max_length=255, null=True, blank=True)
    details = models.TextField(null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    valuation = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    related_component_details = models.TextField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.case} - {self.department_type}"


class ProcessChartValuationRow(models.Model):
    case = models.ForeignKey(
        ProcessChartCase,
        on_delete=models.CASCADE,
        related_name="valuation_rows",
    )

    valuation_type = models.CharField(max_length=255)
    assessment_range = models.CharField(max_length=100, null=True, blank=True)
    value_division = models.CharField(max_length=100, null=True, blank=True)
    ready_reckoner_rate = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    committee_rate = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    unit = models.CharField(max_length=50, null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.case} - {self.valuation_type}"
