import django_tables2 as tables
from .models import Offer, Lead, Call, KpiPlan

class OfferTable(tables.Table):
    class Meta:
        model = Offer
        template_name = "django_tables2/bootstrap4.html"  # Для Bootstrap-стиля
        fields = ("id", "name", "category_name")
        per_page = 10  # Пагинация, как в Sheets

class LeadTable(tables.Table):
    class Meta:
        model = Lead
        template_name = "django_tables2/bootstrap4.html"
        fields = ("call_eff_crm_lead_id", "offer", "aff_id", "lv_username", "category_name")
        per_page = 10

class CallTable(tables.Table):
    class Meta:
        model = Call
        template_name = "django_tables2/bootstrap4.html"
        fields = ("call_eff_id", "offer", "lv_username", "category_name", "created_at", "duration")
        per_page = 10

class KpiPlanTable(tables.Table):
    class Meta:
        model = KpiPlan
        template_name = "django_tables2/bootstrap4.html"
        fields = ("offer", "update_date", "operator_efficiency", "planned_approve", "planned_buyout", "confirmation_price")
        per_page = 10