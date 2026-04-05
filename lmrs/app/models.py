from django.db import models
from django.contrib.auth.models import User


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
        upload_to='documents/files/'
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Attachment for {self.document_master.tool.tool_name}"
    



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

    officer = models.CharField(max_length=200)
    date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} - {self.gut_number}"
    
    def get_documents(self):
        """Get all documents associated with this inspection"""
        return DocumentMaster.objects.filter(inspection=self)


class TreeDetail(models.Model):
    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="trees"
    )

    plot = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=100, blank=True)

    length = models.FloatField(null=True, blank=True)
    width = models.FloatField(null=True, blank=True)
    girth = models.FloatField(null=True, blank=True)
    height = models.FloatField(null=True, blank=True)
    valuation = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name or "Tree"


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
        ('चौ. मीटर', 'चौ. मीटर'),
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
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="land_records"
    )

    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=150)
    gut_number = models.CharField(max_length=50)

    date = models.DateField(null=True, blank=True)

    assessment_type = models.CharField(
        max_length=200,
        null=True,
        blank=True
    )

    aakarnee = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )  # आकारणी e.g. 10.1.1

    rate_applied = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    rate_year = models.CharField(
        max_length=20,
        null=True,
        blank=True
    )


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} - Gut {self.gut_number}"
    
    def get_documents(self):
        """Get all documents associated with this land record"""
        return DocumentMaster.objects.filter(land_record=self)


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

    # Establishment and Facility percentages
    establishment_expense_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="आस्थापना खर्च देय मोबदल्याच्या (0-100%)"
    )

    facility_amount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        default=0,
        help_text="सोईसुविधा रक्कम देय मोबदल्याच्या (0-100%)"
    )

    # Consent field
    is_with_consent = models.BooleanField(
        default=False,
        help_text="Is this record with consent or without consent"
    )

    def __str__(self):
        return f"{self.owner_name_03} - {self.sr_no_02}"
