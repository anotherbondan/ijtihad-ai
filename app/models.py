from tortoise.models import Model
from tortoise import fields
import uuid

class User(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    username = fields.CharField(max_length=50, unique=True)

class RoomChat(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    owner = fields.ForeignKeyField('models.User', related_name='owned_rooms', to_field='id')
    room_name = fields.CharField(max_length=100)
    created_at = fields.DatetimeField(auto_now_add=True)

class ChatMessage(Model):
    id = fields.IntField(pk=True) 
    room = fields.ForeignKeyField('models.RoomChat', related_name='messages', to_field='id')
    sender_type = fields.CharField(max_length=10)
    sender = fields.ForeignKeyField('models.User', null=True, to_field='id')
    message = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)