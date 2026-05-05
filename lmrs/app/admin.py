from django.contrib import admin
from .models import Inspection, AssetDetail, ReadyReckonerRate, LandRecord712, FarmerNames,ToolMaster, Document, Asset

# Register your models here.

admin.site.register(Inspection)
admin.site.register(AssetDetail)
admin.site.register(ReadyReckonerRate)
admin.site.register(LandRecord712)
admin.site.register(FarmerNames)
admin.site.register(ToolMaster)
admin.site.register(Document)
admin.site.register(Asset)
