from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'spreadsheets', views.SpreadsheetViewSet)
router.register(r'sheets', views.SheetViewSet)
router.register(r'cells', views.CellViewSet)
router.register(r'formulas', views.FormulaViewSet)
router.register(r'pivot-tables', views.PivotTableViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'offers', views.OfferviewSet)
router.register(r'operators', views.OperatorViewSet)
router.register(r'affiliates', views.AffiliateViewSet)
router.register(r'kpi-analytics', views.KPIAnalyticsViewSet, basename='kpi-analytics')
router.register(r'kpi-advanced', views.KPIAdvancedAnalysisViewSet, basename='kpi-advanced')
router.register(r'kpi-data', views.KpiDataViewSet)

urlpatterns = [
    path('', include(router.urls)),
]