from django.contrib import admin
from .models import (
    ActiveUserSession, Asset, AssetCategory, AssetDetail, AssetFieldMaster, AssetFormulaMaster,
    AssetList, AssetMeasurement, AssetTypeMaster, Document, DocumentAttachment, DocumentMaster,
    Entry, FarmerNames, Inspection, LandRecord712, Notification, NotificationCommonInfo,
    NotificationFile, ProcessChartAuditLog, ProcessChartCase, ProcessChartDepartmentRow,
    ProcessChartDocument, ProcessChartOwnerNotice, ProcessChartStepData, ProcessChartValuationRow,
    ReadyReckonerInfo, ReadyReckonerRate, RorDistrict, RorDivision, RorSurveyNumber, RorTaluka,
    RorVillage, ToolMaster, TreeMaster, VillageData, VillageData8AFile, VillageData8ARecord,
    VillageData32_1Row, VillageData32_1RowFile, VillageData32_2Row, VillageData32_2RowFile,
    VillageDataFile, VillageDataSec15Rate,
)

# Register your models here.

# Inspection / assets
admin.site.register(Inspection)
admin.site.register(Asset)
admin.site.register(AssetCategory)
admin.site.register(AssetDetail)
admin.site.register(AssetFieldMaster)
admin.site.register(AssetFormulaMaster)
admin.site.register(AssetList)
admin.site.register(AssetMeasurement)
admin.site.register(AssetTypeMaster)
admin.site.register(TreeMaster)

# 7/12 records
admin.site.register(LandRecord712)
admin.site.register(FarmerNames)

# ROR (7/12 API) cache — division/district/taluka/village codes and survey numbers
admin.site.register(RorDivision)
admin.site.register(RorDistrict)
admin.site.register(RorTaluka)
admin.site.register(RorVillage)
admin.site.register(RorSurveyNumber)

# अधिसूचना साधन
admin.site.register(Notification)
admin.site.register(NotificationCommonInfo)
admin.site.register(NotificationFile)

# भूसंपादन प्रक्रिया
admin.site.register(ProcessChartCase)
admin.site.register(ProcessChartStepData)
admin.site.register(ProcessChartAuditLog)
admin.site.register(ProcessChartDocument)
admin.site.register(ProcessChartOwnerNotice)
admin.site.register(ProcessChartDepartmentRow)
admin.site.register(ProcessChartValuationRow)

# गावाची माहिती
admin.site.register(VillageData)
admin.site.register(VillageDataFile)
admin.site.register(VillageDataSec15Rate)
admin.site.register(VillageData8ARecord)
admin.site.register(VillageData8AFile)
admin.site.register(VillageData32_1Row)
admin.site.register(VillageData32_1RowFile)
admin.site.register(VillageData32_2Row)
admin.site.register(VillageData32_2RowFile)

# रेडी रेकनर दर
admin.site.register(ReadyReckonerInfo)
admin.site.register(ReadyReckonerRate)

# Documents, tools, misc
admin.site.register(Document)
admin.site.register(DocumentMaster)
admin.site.register(DocumentAttachment)
admin.site.register(ToolMaster)
admin.site.register(Entry)
admin.site.register(ActiveUserSession)
