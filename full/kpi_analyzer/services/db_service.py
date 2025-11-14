from django.db import connections
import logging
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)


class DBService:
    # =============================================================================
    # УТИЛИТЫ
    # =============================================================================
    @staticmethod
    def exclude_category():
        return ['Архив', 'Входящая линия']

    @staticmethod
    def prepare_sql_array(values):
        """ТОЧНАЯ логика из Google Script"""
        if not values:
            return ""
        if isinstance(values, str):
            values = [values]
        prepared_values = []
        for v in values:
            if v is None:
                continue
            str_val = str(v).strip()
            if str_val:
                str_val = str_val.replace("'", "''")
                prepared_values.append(f"'{str_val}'")
        return ",".join(prepared_values)

    @staticmethod
    def prepare_sql_array_array(values):
        return DBService.prepare_sql_array(values)

    @staticmethod
    def normalize_datetime(datetime_str, time_part="00:00:00"):
        if not datetime_str:
            return ""
        try:
            if " " in datetime_str:
                return datetime_str
            else:
                return f"{datetime_str} {time_part}"
        except:
            return datetime_str

    @staticmethod
    def _to_utc(date_str: Optional[str], time_part: str = "00:00:00") -> Optional[str]:
        """Переводит локальное время (МСК) в UTC (-3 часа) для фильтра по calldate"""
        if not date_str:
            return None
        try:
            if " " in date_str:
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            else:
                dt = datetime.strptime(f"{date_str} {time_part}", "%Y-%m-%d %H:%M:%S")
            dt_utc = dt - timedelta(hours=3)
            return dt_utc.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Ошибка парсинга даты: {date_str} → {e}")
            return None

    @staticmethod
    def _convert_decimal_to_float(data):
        if isinstance(data, dict):
            return {k: DBService._convert_decimal_to_float(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [DBService._convert_decimal_to_float(item) for item in data]
        elif isinstance(data, Decimal):
            return float(data)
        else:
            return data

    # =============================================================================
    # KPI — БЕЗ ФИЛЬТРА ПО ДАТЕ (чтобы 2025 загружался)
    # =============================================================================
    @staticmethod
    def get_kpi_query():
        return """
            SELECT
                offer_plan.id as call_eff_kpi_id,
                offer_plan.period_date as call_eff_period_date,
                offer_plan.offer_id as call_eff_offer_id,
                aff.external_id as call_eff_affiliate_id,
                LEFT(DATE_ADD(offer_plan.updated_at, INTERVAL 3 HOUR), 10) as call_eff_plan_update_date,
                offer_plan.confirmation_price as call_eff_confirmation_price,
                offer_plan.buyout_price as call_eff_buyout_price,
                offer_plan.operator_efficiency as call_eff_operator_efficiency,
                LEFT(DATE_ADD(offer_plan.operator_efficiency_updated_at, INTERVAL 3 HOUR), 10) as call_eff_operator_efficiency_update_date,
                offer_plan.planned_approve_from as call_eff_planned_approve,
                LEFT(DATE_ADD(offer_plan.planned_approve_update_at, INTERVAL 3 HOUR), 10) as call_eff_approve_update_date,
                offer_plan.planned_buyout_from as call_eff_planned_buyout,
                LEFT(DATE_ADD(offer_plan.planned_buyout_update_at, INTERVAL 3 HOUR), 10) as call_eff_buyout_update_date,
                offer_plan.confirmation_price as call_eff_confirmation_price,
                LEFT(DATE_ADD(offer_plan.confirmation_price_updated_at, INTERVAL 3 HOUR), 10) as call_eff_confirmation_price_update_date,
                offer_plan.buyout_price as call_eff_buyout_price,
                LEFT(DATE_ADD(offer_plan.buyout_price_updated_at, INTERVAL 3 HOUR), 10) as call_eff_buyout_price_update_date
            FROM partners_tlofferplanneddataperiod AS offer_plan
            LEFT JOIN partners_affiliate aff ON aff.id = offer_plan.affiliate_id
            ORDER BY offer_plan.period_date ASC
        """

    @staticmethod
    def get_kpi_plans_data() -> List[Dict]:
        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(DBService.get_kpi_query())
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                logger.info(f">>> KPI планы: {len(results)} записей")
                return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f"Ошибка при получении KPI планов: {str(e)}")
            return []

    # =============================================================================
    # ОФФЕРЫ
    # =============================================================================
    @staticmethod
    def get_offers(v: Dict) -> List[Dict]:
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        q = """
            SELECT
                partners_offer.id as id,
                partners_offer.name as name,
                group_offer.name as category_name
            FROM partners_offer
            LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = partners_offer.id
            LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
            WHERE 1=1
            AND group_offer.name NOT IN ({})
        """.format(excl_category)
        if category_a:
            q += f" AND group_offer.name IN ({category_a})"
        if offer_a:
            q += f" AND partners_offer.id IN ({offer_a})"
        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f"Ошибка при получении офферов: {str(e)}")
            return []

    # =============================================================================
    # ЗВОНКИ — БАТЧ ПО id > last_id (ИСПРАВЛЕН JOIN)
    # =============================================================================
    @staticmethod
    def get_calls_batch_exact(v: Dict, last_id: int = 0, limit: int = 200) -> List[Dict]:
        last_id = int(last_id or 0)
        date_from = DBService._to_utc(v.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(v.get('date_to'), "23:59:59")
        if not date_from or not date_to:
            logger.error("Неверные даты для звонков")
            return []
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))
        q = f"""
            SELECT
                partners_atscallevent.id as call_eff_id,
                crm_call_calldata.id as call_eff_crm_id,
                po.id as call_eff_offer_id,
                partners_atscallevent.uniqueid as call_eff_uniqueid,
                partners_atscallevent.billsec as call_eff_billsec,
                crm_call_calldata.oktell_duration as call_eff_billsec_exact,
                LEFT(DATE_ADD(partners_atscallevent.calldate, INTERVAL 3 HOUR), 10) AS call_eff_calldate,
                uu.id as call_eff_operator_id,
                crm_call_calldata.crm_lead_id as call_eff_crm_lead_id,
                pt.webmaster_id as call_eff_affiliate_id
            FROM partners_atscallevent
            LEFT JOIN crm_call_calldata ON crm_call_calldata.id = partners_atscallevent.assigned_call_data_id
            LEFT JOIN partners_lvlead ON partners_atscallevent.lvlead_id = partners_lvlead.id
            LEFT JOIN partners_tllead pt ON partners_lvlead.tl_id = pt.external_id
            LEFT JOIN partners_offer po ON pt.offer_id = po.id
            LEFT JOIN partners_assignedoffer ao ON ao.offer_id = po.id
            LEFT JOIN partners_groupoffer go ON ao.group_id = go.id
            LEFT JOIN partners_lvoperator lvo ON lvo.id = partners_atscallevent.lvoperator_id
            LEFT JOIN partners_userbasedonlvoperator pu ON pu.operator_id = lvo.id
            LEFT JOIN users_user uu ON uu.id = pu.user_id
            WHERE partners_atscallevent.billsec >= 30
            AND partners_atscallevent.calldate >= %s
            AND partners_atscallevent.calldate < %s
            AND partners_atscallevent.id > %s
            AND (go.name IS NULL OR go.name NOT IN ({excl_category}))
        """
        params = [date_from, date_to, last_id]
        if offer_a:
            q += f" AND po.id IN ({offer_a})"
        if aff_id_a:
            q += f" AND pt.webmaster_id IN ({aff_id_a})"
        q += " ORDER BY partners_atscallevent.id ASC LIMIT %s"
        params.append(limit)

        for attempt in range(3):
            try:
                start = time.time()
                with connections['itrade'].cursor() as cursor:
                    cursor.execute(q, params)
                    columns = [col[0] for col in cursor.description]
                    results = [dict(zip(columns, row)) for row in cursor.fetchall()]
                duration = time.time() - start
                logger.info(f">>> Батч звонков: {len(results)} за {duration:.2f}с (id > {last_id})")
                return DBService._convert_decimal_to_float(results)
            except Exception as e:
                if 'Lost connection' in str(e) or 'Server has gone away' in str(e):
                    logger.warning(f"Переподключение (звонки)... попытка {attempt + 1}")
                    time.sleep(3)
                    connections['itrade'].close()
                    continue
                logger.error(f">>> Ошибка батча звонков: {e}")
                return []
        return []

    @staticmethod
    def get_calls(v: Dict) -> List[Dict]:
        all_calls = []
        last_id = 0
        batch_size = 200
        total_loaded = 0
        logger.info(">>> Начало загрузки звонков с курсорной пагинацией...")
        while True:
            batch = DBService.get_calls_batch_exact(v, last_id, batch_size)
            if not batch:
                logger.info(">>> Звонки: батч пустой, завершаем")
                break
            all_calls.extend(batch)
            total_loaded += len(batch)
            last_id = int(batch[-1]['call_eff_id'])
            logger.info(f">>> Звонки: загружено {total_loaded}...")
            if len(batch) < batch_size:
                logger.info(f">>> Звонки: последний батч ({len(batch)} записей)")
                break
            if total_loaded > 50000:
                logger.warning(">>> Звонки: достигнут лимит в 50k записей")
                break
        logger.info(f">>> ИТОГО загружено звонков: {len(all_calls)}")
        return all_calls

    # =============================================================================
    # ЛИДЫ — БАТЧ ПО id > last_id
    # =============================================================================
    @staticmethod
    def get_leads_batch_exact(v: Dict, last_id: int = 0, limit: int = 3000) -> List[Dict]:
        date_from = DBService._to_utc(v.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        lv_op_a = DBService.prepare_sql_array(v.get('lv_op', []))
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))
        if not date_from or not date_to:
            logger.error("Неверные даты для лидов")
            return []
        q = f"""
            SELECT
                crm_leads_crmlead.id as call_eff_crm_lead_id,
                LEFT(DATE_ADD(lv.approved_at, INTERVAL 3 HOUR), 19) AS call_eff_approved_at,
                LEFT(DATE_ADD(lv.canceled_at, INTERVAL 3 HOUR), 19) AS call_eff_canceled_at,
                lv_op.username as lv_username,
                uu.id as call_eff_operator_id,
                lv_status.status_verbose as call_eff_status_verbose,
                lv_status.status_group as call_eff_status_group,
                offer.id as offer_id,
                offer.name as offer_name,
                group_offer.name as category_name,
                tl_lead.webmaster_id as aff_id
            FROM partners_lvlead lv
            LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = lv.id
            LEFT JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
            LEFT JOIN partners_userbasedonlvoperator pu ON pu.operator_id = lv.operator_id
            LEFT JOIN users_user uu ON uu.id = pu.user_id
            LEFT JOIN partners_lvleadstatuses AS lv_status ON lv.leadvertex_status_id = lv_status.id
            LEFT JOIN partners_tllead AS tl_lead ON lv.tl_id = tl_lead.external_id
            LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = tl_lead.subsystem_id
            LEFT JOIN partners_offer as offer ON tl_lead.offer_id = offer.id
            LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
            LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
            WHERE 1=1
            AND offer.id IS NOT NULL
            AND lv_op.username IS NOT NULL
            AND group_offer.name NOT IN ({excl_category})
            AND crm_leads_crmlead.id > %s
            AND lv.approved_at >= %s
            AND lv.approved_at < %s
        """
        params = [last_id, date_from, date_to]
        if category_a:
            q += f" AND group_offer.name IN ({category_a})"
        if offer_a:
            q += f" AND offer.id IN ({offer_a})"
        if advertiser:
            q += f" AND LOWER(subsystem.name) IN ({advertiser})"
        if lv_op_a:
            q += f" AND LOWER(lv_op.username) IN ({lv_op_a})"
        if aff_id_a:
            q += f" AND tl_lead.webmaster_id IN ({aff_id_a})"
        q += " ORDER BY crm_leads_crmlead.id ASC LIMIT %s"
        params.append(limit)
        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q, params)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            logger.info(f">>> Лиды батч: {len(results)} (last_id: {last_id})")
            return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f">>> Ошибка батча лидов: {e}")
            return []

    @staticmethod
    def get_leads(v: Dict) -> List[Dict]:
        all_leads = []
        last_id = 0
        batch_size = 3000
        total_loaded = 0
        logger.info(">>> Начало загрузки лидов с курсорной пагинацией...")
        while True:
            batch = DBService.get_leads_batch_exact(v, last_id, batch_size)
            if not batch:
                break
            all_leads.extend(batch)
            total_loaded += len(batch)
            last_id = int(batch[-1]['call_eff_crm_lead_id'])
            logger.info(f">>> Лиды: загружено {total_loaded}...")
            if len(batch) < batch_size:
                break
        logger.info(f">>> ИТОГО загружено лидов: {len(all_leads)}")
        return all_leads

    # =============================================================================
    # КОНТЕЙНЕР ЛИДОВ — БАТЧ ПО id > last_id
    # =============================================================================
    @staticmethod
    def get_leads_container_batch_exact(v: Dict, last_id: int = 0, limit: int = 10000) -> List[Dict]:
        date_from = DBService._to_utc(v.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(v.get('date_to'), "23:59:59")
        advertiser = DBService.prepare_sql_array(v.get('advertiser', []))
        offer_a = DBService.prepare_sql_array(v.get('offer_id', []))
        category_a = DBService.prepare_sql_array(v.get('category', []))
        excl_category = DBService.prepare_sql_array_array(DBService.exclude_category())
        aff_id_a = DBService.prepare_sql_array(v.get('aff_id', []))
        if not date_from or not date_to:
            logger.error("Неверные даты для контейнеров")
            return []
        q = f"""
            SELECT
                crm_leads_crmlead.id lead_container_crm_lead_id,
                crm_leads_crmlead.id call_eff_crm_lead_id,
                LEFT(DATE_ADD(lv.created_at, INTERVAL 3 HOUR), 19) lead_container_created_at,
                LEFT(DATE_ADD(lv.approved_at, INTERVAL 3 HOUR), 19) lead_container_approved_at,
                LEFT(DATE_ADD(lv.canceled_at, INTERVAL 3 HOUR), 19) lead_container_canceled_at,
                LEFT(DATE_ADD(lv.buyout_at, INTERVAL 3 HOUR), 19) lead_container_buyout_at,
                lv_status.status_verbose as lead_container_status_verbose,
                lv_status.status_group as lead_container_status_group,
                pt.is_trash as lead_container_is_trash,
                LEFT(DATE_ADD(lv.created_at, INTERVAL 27 HOUR), 19) lead_container_lead_ttl_till,
                LEFT(DATE_ADD(NOW(), INTERVAL 3 HOUR), 19) as lead_container_now,
                offer.id as offer_id,
                offer.name as offer_name,
                pt.webmaster_id as aff_id,
                null as lv_username,
                group_offer.name as category_name
            FROM partners_lvlead lv
            LEFT JOIN crm_leads_crmlead ON crm_leads_crmlead.lvlead_id = lv.id
            LEFT JOIN partners_tllead pt ON lv.tl_id = pt.external_id
            LEFT JOIN partners_lvleadstatuses AS lv_status ON lv.leadvertex_status_id = lv_status.id
            LEFT JOIN partners_offer as offer ON pt.offer_id = offer.id
            LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
            LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
            LEFT JOIN partners_subsystem AS subsystem ON subsystem.id = pt.subsystem_id
            WHERE 1=1
            AND offer.id IS NOT NULL
            AND group_offer.name NOT IN ({excl_category})
            AND crm_leads_crmlead.id > %s
            AND lv.created_at >= %s
            AND lv.created_at < %s
        """
        params = [last_id, date_from, date_to]
        if category_a:
            q += f" AND group_offer.name IN ({category_a})"
        if offer_a:
            q += f" AND offer.id IN ({offer_a})"
        if advertiser:
            q += f" AND LOWER(subsystem.name) IN ({advertiser})"
        if aff_id_a:
            q += f" AND pt.webmaster_id IN ({aff_id_a})"
        q += " ORDER BY crm_leads_crmlead.id ASC LIMIT %s"
        params.append(limit)
        try:
            with connections['itrade'].cursor() as cursor:
                cursor.execute(q, params)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            logger.info(f">>> Контейнеры батч: {len(results)} (last_id: {last_id})")
            return DBService._convert_decimal_to_float(results)
        except Exception as e:
            logger.error(f">>> Ошибка батча контейнеров: {e}")
            return []

    @staticmethod
    def get_leads_container(v: Dict) -> List[Dict]:
        all_data = []
        last_id = 0
        batch_size = 10000
        total_loaded = 0
        logger.info(">>> Начало загрузки контейнеров лидов...")
        while True:
            batch = DBService.get_leads_container_batch_exact(v, last_id, batch_size)
            if not batch:
                break
            all_data.extend(batch)
            total_loaded += len(batch)
            last_id = int(batch[-1]['lead_container_crm_lead_id'])
            logger.info(f">>> Контейнеры: загружено {total_loaded}...")
            if len(batch) < batch_size:
                break
        logger.info(f">>> ИТОГО загружено контейнеров: {len(all_data)}")
        return all_data