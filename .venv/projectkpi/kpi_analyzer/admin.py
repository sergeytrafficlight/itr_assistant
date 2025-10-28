from django.contrib import admin
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from .models import Offer, Lead, Call, KpiPlan

class OfferResource(resources.ModelResource):
    class Meta:
        model = Offer

class LeadResource(resources.ModelResource):
    class Meta:
        model = Lead

class CallResource(resources.ModelResource):
    class Meta:
        model = Call

class KpiPlanResource(resources.ModelResource):
    class Meta:
        model = KpiPlan

@admin.register(Offer)
class OfferAdmin(ImportExportModelAdmin):
    resource_class = OfferResource

@admin.register(Lead)
class LeadAdmin(ImportExportModelAdmin):
    resource_class = LeadResource

@admin.register(Call)
class CallAdmin(ImportExportModelAdmin):
    resource_class = CallResource

@admin.register(KpiPlan)
class KpiPlanAdmin(ImportExportModelAdmin):
    resource_class = KpiPlanResource