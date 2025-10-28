from django.urls import path
from .views import (
    TimesheetView, KpiAnalyzerView, kpi_analyze_html,
    OfferTableView, LeadTableView, CallTableView, KpiPlanTableView, LeadPivotView, KpiSummaryView
)

urlpatterns = [
    path('api/timesheet/', TimesheetView.as_view(), name='timesheet'),
    path('api/kpi-analyze/', KpiAnalyzerView.as_view(), name='kpi_analyze'),
    path('kpi-analyze/', kpi_analyze_html, name='kpi_analyze_html'),
    path('offers/', OfferTableView.as_view(), name='offers_table'),
    path('leads/', LeadTableView.as_view(), name='leads_table'),
    path('calls/', CallTableView.as_view(), name='calls_table'),
    path('kpi-plans/', KpiPlanTableView.as_view(), name='kpi_plans_table'),
    path('leads-pivot/', LeadPivotView.as_view(), name='leads_pivot_table'),
    path('kpi-summary/', KpiSummaryView.as_view(), name='kpi_summary'),
]