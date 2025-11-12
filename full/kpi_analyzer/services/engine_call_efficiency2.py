class EngineCallEfficiency2:
    min_eff = 0.1
    call_effeciency_second = 60

    class Kpi:
        def __init__(self, r):
            self.id = r.get('call_eff_kpi_id')
            self.update_date = r.get('call_eff_plan_update_date')
            self.period_date = r.get('call_eff_period_date')
            self.offer_id = r.get('call_eff_offer_id')
            self.affiliate_id = r.get('call_eff_affiliate_id')
            self.confirmation_price = r.get('call_eff_confirmation_price')
            self.buyout_price = r.get('call_eff_buyout_price')
            self.operator_efficiency = r.get('call_eff_operator_efficiency')
            self.operator_effeciency_update_date = r.get('call_eff_operator_efficiency_update_date')
            self.planned_approve = r.get('call_eff_planned_approve')
            self.planned_approve_update_date = r.get('call_eff_approve_update_date')
            self.planned_buyout = r.get('call_eff_planned_buyout')
            self.planned_buyout_update_date = r.get('call_eff_buyout_update_date')
            self.confirmation_price_update_date = r.get('call_eff_confirmation_price_update_date')
            self.buyout_price_update_date = r.get('call_eff_buyout_price_update_date')

            self.key_aff_offer = EngineCallEfficiency2.kpi_make_key(self.affiliate_id, self.offer_id)
            self.is_personal_plan = self.affiliate_id is not None

            if self.period_date and len(self.period_date) != 10:
                raise Exception(f"Wrong date for KPI '{self.period_date}' len({len(self.period_date)})")

        def print_kpi(self):
            return f"ID: {self.id} date: {self.period_date} offer_id: {self.offer_id} affiliate_id: {self.affiliate_id} op_eff: {self.operator_efficiency}"

    class Call:
        def __init__(self, r):
            self.id = r.get('call_eff_id')
            self.crm_id = r.get('call_eff_crm_id')
            self.offer_id = r.get('call_eff_offer_id')
            self.uniqueid = r.get('call_eff_uniqueid')
            self.billsec = r.get('call_eff_billsec')
            self.billsec_exact = r.get('call_eff_billsec_exact')
            self.operator_id = r.get('call_eff_operator_id')
            self.crm_lead_id = r.get('call_eff_crm_lead_id')
            self.calldate_str = r.get('call_eff_calldate')
            self.affiliate_id = r.get('call_eff_affiliate_id')

            if self.billsec_exact:
                try:
                    self.billsec_exact = int(self.billsec_exact)
                    if self.billsec_exact < 0:
                        self.billsec_exact = self.billsec
                except:
                    self.billsec_exact = self.billsec

            if self.billsec is None:
                raise Exception(f"Billsec is null id: {self.id}")

            if self.billsec_exact and self.billsec_exact < self.billsec:
                self.billsec = self.billsec_exact

            self.calldate_date_str = self.calldate_str[:10] if self.calldate_str else ""

        def make_key(self):
            return f"{self.calldate_date_str} {self.operator_id} {self.crm_lead_id}"

        def print_call(self):
            return f"ID: {self.id} crm id: {self.crm_id} offer_id: {self.offer_id} affiliate_id: {self.affiliate_id} calldate: {self.calldate_str}"

    class Lead:
        def __init__(self, r):
            self.crm_lead_id = r.get('call_eff_crm_lead_id')
            self.approved_at = r.get('call_eff_approved_at')
            self.canceled_at = r.get('call_eff_canceled_at')
            self.status_verbose = r.get('call_eff_status_verbose')
            self.status_group = r.get('call_eff_status_group')
            self.operator_id = r.get('call_eff_operator_id')
            self.is_salary_pay = True
            self.is_salary_not_pay_reason = ""

        def set_no_salary(self, reason):
            self.is_salary_pay = False
            self.is_salary_not_pay_reason = reason

        def finalyze(self):
            from .engine_leads_proccesing import EngineLeadsProcessing
            self.is_salary_not_pay_reason = EngineLeadsProcessing.is_fake_approve({
                'status_verbose': self.status_verbose,
                'status_group': self.status_group,
                'approved_at': self.approved_at,
                'canceled_at': self.canceled_at
            })
            self.is_salary_pay = not bool(self.is_salary_not_pay_reason)

    class CallGroup:
        def __init__(self, key, call, effeciency_call_seconds):
            self.key = key
            self.calls = {}
            self.calls_effective = {}
            self.call_effective_first = None
            self.is_effective = False
            self.calls_effective_count = 0
            self.offer_id = call.offer_id
            self.affiliate_id = call.affiliate_id
            self.calldate_str = call.calldate_str
            self.effeciency_call_seconds = effeciency_call_seconds

        def push_call(self, call):
            if call.uniqueid in self.calls:
                self.calls[call.uniqueid].billsec = max(self.calls[call.uniqueid].billsec, call.billsec)
            else:
                self.calls[call.uniqueid] = call

        def finalyze(self):
            for call in self.calls.values():
                if call.billsec >= self.effeciency_call_seconds:
                    self.calls_effective[call.uniqueid] = call
                    self.calls_effective_count += 1
                    if self.call_effective_first is None:
                        self.call_effective_first = call
            self.is_effective = self.calls_effective_count > 0

    class KpiList:
        def __init__(self):
            self.kpi_by_aff_offer = {}
            self.kpi_by_offer = {}
            self.kpi_cache = {}

        def push_kpi_item(self, storage, kpi, key):
            if key not in storage:
                storage[key] = []
            items = storage[key]
            if items and items[-1].period_date > kpi.period_date:
                raise Exception(f"Wrong kpi sort order\nprev: {items[-1].print_kpi()}\nnew: {kpi.print_kpi()}")
            items.append(kpi)

        def push_kpi(self, sql_data):
            kpi = EngineCallEfficiency2.Kpi(sql_data)
            if kpi.affiliate_id is not None:
                self.push_kpi_item(self.kpi_by_aff_offer, kpi, kpi.key_aff_offer)
            else:
                self.push_kpi_item(self.kpi_by_offer, kpi, kpi.offer_id)

        def find_kpi_by_list(self, storage, key, period_date):
            if key not in storage:
                return None
            items = storage[key]
            for i in range(len(items) - 1, -1, -1):
                if items[i].period_date > period_date:
                    continue
                return items[i]
            return None

        def find_kpi(self, affiliate_id, offer_id, period_date):
            if period_date and len(period_date) != 10:
                raise Exception(f"Wrong kpi request period date '{period_date}' expecting len 10")

            result = None
            if affiliate_id is not None:
                key_cache = EngineCallEfficiency2.kpi_make_key_cache(affiliate_id, offer_id, period_date)
                if key_cache in self.kpi_cache:
                    return self.kpi_cache[key_cache]

                key = EngineCallEfficiency2.kpi_make_key(affiliate_id, offer_id)
                result = self.find_kpi_by_list(self.kpi_by_aff_offer, key, period_date)
                if result:
                    self.kpi_cache[key_cache] = result
                    return result

            key_cache = EngineCallEfficiency2.kpi_make_key_cache(None, offer_id, period_date)
            if key_cache in self.kpi_cache:
                return self.kpi_cache[key_cache]

            key = EngineCallEfficiency2.kpi_make_key(None, offer_id)
            result = self.find_kpi_by_list(self.kpi_by_offer, key, period_date)
            if result:
                self.kpi_cache[key_cache] = result
            return result

        def find_kpi_operator_eff(self, affiliate_id, offer_id, period_date):
            result = self.find_kpi(affiliate_id, offer_id, period_date)
            if result and (
                    result.operator_efficiency is None or result.operator_efficiency < EngineCallEfficiency2.min_eff) and result.affiliate_id == affiliate_id:
                return self.find_kpi(None, offer_id, period_date)
            return result

        def print_kpi_list(self):
            result = "AFF OFFER\n"
            for key, items in self.kpi_by_aff_offer.items():
                result += f"K: {key}\n"
                for kpi in items:
                    result += f"\t{kpi.print_kpi()}\n"
            result += "OFFER\n"
            for key, items in self.kpi_by_offer.items():
                result += f"K: {key}\n"
                for kpi in items:
                    result += f"\t{kpi.print_kpi()}\n"
            return result

    class Stat:
        def __init__(self):
            self.calls_group = {}
            self.leads = {}
            self.calls_group_effective_count = 0
            self.calls_group_with_calculation = 0
            self.calls_group_without_calculation = 0
            self.leads_effective_count = 0
            self.leads_with_calculation = 0
            self.leads_without_calculation = 0
            self.effective_rate = 0
            self.expecting_approved_leads = 0.0
            self.expecting_effective_rate = 0.0
            self.effective_percent = 0.0
            self.kpi_calculation_errors = ""
            self.finalyzed = False
            self.name = ""

        def push_call(self, call_data):
            call = EngineCallEfficiency2.Call(call_data)
            key = call.make_key()
            if key not in self.calls_group:
                self.calls_group[key] = EngineCallEfficiency2.CallGroup(key, call, self.call_effeciency_second)
            self.calls_group[key].push_call(call)

        def push_lead(self, lead_data):
            lead = EngineCallEfficiency2.Lead(lead_data)
            if lead.crm_lead_id in self.leads:
                raise Exception(f"Lead duplicate id: {lead.crm_lead_id}")
            self.leads[lead.crm_lead_id] = lead

        def get_effective_calls(self):
            return [group.call_effective_first.crm_id for group in self.calls_group.values() if group.is_effective]

        def get_effective_calls_ids(self):
            return "\n".join(map(str, self.get_effective_calls()))

        def finalyze(self, kpi_list):
            if self.finalyzed:
                raise Exception("Effective calls already finalyzed")
            self.finalyzed = True

            for group in self.calls_group.values():
                group.finalyze()
                if group.is_effective:
                    if group.offer_id == 0:
                        self.calls_group_without_calculation += 1
                        continue

                    self.calls_group_with_calculation += 1
                    kpi = kpi_list.find_kpi_operator_eff(group.affiliate_id, group.offer_id, group.calldate_str)

                    if kpi is None:
                        self.expecting_approved_leads = None
                        self.kpi_calculation_errors += f"Can't find KPI for offer: {group.offer_id} affiliate_id: {group.affiliate_id}\n"
                    elif kpi.operator_efficiency < EngineCallEfficiency2.min_eff:
                        self.expecting_approved_leads = None
                        self.kpi_calculation_errors += f"Wrong KPI for offer: {group.offer_id} affiliate_id: {group.affiliate_id} effeciency: {kpi.operator_efficiency} (< {EngineCallEfficiency2.min_eff})\n"
                    elif self.expecting_approved_leads is not None:
                        self.expecting_approved_leads += 1.0 / kpi.operator_efficiency

            for lead in self.leads.values():
                lead.finalyze()
                if lead.is_salary_pay:
                    if lead.offer_id == 0:
                        self.leads_without_calculation += 1
                        continue
                    self.leads_with_calculation += 1

            if self.calls_group_with_calculation and self.leads_with_calculation:
                self.effective_rate = self.calls_group_with_calculation / self.leads_with_calculation

            if self.expecting_approved_leads is not None:
                self.effective_percent = safe_div(self.leads_with_calculation, self.expecting_approved_leads) * 100
                self.expecting_effective_rate = safe_div(self.calls_group_with_calculation,
                                                         self.expecting_approved_leads)
            else:
                self.effective_percent = None

            self.calls_group_effective_count = self.calls_group_without_calculation + self.calls_group_with_calculation
            self.leads_effective_count = self.leads_with_calculation + self.leads_without_calculation

    @staticmethod
    def kpi_make_key(affiliate_id, offer_id):
        return str(offer_id) if affiliate_id is None else f"{affiliate_id}-{offer_id}"

    @staticmethod
    def kpi_make_key_cache(affiliate_id, offer_id, date):
        affiliate_str = "" if affiliate_id is None else str(affiliate_id)
        return f"{affiliate_str}-{offer_id}-{date}"


def safe_div(numerator, denominator, default=0.0):
    return numerator / denominator if denominator and denominator != 0 else default