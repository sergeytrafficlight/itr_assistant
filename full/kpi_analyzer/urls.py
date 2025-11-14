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
router.register(r'offers', views.OfferViewSet)
router.register(r'operators', views.OperatorViewSet)
router.register(r'affiliates', views.AffiliateViewSet)


router.register(r'kpi', views.KPIAdvancedAnalysisViewSet, basename='kpi')

router.register(r'kpi-data', views.KpiDataViewSet)


urlpatterns = [
    path('', include(router.urls)),


    path('legacy/kpi-analysis/', views.LegacyKPIAnalysisView.as_view(), name='legacy-kpi-analysis'),
    path('legacy/filter-params/', views.LegacyFilterParamsView.as_view(), name='legacy-filter-params'),


    path('kpi/advanced_analysis/', views.KPIAdvancedAnalysisViewSet.as_view({'post': 'advanced_analysis'}),
         name='kpi-advanced-analysis'),
]