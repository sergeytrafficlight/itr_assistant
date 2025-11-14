from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Cell, CellDependency
from .services.formula_engine import FormulaEngine


@receiver(post_save, sender=Cell)
def update_cell_dependencies(sender, instance, **kwargs):
    """Обновление зависимостей ячейки при сохранении"""
    try:
        formula_engine = FormulaEngine()

        if instance.formula:
            dependencies = formula_engine.extract_dependencies(instance.formula)

            # Удаляем старые зависимости
            CellDependency.objects.filter(cell=instance).delete()

            # Создаем новые зависимости
            for dep_ref in dependencies:
                try:
                    depends_on_cell = Cell.objects.get(
                        sheet=instance.sheet,
                        row=dep_ref['row'],
                        col=dep_ref['col']
                    )
                    CellDependency.objects.create(
                        cell=instance,
                        depends_on=depends_on_cell
                    )
                except Cell.DoesNotExist:
                    continue
    except Exception as e:
        print(f"Ошибка обновления зависимостей: {e}")


@receiver(post_save, sender=Cell)
def recalculate_dependent_cells(sender, instance, **kwargs):
    """Пересчет зависимых ячеек при изменении"""
    # Находим ячейки, которые зависят от текущей
    dependent_cells = Cell.objects.filter(
        dependencies__depends_on=instance
    ).distinct()

    formula_engine = FormulaEngine()
    for cell in dependent_cells:
        if cell.formula:
            try:
                result = formula_engine.evaluate_formula(cell.formula, cell.sheet)
                cell.computed_value = str(result)
                cell.save(update_fields=['computed_value'])
            except Exception as e:
                cell.computed_value = f"#ERROR: {str(e)}"
                cell.save(update_fields=['computed_value'])


@receiver(post_delete, sender=Cell)
def cleanup_dependencies(sender, instance, **kwargs):
    """Очистка зависимостей при удалении ячейки"""
    CellDependency.objects.filter(cell=instance).delete()
    CellDependency.objects.filter(depends_on=instance).delete()