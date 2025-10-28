from django.shortcuts import render
from django_tables2 import SingleTableView
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.views import FilterView
from django.db.models import Count
from django_pivot.pivot import pivot
from .tables import OfferTable, LeadTable, CallTable, KpiPlanTable
from .models import Offer, Lead, Call, KpiPlan
from .kpi_analyzer import OpAnalyzeKpiV2
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView

class OfferTableView(LoginRequiredMixin, FilterView, SingleTableView):
    model = Offer
    table_class = OfferTable
    template_name = 'kpi_analyzer/table.html'

class LeadTableView(LoginRequiredMixin, FilterView, SingleTableView):
    model = Lead
    table_class = LeadTable
    template_name = 'kpi_analyzer/table.html'

class CallTableView(LoginRequiredMixin, FilterView, SingleTableView):
    model = Call
    table_class = CallTable
    template_name = 'kpi_analyzer/table.html'

class KpiPlanTableView(LoginRequiredMixin, FilterView, SingleTableView):
    model = KpiPlan
    table_class = KpiPlanTable
    template_name = 'kpi_analyzer/table.html'

class LeadPivotView(LoginRequiredMixin, TemplateView):
    template_name = 'kpi_analyzer/pivot_table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            qs = Lead.objects.values('lv_username', 'category_name').annotate(count=Count('call_eff_crm_lead_id'))
            if qs.exists():
                pivot_data = pivot(
                    queryset=qs,
                    rows=['lv_username'],
                    columns=['category_name'],
                    values='count',
                    aggfunc='sum'
                )
                context['pivot_table'] = pivot_data._repr_html_()
            else:
                context['pivot_message'] = "Нет данных для сводной таблицы."
        except Exception as e:
            context['pivot_error'] = str(e)
        return context

class KpiSummaryView(LoginRequiredMixin, TemplateView):
    template_name = 'kpi_analyzer/kpi_summary.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        stat = OpAnalyzeKpiV2.Stat()
        for call in Call.objects.all():
            stat.push_call(call)
        for lead in Lead.objects.all():
            stat.push_lead(lead)
        for offer in Offer.objects.all():
            stat.push_offer(offer)
        stat.finalyze()

        pd = []
        for category in stat.category.values():
            OpAnalyzeKpiV2.print_pd_category(pd, category)
            for offer in category.offer.values():
                OpAnalyzeKpiV2.print_pd_offer(pd, offer, category)
            for aff in category.aff.values():
                OpAnalyzeKpiV2.print_pd_aff(pd, aff)
            for operator in category.operator.values():
                OpAnalyzeKpiV2.print_pd_operator(pd, operator)

        context['kpi_data'] = stat.category
        context['recommendations'] = [stat.category[c].recommended_effeciency for c in stat.category]
        context['pd'] = pd
        return context

class TimesheetView(APIView):
    def get(self, request):
        from .kpi_analyzer import Timesheet
        timesheet = Timesheet(minutes_per_period=5)
        calls = Call.objects.all()
        for call in calls:
            if call.created_at and call.duration is not None:
                created_at_str = call.created_at.strftime("%Y-%m-%d %H:%M:%S")
                timesheet.push_call(call.lv_username, created_at_str, call.duration)
        return Response({
            "total_working_time_minutes": timesheet.get_working_time_minutes(),
            "operators_count": timesheet.get_operators_count(),
            "operators": timesheet.operators
        })

class KpiAnalyzerView(APIView):
    def get(self, request):
        stat = OpAnalyzeKpiV2.Stat()
        stat.finalyze()
        operators = stat.category.get('Test Category', {}).get('operator_sorted', [])
        recommended = OpAnalyzeKpiV2.get_recommended_effeciency(
            operators,
            OpAnalyzeKpiV2.get_operators_for_recommendations(operators).value
        )
        return Response({
            "recommended_efficiency": recommended.value,
            "comment": recommended.comment,
            "data": "Full KPI analysis from sheet"
        })

@login_required
def kpi_analyze_html(request):
    return render(request, 'kpi_analyzer/kpi_analyze.html', {
        "message": "KPI Analyze HTML"
    })