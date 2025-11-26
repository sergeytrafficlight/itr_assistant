from django.db import connections
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from functools import wraps
import math

logger = logging.getLogger(__name__)


class DBService:
    EXCLUDED_CATEGORIES = ['Архив', 'Входящая линия']
    BAD_APPROVE_STATUS = ['отправить позже', 'отмен', 'предоплаты', '4+ дней', '4 день', '3 день', '2 день', '1 день',
                          'перезвон']
    GOOD_APPROVE_STATUS_GROUP = ['accepted', 'shipped', 'paid', 'return']

    # Настройки retry
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    BATCH_SIZE = 1000

    @staticmethod
    def retry_on_db_error(func):
        """Декоратор для повторных попыток при ошибках БД"""

        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(DBService.MAX_RETRIES + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < DBService.MAX_RETRIES:
                        wait_time = DBService.RETRY_DELAY * (2 ** attempt)
                        logger.warning(f"Попытка {attempt + 1}/{DBService.MAX_RETRIES + 1} не удалась. "
                                       f"Ошибка: {e}. Повтор через {wait_time}с")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Все {DBService.MAX_RETRIES + 1} попыток не удались. Последняя ошибка: {e}")
            raise last_exception

        return wrapper

    @staticmethod
    def _prepare_in_values(values: List[Any]) -> Tuple[str, List[Any]]:
        if not values:
            return "1=0", []
        placeholders = ",".join(["%s"] * len(values))
        return f"({placeholders})", [str(v).strip().replace("'", "''") if isinstance(v, str) else v for v in values]

    @staticmethod
    def _to_utc(date_str: Optional[str], time_part: str = "00:00:00") -> Optional[str]:
        if not date_str:
            return None
        try:
            format_str = "%Y-%m-%d %H:%M:%S" if " " in date_str else f"%Y-%m-%d {time_part}"
            dt = datetime.strptime(date_str if " " in date_str else f"{date_str} {time_part}", format_str)
            dt_utc = dt - timedelta(hours=3)
            return dt_utc.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Ошибка парсинга даты: {date_str} → {e}")
            return None

    @staticmethod
    @retry_on_db_error
    def _execute_query(query: str, params: List[Any]) -> List[Dict]:
        try:
            start = time.time()
            with connections['itrade'].cursor() as cursor:
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]

            duration = time.time() - start
            logger.info(f">>> Запрос выполнен за {duration:.2f}с, строк: {len(results)}")
            return results
        except Exception as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            raise

    @staticmethod
    def _process_in_batches(data: List[Dict], batch_size: int, process_func: callable) -> List[Dict]:
        if not data:
            return []

        results = []
        total_batches = math.ceil(len(data) / batch_size)

        for batch_num in range(total_batches):
            start_idx = batch_num * batch_size
            end_idx = start_idx + batch_size
            batch = data[start_idx:end_idx]

            logger.info(f"Обработка батча {batch_num + 1}/{total_batches}, размер: {len(batch)}")

            try:
                batch_results = process_func(batch)
                results.extend(batch_results)
            except Exception as e:
                logger.error(f"Ошибка обработки батча {batch_num + 1}: {e}")
                continue

        return results

    @staticmethod
    def get_kpi_plans_data(filters: Optional[Dict] = None) -> List[Dict]:
        query = """
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
          ORDER BY period_date ASC
          """
        return DBService._execute_query(query, [])

    @staticmethod
    def get_offers(filters: Dict) -> List[Dict]:
        offer_ids = filters.get('offer_id', [])
        categories = filters.get('category', [])

        query = """
        SELECT
            partners_offer.id as id,
            partners_offer.name as name,
            group_offer.name as category_name
        FROM partners_offer
        LEFT JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = partners_offer.id 
        LEFT JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id 
        WHERE 1=1
        AND group_offer.name NOT IN ({})
        """.format(",".join(["%s"] * len(DBService.EXCLUDED_CATEGORIES)))

        params = DBService.EXCLUDED_CATEGORIES.copy()

        if categories:
            placeholders, cat_params = DBService._prepare_in_values(categories)
            query += f" AND group_offer.name IN {placeholders}"
            params.extend(cat_params)

        if offer_ids:
            placeholders, offer_params = DBService._prepare_in_values(offer_ids)
            query += f" AND partners_offer.id IN {placeholders}"
            params.extend(offer_params)

        return DBService._execute_query(query, params)

    @staticmethod
    def get_calls(filters: Dict) -> List[Dict]:
        date_from = DBService._to_utc(filters.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(filters.get('date_to'), "23:59:59")

        if not date_from or not date_to:
            logger.error("Не указаны даты начала или окончания периода")
            return []

        advertiser = [a.lower() for a in filters.get('advertiser', [])]
        offer_ids = filters.get('offer_id', [])
        categories = filters.get('category', [])
        lv_ops = [op.lower() for op in filters.get('lv_op', [])]
        aff_ids = filters.get('aff_id', [])

        query = """
        SELECT
            pae.id as call_eff_id,
            ccd.id as call_eff_crm_id,
            po.id as call_eff_offer_id,
            po.name as offer_name,
            pae.uniqueid as call_eff_uniqueid,
            LEFT(DATE_ADD(pae.calldate, INTERVAL 3 HOUR), 10) AS call_eff_calldate,
            ccd.crm_lead_id as call_eff_crm_lead_id,
            uu.id as call_eff_operator_id,
            pae.billsec as call_eff_billsec,
            ccd.oktell_duration as call_eff_billsec_exact,
            ccd.oktell_anti_robot as call_eff_robo_detected,
            lv_op.username as lv_username,
            group_offer.name as category_name,
            pt.webmaster_id as call_eff_affiliate_id
        FROM partners_atscallevent pae FORCE INDEX (calldate, lvlead_id)
        INNER JOIN partners_lvlead lv FORCE INDEX (tl_id, operator_id) ON pae.lvlead_id = lv.id
        INNER JOIN partners_tllead pt FORCE INDEX (external_id_2, offer_id, affiliate_id) ON lv.tl_id = pt.external_id
        INNER JOIN partners_offer po FORCE INDEX (PRIMARY) ON pt.offer_id = po.id
        INNER JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = po.id
        INNER JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
        LEFT JOIN crm_call_calldata ccd ON ccd.id = pae.assigned_call_data_id
        LEFT JOIN partners_lvoperator lv_op FORCE INDEX (PRIMARY) ON lv_op.id = pae.lvoperator_id
        LEFT JOIN partners_userbasedonlvoperator pu ON pu.operator_id = pae.lvoperator_id
        LEFT JOIN users_user uu ON uu.id = pu.user_id
        LEFT JOIN users_department ud ON ud.id = uu.department_id
        LEFT JOIN partners_subsystem subsystem ON subsystem.id = pt.subsystem_id
        LEFT JOIN crm_call_oktelltask ccot ON pae.oktell_task_id = ccot.id
        WHERE 1=1
        AND pae.calldate BETWEEN %s AND %s
        AND pae.billsec >= 30
        AND group_offer.name NOT IN ({})
        AND po.id IS NOT NULL
        AND lv_op.username IS NOT NULL
        AND ((ud.name LIKE '%%_НП_%%' OR ud.name LIKE '%%_СП_%%') OR ccot.type = 'new_sales')
        """.format(",".join(["%s"] * len(DBService.EXCLUDED_CATEGORIES)))

        params = [date_from, date_to] + DBService.EXCLUDED_CATEGORIES

        if categories and categories != ['']:
            placeholders, cat_params = DBService._prepare_in_values(categories)
            query += f" AND group_offer.name IN {placeholders}"
            params.extend(cat_params)

        if offer_ids and offer_ids != ['']:
            placeholders, offer_params = DBService._prepare_in_values(offer_ids)
            query += f" AND po.id IN {placeholders}"
            params.extend(offer_params)

        if advertiser and advertiser != ['']:
            placeholders, adv_params = DBService._prepare_in_values(advertiser)
            query += f" AND LOWER(subsystem.name) IN {placeholders}"
            params.extend(adv_params)

        if lv_ops and lv_ops != ['']:
            placeholders, lv_params = DBService._prepare_in_values(lv_ops)
            query += f" AND LOWER(lv_op.username) IN {placeholders}"
            params.extend(lv_params)

        if aff_ids and aff_ids != ['']:
            placeholders, aff_params = DBService._prepare_in_values(aff_ids)
            query += f" AND pt.webmaster_id IN {placeholders}"
            params.extend(aff_params)

        query += " ORDER BY pae.calldate ASC"

        return DBService._execute_query(query, params)

    @staticmethod
    def get_leads(filters: Dict) -> List[Dict]:
        date_from = DBService._to_utc(filters.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(filters.get('date_to'), "23:59:59")

        if not date_from or not date_to:
            logger.error("Не указаны даты начала или окончания периода")
            return []

        advertiser = [a.lower() for a in filters.get('advertiser', [])]
        offer_ids = filters.get('offer_id', [])
        categories = filters.get('category', [])
        lv_ops = [op.lower() for op in filters.get('lv_op', [])]
        aff_ids = filters.get('aff_id', [])

        # ОПТИМИЗИРОВАННЫЙ ЗАПРОС
        query = """
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
        AND group_offer.name NOT IN ({})
        AND lv.approved_at BETWEEN %s AND %s
        """.format(",".join(["%s"] * len(DBService.EXCLUDED_CATEGORIES)))

        params = DBService.EXCLUDED_CATEGORIES + [date_from, date_to]

        if categories:
            placeholders, cat_params = DBService._prepare_in_values(categories)
            query += f" AND group_offer.name IN {placeholders}"
            params.extend(cat_params)

        if offer_ids:
            placeholders, offer_params = DBService._prepare_in_values(offer_ids)
            query += f" AND offer.id IN {placeholders}"
            params.extend(offer_params)

        if advertiser:
            placeholders, adv_params = DBService._prepare_in_values(advertiser)
            query += f" AND LOWER(subsystem.name) IN {placeholders}"
            params.extend(adv_params)

        if lv_ops:
            placeholders, lv_params = DBService._prepare_in_values(lv_ops)
            query += f" AND LOWER(lv_op.username) IN {placeholders}"
            params.extend(lv_params)

        if aff_ids:
            placeholders, aff_params = DBService._prepare_in_values(aff_ids)
            query += f" AND tl_lead.webmaster_id IN {placeholders}"
            params.extend(aff_params)

        query += " ORDER BY lv.approved_at ASC"

        return DBService._execute_query(query, params)

    @staticmethod
    def get_leads_container(filters: Dict) -> List[Dict]:
        date_from = DBService._to_utc(filters.get('date_from'), "00:00:00")
        date_to = DBService._to_utc(filters.get('date_to'), "23:59:59")

        if not date_from or not date_to:
            logger.error("Не указаны даты начала или окончания периода")
            return []

        advertiser = [a.lower() for a in filters.get('advertiser', [])]
        offer_ids = filters.get('offer_id', [])
        categories = filters.get('category', [])
        aff_ids = filters.get('aff_id', [])
        lv_ops = [op.lower() for op in filters.get('lv_op', [])]

        # ОПТИМИЗИРОВАННЫЙ ЗАПРОС
        query = """
        SELECT
            clc.id as lead_container_crm_lead_id,
            clc.id as call_eff_crm_lead_id,
            LEFT(DATE_ADD(lv.created_at, INTERVAL 3 HOUR), 19) as lead_container_created_at,
            LEFT(DATE_ADD(lv.approved_at, INTERVAL 3 HOUR), 19) as lead_container_approved_at,
            LEFT(DATE_ADD(lv.canceled_at, INTERVAL 3 HOUR), 19) as lead_container_canceled_at,
            LEFT(DATE_ADD(lv.buyout_at, INTERVAL 3 HOUR), 19) as lead_container_buyout_at,
            lv_status.status_verbose as lead_container_status_verbose,
            lv_status.status_group as lead_container_status_group,
            pt.is_trash as lead_container_is_trash,
            LEFT(DATE_ADD(lv.created_at, INTERVAL 27 HOUR), 19) as lead_container_lead_ttl_till,
            LEFT(DATE_ADD(NOW(), INTERVAL 3 HOUR), 19) as lead_container_now,
            offer.id as offer_id,
            offer.name as offer_name,
            pt.webmaster_id as aff_id,
            lv_op.username as lv_username,
            group_offer.name as category_name
        FROM partners_lvlead lv
        INNER JOIN partners_tllead pt ON lv.tl_id = pt.external_id
        INNER JOIN partners_offer offer ON pt.offer_id = offer.id
        INNER JOIN partners_assignedoffer assigned_offer ON assigned_offer.offer_id = offer.id
        INNER JOIN partners_groupoffer group_offer ON assigned_offer.group_id = group_offer.id
        LEFT JOIN crm_leads_crmlead clc ON clc.lvlead_id = lv.id
        LEFT JOIN partners_lvleadstatuses lv_status ON lv.leadvertex_status_id = lv_status.id
        LEFT JOIN partners_subsystem subsystem ON subsystem.id = pt.subsystem_id
        LEFT JOIN partners_lvoperator lv_op ON lv_op.id = lv.operator_id
        WHERE 1=1
        AND offer.id IS NOT NULL
        AND group_offer.name NOT IN ({})
        AND lv.created_at BETWEEN %s AND %s
        """.format(",".join(["%s"] * len(DBService.EXCLUDED_CATEGORIES)))

        params = DBService.EXCLUDED_CATEGORIES + [date_from, date_to]

        if categories:
            placeholders, cat_params = DBService._prepare_in_values(categories)
            query += f" AND group_offer.name IN {placeholders}"
            params.extend(cat_params)

        if offer_ids:
            placeholders, offer_params = DBService._prepare_in_values(offer_ids)
            query += f" AND offer.id IN {placeholders}"
            params.extend(offer_params)

        if advertiser:
            placeholders, adv_params = DBService._prepare_in_values(advertiser)
            query += f" AND LOWER(subsystem.name) IN {placeholders}"
            params.extend(adv_params)

        if aff_ids:
            placeholders, aff_params = DBService._prepare_in_values(aff_ids)
            query += f" AND pt.webmaster_id IN {placeholders}"
            params.extend(aff_params)

        if lv_ops:
            placeholders, lv_params = DBService._prepare_in_values(lv_ops)
            query += f" AND LOWER(lv_op.username) IN {placeholders}"
            params.extend(lv_params)

        logger.info(f"Запрос контейнеров лидов за период: {date_from} - {date_to}")
        return DBService._execute_query(query, params)

    @staticmethod
    def is_fake_approve(lead_dict: Dict) -> str:
        try:
            required_fields = ['status_verbose', 'status_group', 'approved_at', 'canceled_at']
            for field in required_fields:
                if field not in lead_dict:
                    return f"Отсутствует поле: {field}"

            status_verbose = lead_dict.get('status_verbose', '')
            status_group = lead_dict.get('status_group', '')
            approved_at = lead_dict.get('approved_at', '')
            canceled_at = lead_dict.get('canceled_at', '')

            if status_group not in DBService.GOOD_APPROVE_STATUS_GROUP:
                return f"Группа статусов: {status_group}"

            status_verbose_lower = status_verbose.lower()
            if 'отправить позже' in status_verbose_lower:
                return "Заказ в статусе 'Отправить позже'"

            if approved_at and canceled_at and canceled_at.strip():
                try:
                    approved_dt = datetime.strptime(approved_at, '%Y-%m-%d %H:%M:%S')
                    canceled_dt = datetime.strptime(canceled_at, '%Y-%m-%d %H:%M:%S')
                    if canceled_dt >= approved_dt:
                        return f"Заказ отменён ({canceled_at}) после подтверждения ({approved_at})"
                except ValueError:
                    if canceled_at >= approved_at:
                        return f"Заказ отменён ({canceled_at}) после подтверждения ({approved_at})"

            if not approved_at or approved_at.strip() == '':
                return "Отсутствует дата подтверждения"

            for bad_status in DBService.BAD_APPROVE_STATUS:
                if bad_status in status_verbose_lower:
                    return f"Заказ в статусе: {status_verbose}"

            return ""

        except Exception as e:
            logger.error(f"Ошибка в is_fake_approve: {e}")
            return f"Ошибка проверки: {str(e)}"

    @staticmethod
    def is_fake_buyout(lead_dict: Dict) -> str:
        try:
            if 'status_group' not in lead_dict:
                return "Отсутствует поле: status_group"
            if 'buyout_at' not in lead_dict:
                return "Отсутствует поле: buyout_at"

            status_group = lead_dict.get('status_group', '')
            buyout_at = lead_dict.get('buyout_at', '')

            if status_group != 'paid':
                return "Лид не в группе статусов paid"
            if not buyout_at or buyout_at.strip() == '':
                return "Отсутствует дата выкупа"

            return ""

        except Exception as e:
            logger.error(f"Ошибка в is_fake_buyout: {e}")
            return f"Ошибка проверки: {str(e)}"