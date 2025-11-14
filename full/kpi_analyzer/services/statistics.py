from typing import Dict, List, Any, Optional
from datetime import datetime
from decimal import Decimal
import logging

from .engine_leads_processing import EngineLeadsProcessing  # ← КРИТИЧЕСКИЙ ИМПОРТ

logger = logging.getLogger(__name__)


def safe_div(numerator, denominator, default=0.0):
    """Безопасное деление с обработкой всех ошибок"""
    try:
        if denominator is None or denominator == 0:
            return default
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return default


def parse_date_time(date_str: str) -> Optional[datetime]:
    """Парсинг даты из строки формата 'YYYY-MM-DD HH:MM:SS'"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


MINUTE_MLSEC = 60 * 1000


class GlobalLeadContainerStat:
    class Lead:
        def __init__(self, sql: Dict):
            self.crm_id = sql.get('lead_container_crm_lead_id')
            self.offer_id = sql.get('offer_id')
            self.aff_id = sql.get('aff_id')
            self.category_name = sql.get('category_name')
            self.created_at = sql.get('lead_container_created_at')
            self.approved_at = sql.get('lead_container_approved_at')
            self.canceled_at = sql.get('lead_container_canceled_at')  # ← ДОБАВЛЕНО
            self.buyout_at = sql.get('lead_container_buyout_at')
            self.is_trash = bool(int(sql.get('lead_container_is_trash', 0) or 0))
            self.status_group = sql.get('lead_container_status_group', '').lower()
            self.status_verbose = sql.get('lead_container_status_verbose', '').lower()
            self.is_fake_approve = False
            self.is_approve = False
            self.is_buyout = False

        def finalize(self):  # ← ИСПРАВЛЕНО: finalyze → finalize
            """Фильтрация фейковых аппрувов"""
            if not self.approved_at or self.approved_at == '':
                return

            fake_reason = EngineLeadsProcessing.is_fake_approve({
                'status_verbose': self.status_verbose,
                'status_group': self.status_group,
                'approved_at': self.approved_at,
                'canceled_at': self.canceled_at or ''
            })

            if fake_reason:
                logger.debug(f"Фейковый аппрув отсеян: {self.crm_id}, причина: {fake_reason}")
                self.is_fake_approve = True
                return

            self.is_approve = True
            if self.buyout_at and self.buyout_at != '':
                self.is_buyout = True

    def __init__(self):
        self.leads: Dict[int, 'GlobalLeadContainerStat.Lead'] = {}
        self.leads_count = 0
        self.leads_non_trash_count = 0
        self.leads_approved_count = 0
        self.leads_buyout_count = 0
        self.finalized = False  # ← ИСПРАВЛЕНО: finalyzed → finalized

    def push_lead(self, sql_data: Dict):
        """Добавление лида с фильтрацией дубликатов"""
        lead_id = sql_data.get('lead_container_crm_lead_id')
        if not lead_id:
            return
        if lead_id in self.leads:
            return  # Дубликат — пропускаем
        self.leads[lead_id] = self.Lead(sql_data)

    def finalize(self):  # ← ИСПРАВЛЕНО: finalyze → finalize
        """Финализация: считаем только валидные лиды"""
        if self.finalized:
            return
        self.finalized = True

        self.leads_count = len(self.leads)
        for lead in self.leads.values():
            lead.finalize()  # ← теперь вызываем finalize()

            # Пропускаем trash и фейки
            if lead.is_trash or lead.is_fake_approve:
                continue

            self.leads_non_trash_count += 1
            if lead.is_approve:
                self.leads_approved_count += 1
            if lead.is_buyout:
                self.leads_buyout_count += 1