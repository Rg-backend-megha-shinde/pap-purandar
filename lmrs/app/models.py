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