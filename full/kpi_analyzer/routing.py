from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/spreadsheet/(?P<spreadsheet_id>\w+)/$', consumers.SpreadsheetConsumer.as_asgi()),
]