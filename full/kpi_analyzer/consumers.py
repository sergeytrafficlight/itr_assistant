import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Cell

class SpreadsheetConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.spreadsheet_id = self.scope['url_route']['kwargs']['spreadsheet_id']
        self.room_group_name = f'spreadsheet_{self.spreadsheet_id}'
        
        # Присоединение к группе комнаты
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        # Покидание группы комнаты
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    # В consumers.py ДОБАВИТЬ:
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json['type']

            if message_type == 'cell_update':
                await self.handle_cell_update(text_data_json)
            elif message_type == 'sheet_update':
                await self.handle_sheet_update(text_data_json)
            else:
                await self.send(json.dumps({'error': 'Unknown message type'}))

        except json.JSONDecodeError:
            await self.send(json.dumps({'error': 'Invalid JSON'}))
        except Exception as e:
            await self.send(json.dumps({'error': str(e)}))
    
    async def handle_cell_update(self, data):
        """Обработка обновления ячейки"""
        cell_data = data['cell']
        
        # Сохранение в базе данных
        await self.save_cell_update(cell_data)
        
        # Рассылка обновления всем подключенным клиентам
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'cell_updated',
                'cell': cell_data
            }
        )
    
    async def handle_sheet_update(self, data):
        """Обработка обновления листа"""
        sheet_data = data['sheet']
        
        # Рассылка обновления всем подключенным клиентам
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'sheet_updated',
                'sheet': sheet_data
            }
        )
    
    async def cell_updated(self, event):
        """Отправка обновления ячейки клиенту"""
        await self.send(text_data=json.dumps({
            'type': 'cell_updated',
            'cell': event['cell']
        }))
    
    async def sheet_updated(self, event):
        """Отправка обновления листа клиенту"""
        await self.send(text_data=json.dumps({
            'type': 'sheet_updated',
            'sheet': event['sheet']
        }))
    
    @database_sync_to_async
    def save_cell_update(self, cell_data):
        """Сохранение обновления ячейки в базу данных"""
        try:
            cell = Cell.objects.get(
                sheet_id=cell_data['sheet_id'],
                row=cell_data['row'],
                col=cell_data['col']
            )
            
            # Обновление полей ячейки
            for field in ['value', 'formula', 'style']:
                if field in cell_data:
                    setattr(cell, field, cell_data[field])
            
            cell.save()
        except Cell.DoesNotExist:
            # Создание новой ячейки
            Cell.objects.create(**cell_data)