from django.db import models

class Offer(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=255)
    category_name = models.CharField(max_length=100)

    def __str__(self):
        return f"[{self.id}] {self.name}"

class Lead(models.Model):
    call_eff_crm_lead_id = models.IntegerField()
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE)
    aff_id = models.IntegerField()
    lv_username = models.CharField(max_length=100)
    category_name = models.CharField(max_length=100)

    def __str__(self):
        return f"Lead {self.call_eff_crm_lead_id} by {self.lv_username}"

class Call(models.Model):
    call_eff_id = models.IntegerField(primary_key=True)
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE)
    call_eff_affiliate_id = models.IntegerField()
    lv_username = models.CharField(max_length=100)
    category_name = models.CharField(max_length=100)
    created_at = models.DateTimeField()
    duration = models.IntegerField()

    def __str__(self):
        return f"Call {self.call_eff_id} by {self.lv_username}"

class KpiPlan(models.Model):
    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, null=True)
    update_date = models.DateField()
    operator_efficiency = models.FloatField(null=True)
    planned_approve = models.FloatField(null=True)
    planned_buyout = models.FloatField(null=True)
    confirmation_price = models.FloatField(null=True)
    operator_effeciency_update_date = models.DateField(null=True)
    planned_approve_update_date = models.DateField(null=True)
    planned_buyout_update_date = models.DateField(null=True)

    def __str__(self):
        return f"KPI for {self.offer} on {self.update_date}"

class KpiList:
    def __init__(self):
        self.plans = KpiPlan.objects.all()

    def find_kpi(self, category, offer_id, date_str):
        try:
            return self.plans.filter(
                offer_id=int(offer_id),
                update_date=date_str
            ).first()
        except (ValueError, TypeError):
            return None