import re
import math
from typing import Dict, List, Any
from lark import Lark, Transformer


class FormulaEngine:
    def __init__(self):
        self.grammar = """
            ?start: expression

            ?expression: term
                | expression "+" term -> add
                | expression "-" term -> subtract

            ?term: factor
                | term "*" factor -> multiply
                | term "/" factor -> divide
                | term "^" factor -> power

            ?factor: number
                | "-" factor -> negative
                | "+" factor -> positive
                | "(" expression ")"
                | cell_reference
                | function_call
                | string

            number: SIGNED_NUMBER
            string: /"[^"]*"/ | /'[^']*'/

            cell_reference: /[A-Z]+[0-9]+/

            function_call: /[A-ZА-Я_]+/ "(" [arguments] ")"

            arguments: expression ("," expression)*

            %import common.SIGNED_NUMBER
            %import common.WS
            %ignore WS
        """

        self.parser = Lark(self.grammar, parser='lalr')

        # Русские и английские функции KPI
        self.functions = {
            # Основные математические
            'SUM': lambda args: sum(args),
            'СУММ': lambda args: sum(args),
            'AVERAGE': lambda args: sum(args) / len(args) if args else 0,
            'СРЗНАЧ': lambda args: sum(args) / len(args) if args else 0,
            'COUNT': lambda args: len(args),
            'СЧЁТ': lambda args: len(args),
            'MAX': lambda args: max(args) if args else 0,
            'МАКС': lambda args: max(args) if args else 0,
            'MIN': lambda args: min(args) if args else 0,
            'МИН': lambda args: min(args) if args else 0,

            # Логические
            'IF': self.if_function,
            'ЕСЛИ': self.if_function,

            # Поисковые
            'VLOOKUP': self.vlookup,
            'ВПР': self.vlookup,

            # Текстовые
            'CONCATENATE': lambda args: ''.join(str(arg) for arg in args),
            'СЦЕПИТЬ': lambda args: ''.join(str(arg) for arg in args),

            # KPI-специфичные функции
            'EFFECTIVE_RATE': self.effective_rate_function,
            'ЭФФЕКТИВНОСТЬ': self.effective_rate_function,
            'APPROVE_RATE': self.approve_rate_function,
            'АППРУВ_ПРОЦЕНТ': self.approve_rate_function,
            'BUYOUT_RATE': self.buyout_rate_function,
            'ВЫКУП_ПРОЦЕНТ': self.buyout_rate_function,
            'CR': self.cr_function,
            'CPL': self.cpl_function,

            # QUERY функции
            'QUERY': self.query_function,
            'ФИЛЬТР': self.query_function,
            'FILTER': self.query_function,
        }

    def safe_div(self, a, b):
        """Безопасное деление"""
        if b is None or b == 0:
            return 0
        return a / b

    def if_function(self, args):
        """Функция ЕСЛИ/IF"""
        if len(args) < 2:
            return None
        condition = bool(args[0])
        true_value = args[1]
        false_value = args[2] if len(args) > 2 else None
        return true_value if condition else false_value

    def vlookup(self, args):
        """Полная реализация функции ВПР/VLOOKUP"""
        if len(args) < 3:
            return None

        lookup_value = args[0]
        table_data = args[1]  # [[col1, col2, ...], ...]
        col_index = int(args[2]) - 1  # Excel uses 1-based indexing
        range_lookup = args[3] if len(args) > 3 else True

        if not isinstance(table_data, list) or not table_data:
            return None

        # Поиск в таблице
        for row in table_data:
            if not row:
                continue

            if range_lookup and isinstance(lookup_value, (int, float)):
                # Приблизительный поиск для чисел
                if row[0] <= lookup_value:
                    if col_index < len(row):
                        return row[col_index]
            else:
                # Точный поиск
                if row[0] == lookup_value:
                    if col_index < len(row):
                        return row[col_index]

        return None

    def query_function(self, args):
        """Полная реализация QUERY/ФИЛЬТР функции"""
        if len(args) < 2:
            return None

        data_range = args[0]
        query = args[1].upper()

        if not isinstance(data_range, list):
            return data_range

        # Простой парсер SQL-like запросов
        if 'SELECT' in query and 'WHERE' in query:
            return self._execute_sql_like_query(data_range, query)
        elif 'FILTER' in query or 'ФИЛЬТР' in query:
            return self._execute_filter_query(data_range, query)

        return data_range

    def _execute_sql_like_query(self, data, query):
        """Выполнение SQL-подобных запросов"""
        # Извлекаем условия из запроса
        conditions = []
        if 'WHERE' in query:
            where_part = query.split('WHERE')[1].split('ORDER BY')[0].strip()
            conditions = self._parse_conditions(where_part)

        # Фильтруем данные
        filtered_data = []
        for row in data:
            if self._evaluate_conditions(row, conditions):
                filtered_data.append(row)

        return filtered_data

    def _execute_filter_query(self, data, query):
        """Выполнение FILTER запросов"""
        # Простая реализация фильтрации
        conditions = []
        if '=' in query:
            parts = query.split('=')
            if len(parts) == 2:
                col = parts[0].replace('FILTER', '').replace('ФИЛЬТР', '').strip()
                value = parts[1].strip().strip("'")
                conditions.append(('equals', col, value))

        filtered_data = []
        for row in data:
            if self._evaluate_conditions(row, conditions):
                filtered_data.append(row)

        return filtered_data

    def _parse_conditions(self, where_clause):
        """Парсинг условий WHERE"""
        conditions = []
        # Простая реализация для базовых условий
        if '=' in where_clause:
            col, value = where_clause.split('=', 1)
            conditions.append(('equals', col.strip(), value.strip().strip("'")))
        elif '>' in where_clause:
            col, value = where_clause.split('>', 1)
            conditions.append(('greater', col.strip(), float(value.strip())))
        elif '<' in where_clause:
            col, value = where_clause.split('<', 1)
            conditions.append(('less', col.strip(), float(value.strip())))

        return conditions

    def _evaluate_conditions(self, row, conditions):
        """Проверка условий для строки"""
        for condition in conditions:
            op, col, value = condition
            col_index = self._column_to_index(col) if isinstance(col, str) else col

            if col_index >= len(row):
                return False

            cell_value = row[col_index]

            if op == 'equals':
                if str(cell_value) != str(value):
                    return False
            elif op == 'greater':
                if float(cell_value) <= float(value):
                    return False
            elif op == 'less':
                if float(cell_value) >= float(value):
                    return False

        return True

    def _column_to_index(self, col_letter):
        """Конвертация букв колонки в индекс"""
        col_letter = col_letter.upper().replace('COL', '').replace('$', '')
        index = 0
        for char in col_letter:
            index = index * 26 + (ord(char) - ord('A') + 1)
        return index - 1

    def effective_rate_function(self, args):
        """Расчет эффективности: effective_calls / effective_leads"""
        if len(args) >= 2:
            return self.safe_div(args[0], args[1])
        return 0

    def approve_rate_function(self, args):
        """Расчет процента аппрува"""
        if len(args) >= 2:
            return self.safe_div(args[0], args[1]) * 100
        return 0

    def buyout_rate_function(self, args):
        """Расчет процента выкупа"""
        if len(args) >= 2:
            return self.safe_div(args[0], args[1]) * 100
        return 0

    def cr_function(self, args):
        """Conversion Rate"""
        if len(args) >= 2:
            return self.safe_div(args[0], args[1]) * 100
        return 0

    def cpl_function(self, args):
        """Cost Per Lead"""
        if len(args) >= 2:
            return self.safe_div(args[0], args[1])
        return 0

    def extract_dependencies(self, formula: str) -> List[Dict]:
        """Извлечение зависимостей из формулы"""
        dependencies = []
        cell_refs = re.findall(r'[A-Z]+[0-9]+', formula.upper())

        for ref in cell_refs:
            col = ''.join(filter(str.isalpha, ref))
            row = ''.join(filter(str.isdigit, ref))

            # Конвертация буквенного обозначения колонки в число
            col_num = 0
            for char in col:
                col_num = col_num * 26 + (ord(char) - ord('A') + 1)

            dependencies.append({
                'ref': ref,
                'row': int(row),
                'col': col_num - 1  # 0-based индекс
            })

        return dependencies

    def evaluate_formula(self, formula: str, sheet_data: Dict) -> Any:
        """Вычисление формулы с улучшенной обработкой ошибок"""
        try:
            if not formula or not formula.strip():
                return ""


            if formula.startswith('='):
                formula = formula[1:]


            formula = self.translate_russian_functions(formula)


            if self._has_circular_reference(formula, sheet_data):
                return "#CIRCULAR_REF"

            tree = self.parser.parse(formula)
            result = self._evaluate_tree(tree, sheet_data)


            if isinstance(result, float):
                if result == int(result):
                    return int(result)
                return round(result, 4)

            return result

        except Exception as e:
            error_msg = f"#ERROR: {str(e)}"
            print(f"❌ Formula error: {formula} -> {error_msg}")
            return error_msg

    def _has_circular_reference(self, formula: str, sheet_data: Dict) -> bool:
        """Проверка на циклические ссылки"""
        # Базовая реализация - можно расширить
        dependencies = self.extract_dependencies(formula)
        # Логика проверки циклических ссылок
        return False

    def translate_russian_functions(self, formula: str) -> str:
        """Перевод русских названий функций в английские"""
        translations = {
            'СУММ': 'SUM',
            'СРЗНАЧ': 'AVERAGE',
            'СЧЁТ': 'COUNT',
            'МАКС': 'MAX',
            'МИН': 'MIN',
            'ЕСЛИ': 'IF',
            'ВПР': 'VLOOKUP',
            'СЦЕПИТЬ': 'CONCATENATE',
            'ЭФФЕКТИВНОСТЬ': 'EFFECTIVE_RATE',
            'АППРУВ_ПРОЦЕНТ': 'APPROVE_RATE',
            'ВЫКУП_ПРОЦЕНТ': 'BUYOUT_RATE',
            'ФИЛЬТР': 'QUERY',
        }

        for rus, eng in translations.items():
            formula = re.sub(rf'\b{rus}\b', eng, formula, flags=re.IGNORECASE)

        return formula

    def _evaluate_tree(self, tree, sheet_data):
        """Рекурсивное вычисление дерева разбора"""
        if tree.data == 'number':
            return float(tree.children[0])

        elif tree.data == 'string':
            return str(tree.children[0])[1:-1]  # Убираем кавычки

        elif tree.data == 'cell_reference':
            return self._get_cell_value(tree.children[0], sheet_data)

        elif tree.data == 'function_call':
            func_name = tree.children[0].upper()
            args = []

            if len(tree.children) > 1:
                args_tree = tree.children[1]
                if args_tree.data == 'arguments':
                    for child in args_tree.children:
                        args.append(self._evaluate_tree(child, sheet_data))

            if func_name in self.functions:
                return self.functions[func_name](args)
            else:
                raise ValueError(f"Неизвестная функция: {func_name}")

        elif tree.data in ['add', 'subtract', 'multiply', 'divide', 'power']:
            left = self._evaluate_tree(tree.children[0], sheet_data)
            right = self._evaluate_tree(tree.children[1], sheet_data)

            if tree.data == 'add':
                return left + right
            elif tree.data == 'subtract':
                return left - right
            elif tree.data == 'multiply':
                return left * right
            elif tree.data == 'divide':
                return self.safe_div(left, right)
            elif tree.data == 'power':
                return left ** right

        elif tree.data == 'negative':
            return -self._evaluate_tree(tree.children[0], sheet_data)

        elif tree.data == 'positive':
            return self._evaluate_tree(tree.children[0], sheet_data)

        else:
            # Для выражений в скобках
            return self._evaluate_tree(tree.children[0], sheet_data)

    def _get_cell_value(self, cell_ref: str, sheet_data: Dict) -> float:
        """Получение значения ячейки по ссылке"""
        col = ''.join(filter(str.isalpha, cell_ref))
        row = ''.join(filter(str.isdigit, cell_ref))

        # Конвертация буквенного обозначения колонки в число
        col_num = 0
        for char in col:
            col_num = col_num * 26 + (ord(char) - ord('A') + 1)

        row_num = int(row) - 1  # 0-based индекс
        col_num = col_num - 1  # 0-based индекс

        # Получение значения из данных листа
        if 'celldata' in sheet_data:
            for cell in sheet_data['celldata']:
                if cell.get('r') == row_num and cell.get('c') == col_num:
                    value = cell.get('v')
                    if value is None:
                        return 0.0
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return 0.0

        return 0.0