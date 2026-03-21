from django.db import models
from django.contrib.auth.models import User


# =========================================================
# 🔹 Inspection Tool
# =========================================================

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

    def __str__(self):
        return self.name or "Tree"


# =========================================================
# 🔹 Ready Reckoner Rate Tool
# =========================================================

class ReadyReckonerRate(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="rr_rates"
    )

    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=100)

    year = models.CharField(max_length=20, default='2024-2025')

    assessment_type = models.CharField(max_length=200)

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

    UNIT_CHOICES = [
        ('हेक्टर', 'हेक्टर'),
        ('चौ. मीटर', 'चौ. मीटर'),
    ]

    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)

    document = models.FileField(
        upload_to='ready_reckoner_documents/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return (
            f"{self.village} | {self.assessment_type} | "
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

    document_712 = models.FileField(
        upload_to='712_documents/',
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} - Gut {self.gut_number}"


class FarmerNames(models.Model):
    land_record = models.ForeignKey(
        LandRecord712,
        on_delete=models.CASCADE,
        related_name='farmers'
    )

    farmer_name = models.CharField(max_length=200)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.farmer_name} - Gut {self.land_record.gut_number}"
    

class TreeMaster(models.Model):
    tree_name_marathi = models.CharField(max_length=200, unique=True)

    class Meta:
        db_table = "tree_master"
        ordering = ["tree_name_marathi"]

    def __str__(self):
        return self.tree_name_marathi



# =========================================================
# 🔹 General Documents Upload Tool
# =========================================================

class GeneralDocument(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="general_documents"
    )

    # Location hierarchy (optional fields)
    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100, null=True, blank=True)
    village = models.CharField(max_length=150, null=True, blank=True)
    gut_number = models.CharField(max_length=50, null=True, blank=True)

    # Document details
    document_name = models.CharField(max_length=255)

    document = models.FileField(
        upload_to='general_documents/',
        null=True,
        blank=True
    )

    description = models.TextField(
        null=True,
        blank=True
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.document_name} - {self.district}"


# =========================================================
# 🔹 Court Matter Documents
# =========================================================

class CourtMatterDocument(models.Model):

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="court_documents"
    )

    # Document level (where it applies)
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

    # Location hierarchy
    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100, null=True, blank=True)
    village = models.CharField(max_length=150, null=True, blank=True)
    gut_number = models.CharField(max_length=50, null=True, blank=True)

    # Court matter specific fields
    document_name = models.CharField(max_length=255)

    document_date = models.DateField(
        null=True,
        blank=True
    )

    court_date = models.DateField(
        null=True,
        blank=True
    )

    document = models.FileField(
        upload_to='court_documents/',
        null=True,
        blank=True
    )

    description = models.TextField(
        null=True,
        blank=True
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.document_name} | Court Date: {self.court_date}"