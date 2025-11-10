import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import kpi_analyzer.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kpi_analyzer_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            kpi_analyzer.routing.websocket_urlpatterns
        )
    ),
})