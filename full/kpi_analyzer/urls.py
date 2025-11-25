from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'spreadsheets', views.SpreadsheetViewSet)
router.register(r'sheets', views.SheetViewSet)
router.register(r'cells', views.CellViewSet)
router.register(r'formulas', views.FormulaViewSet)
router.register(r'pivot-tables', views.PivotTableViewSet)
router.register(r'kpi', views.KPIAdvancedAnalysisViewSet, basename='kpi')
router.register(r'kpi-analysis', views.KPIAdvancedAnalysisViewSet, basename='kpi-analysis')
router.register(r'kpi-data', views.KpiDataViewSet)

urlpatterns = [
    path('', include(router.urls)),

    # Справочники
    path('categories/', views.CategoryListView.as_view(), name='categories-list'),
    path('advertisers/', views.AdvertiserListView.as_view(), name='advertisers-list'),

    # Legacy endpoints
    path('legacy/kpi-analysis/', views.LegacyKPIAnalysisView.as_view(), name='legacy-kpi-analysis'),
    path('legacy/filter-params/', views.LegacyFilterParamsView.as_view(), name='legacy-filter-params'),

    # Админка
    path('admin/stats/', views.AdminStatsView.as_view(), name='admin-stats'),
    path('admin/users/', views.UserListView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', views.UserDetailView.as_view(), name='admin-user-detail'),
    path('admin/auth/me/', views.AdminAuthView.as_view(), name='admin-auth-me'),

    # Аутентификация
    path('auth/login/', views.PublicTokenObtainPairView.as_view(), name='auth-login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/register/', views.UserRegistrationView.as_view(), name='auth-register'),
]