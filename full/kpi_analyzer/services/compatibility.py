from datetime import datetime, date


class GoogleScriptCompatibility:
    """Сервисные функции для совместимости с Google Script"""

    BLANK_KEY = ""  # Аналог BLANK_KEY из Google Script

    @staticmethod
    def prepare_sql_array(values):
        """Точная реализация prepare_sql_array из эталона"""
        if not values:
            return ""
        if isinstance(values, str):
            values = [values]

        # Фильтрация и подготовка значений как в эталоне
        prepared_values = []
        for v in values:
            if v is None:
                continue
            str_val = str(v).strip()
            if str_val:
                # Экранирование кавычек и специальных символов
                str_val = str_val.replace("'", "''")
                prepared_values.append(f"'{str_val}'")

        return ",".join(prepared_values)

    @staticmethod
    def prepare_sql_array_array(values):
        """Точная реализация prepare_sql_array_array"""
        return GoogleScriptCompatibility.prepare_sql_array(values)

    @staticmethod
    def normalize_datetime(datetime_str, time_part="00:00:00"):
        """Нормализация даты-времени как в эталоне"""
        if not datetime_str:
            return ""

        # Базовая реализация - в эталоне сложнее
        try:
            if " " in datetime_str:
                return datetime_str  # Уже содержит время
            else:
                return f"{datetime_str} {time_part}"
        except:
            return datetime_str

    @staticmethod
    def print_float(value, precision=4):
        """Форматирование float как в Google Script"""
        if value is None:
            return ""
        try:
            num = float(value)
            if num == int(num):
                return str(int(num))
            return f"{num:.{precision}f}".rstrip('0').rstrip('.')
        except (ValueError, TypeError):
            return str(value)

    @staticmethod
    def print_percent(prefix, numerator, denominator, suffix):
        """Форматирование процентов как в эталоне"""
        if denominator is None or denominator == 0:
            return ""
        percent = (numerator / denominator) * 100
        return f"{prefix}{percent:.2f}%{suffix}"

    @staticmethod
    def safe_div(numerator, denominator, default=0.0):
        """Безопасное деление как в эталоне"""
        if denominator is None or denominator == 0:
            return default
        return numerator / denominator