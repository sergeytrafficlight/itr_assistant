from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required


def api_routes(request):
    """Показать все доступные API routes"""
    return JsonResponse({
        'message': 'API is working!',
        'available_routes': [
            '/api/auth/login/',
            '/api/auth/refresh/',
            '/api/admin/auth/me/',
        ]
    })


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('kpi_analyzer.urls')),

    path('', login_required(TemplateView.as_view(template_name='index.html')), name='home'),
    path('sheets/', login_required(TemplateView.as_view(template_name='index.html'))),
    path('analytics/', login_required(TemplateView.as_view(template_name='index.html'))),
    path('reports/', login_required(TemplateView.as_view(template_name='index.html'))),
    path('full-data/', login_required(TemplateView.as_view(template_name='index.html'))),
    path('admin-panel/', login_required(TemplateView.as_view(template_name='index.html'))),

    path('login/', TemplateView.as_view(template_name='index.html')),
]