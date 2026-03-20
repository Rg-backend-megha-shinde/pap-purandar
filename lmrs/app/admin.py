from django.contrib import admin
from .models import Inspection, TreeDetail, ReadyReckonerRate, LandRecord712, FarmerNames

# Register your models here.

admin.site.register(Inspection)
admin.site.register(TreeDetail)
admin.site.register(ReadyReckonerRate)
admin.site.register(LandRecord712)
admin.site.register(FarmerNames)


