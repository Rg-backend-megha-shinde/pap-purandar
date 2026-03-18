from django.db import models

# 🔹 Main Form Table
class Inspection(models.Model):
    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=100)
    gut_number = models.CharField(max_length=50)

    officer = models.CharField(max_length=200)
    date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.village} - {self.gut_number}"


# 🔹 Tree Rows Table
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

class ReadyReckonerRate(models.Model):
    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=100)

    assessment_type = models.CharField(max_length=200)
    assessment_range_min = models.DecimalField(max_digits=10, decimal_places=2)
    assessment_range_max = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=15, decimal_places=2)
    UNIT_CHOICES = [
        ('हेक्टर', 'हेक्टर'),
        ('चौ. मीटर', 'चौ. मीटर'),
    ]
    unit = models.CharField(max_length=50, choices=UNIT_CHOICES)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.village} | {self.assessment_type} | {self.assessment_range_min}-{self.assessment_range_max} | ₹{self.rate}"
    

class LandRecord712(models.Model):
    district = models.CharField(max_length=100)
    taluka = models.CharField(max_length=100)
    village = models.CharField(max_length=150)
    gut_number = models.CharField(max_length=50)
    farmer_name = models.CharField(max_length=200)
    assessment_type = models.CharField(max_length=200, null=True, blank=True)
    aakarnee = models.CharField(max_length=100, null=True, blank=True)  # आकारणी e.g. 10.1.1
    rate_applied = models.CharField(max_length=100, null=True, blank=True)  # e.g. 2298500, 685000, 1000
    document_712 = models.FileField(upload_to='712_documents/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.village} - Gut {self.gut_number} - {self.farmer_name}"