from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

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