from django.contrib import admin
from .models import Inspection, AssetDetail, ReadyReckonerRate, LandRecord712, FarmerNames, ToolMaster, Document, Asset, AssetCategory, AssetList, AssetTypeMaster, AssetFieldMaster, AssetFormulaMaster

# Register your models here.

admin.site.register(Inspection)
admin.site.register(AssetDetail)
admin.site.register(ReadyReckonerRate)
admin.site.register(LandRecord712)
admin.site.register(FarmerNames)
admin.site.register(ToolMaster)
admin.site.register(Document)
admin.site.register(Asset)
admin.site.register(AssetTypeMaster)
admin.site.register(AssetFieldMaster)
admin.site.register(AssetFormulaMaster)
admin.site.register(AssetCategory)
admin.site.register(AssetList)
