from tortoise.models import Model
from tortoise import fields
import uuid

class User(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    username = fields.CharField(max_length=50, unique=True)
    password = fields.CharField(max_length=128)  # disarankan buat password panjang dan hashed
    email = fields.CharField(max_length=100, unique=True)  # panjang email bisa lebih dari 50

class RoomChat(Model):
    id = fields.UUIDField(pk=True, default=uuid.uuid4)
    owner = fields.ForeignKeyField('models.User', related_name='owned_rooms', to_field='id')
    room_name = fields.CharField(max_length=100)
    created_at = fields.DatetimeField(auto_now_add=True)

class ChatMessage(Model):
    id = fields.IntField(pk=True)
    room = fields.ForeignKeyField('models.RoomChat', related_name='messages', to_field='id')
    sender_type = fields.CharField(max_length=10)  # 'user' atau 'bot'
    sender = fields.ForeignKeyField('models.User', null=True, to_field='id')  # null kalau bot
    message = fields.TextField()
    created_at = fields.DatetimeField(auto_now_add=True)

class QA_Pair(Model):
    id = fields.IntField(pk=True)
    question = fields.ForeignKeyField('models.ChatMessage', related_name='qa_question', to_field='id')
    answer = fields.ForeignKeyField('models.ChatMessage', related_name='qa_answer', to_field='id')

class ScannedProduct(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="scans", to_field='id')
    product_name = fields.CharField(max_length=100)
    scanned_at = fields.DatetimeField(auto_now_add=True)
    status = fields.CharField(max_length=20)
