# chat/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from accounts.models import Account, Contact, Message
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # ✅ Convert to string explicitly
        self.user_id = str(self.scope['url_route']['kwargs']['user_id'])
        self.room_group_name = f'chat_{self.user_id}'

        logger.info(f"🔌 WebSocket connect attempt: user_id={self.user_id}")

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()
        
        # Set user online
        await self.set_user_online(self.user_id, True)
        logger.info(f"✅ User {self.user_id} connected to {self.room_group_name}")

    async def disconnect(self, close_code):
        logger.info(f"🔴 User {self.user_id} disconnecting, code: {close_code}")
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Set user offline
        await self.set_user_online(self.user_id, False)
        logger.info(f"❌ User {self.user_id} disconnected")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            logger.info(f"📨 Received message: type={message_type}, data={data}")

            if message_type == 'send_message':
                await self.handle_send_message(data)
            elif message_type == 'contact_request':
                await self.handle_contact_request(data)
            elif message_type == 'accept_contact':
                await self.handle_accept_contact(data)
            else:
                logger.warning(f"⚠️ Unknown message type: {message_type}")
        
        except Exception as e:
            logger.error(f"❌ Error in receive: {str(e)}", exc_info=True)

    async def handle_send_message(self, data):
        try:
            to_user_id = data.get('to_user_id')
            message_text = data.get('message')
            message_id = data.get('message_id')

            logger.info(f"💬 Sending message: from={self.user_id}, to={to_user_id}, text={message_text[:50]}")

            # Save message to database
            message = await self.save_message(
                sender_telegram_id=int(self.user_id),  # ✅ Convert to int for DB query
                receiver_id=to_user_id,
                content=message_text
            )

            if not message:
                logger.error("❌ Failed to save message")
                return

            # Get receiver's telegram_id
            receiver_telegram_id = await self.get_telegram_id(to_user_id)
            
            if receiver_telegram_id:
                # Send to receiver
                await self.channel_layer.group_send(
                    f'chat_{receiver_telegram_id}',
                    {
                        'type': 'chat_message',
                        'message': message_text,
                        'from_user_id': self.user_id,
                        'message_id': message_id,
                        'timestamp': message.created_at.isoformat()
                    }
                )
                logger.info(f"✅ Message sent to chat_{receiver_telegram_id}")
            else:
                logger.error(f"❌ Receiver not found: {to_user_id}")
        
        except Exception as e:
            logger.error(f"❌ Error sending message: {str(e)}", exc_info=True)

    async def handle_contact_request(self, data):
        try:
            to_user_id = data.get('to_user_id')
            custom_name = data.get('custom_name', '')

            logger.info(f"👥 Contact request: from={self.user_id}, to={to_user_id}")

            # Get receiver's telegram_id
            receiver_telegram_id = await self.get_telegram_id(to_user_id)
            
            if receiver_telegram_id:
                # Send notification to target user
                await self.channel_layer.group_send(
                    f'chat_{receiver_telegram_id}',
                    {
                        'type': 'contact_request_notification',
                        'from_user_id': self.user_id,
                        'from_name': custom_name
                    }
                )
                logger.info(f"✅ Contact request sent to chat_{receiver_telegram_id}")
            else:
                logger.error(f"❌ Target user not found: {to_user_id}")
        
        except Exception as e:
            logger.error(f"❌ Error in contact request: {str(e)}", exc_info=True)

    async def handle_accept_contact(self, data):
        try:
            from_user_id = data.get('from_user_id')

            logger.info(f"✅ Accepting contact: from={from_user_id}, to={self.user_id}")

            # Get sender's telegram_id
            sender_telegram_id = await self.get_telegram_id(from_user_id)
            
            if sender_telegram_id:
                # Notify sender that contact was accepted
                await self.channel_layer.group_send(
                    f'chat_{sender_telegram_id}',
                    {
                        'type': 'contact_accepted_notification',
                        'user_id': self.user_id
                    }
                )
                logger.info(f"✅ Contact accepted notification sent to chat_{sender_telegram_id}")
            else:
                logger.error(f"❌ Sender not found: {from_user_id}")
        
        except Exception as e:
            logger.error(f"❌ Error accepting contact: {str(e)}", exc_info=True)

    # WebSocket message handlers
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': event['message'],
            'from_user_id': event['from_user_id'],
            'message_id': event['message_id'],
            'timestamp': event['timestamp']
        }))

    async def contact_request_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'contact_request',
            'from_user_id': event['from_user_id'],
            'from_name': event['from_name']
        }))

    async def contact_accepted_notification(self, event):
        await self.send(text_data=json.dumps({
            'type': 'contact_accepted',
            'user_id': event['user_id']
        }))

    # Database operations
    @database_sync_to_async
    def save_message(self, sender_telegram_id, receiver_id, content):
        try:
            sender = Account.objects.get(telegram_id=sender_telegram_id)
            receiver = Account.objects.get(id=receiver_id)
            
            # Message expires in 30 seconds (configurable)
            expires_at = timezone.now() + timedelta(seconds=30)
            
            message = Message.objects.create(
                sender=sender,
                receiver=receiver,
                text=content,  # ✅ Fixed: Use 'text' field instead of 'content'
                expires_at=expires_at
            )
            logger.info(f"💾 Message saved: id={message.id}")
            return message
        except Account.DoesNotExist as e:
            logger.error(f"❌ Account not found: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error saving message: {str(e)}", exc_info=True)
            return None

    @database_sync_to_async
    def set_user_online(self, telegram_id, is_online):
        try:
            user = Account.objects.get(telegram_id=int(telegram_id))  # ✅ Convert to int
            user.is_online = is_online
            if not is_online:
                user.last_seen = timezone.now()
            user.save()
            logger.info(f"👤 User {telegram_id} online status: {is_online}")
        except Account.DoesNotExist:
            logger.error(f"❌ User not found: {telegram_id}")
        except Exception as e:
            logger.error(f"❌ Error setting user online: {str(e)}", exc_info=True)

    @database_sync_to_async
    def get_telegram_id(self, user_id):
        try:
            user = Account.objects.get(id=user_id)
            return str(user.telegram_id)  # ✅ Return as string for consistency
        except Account.DoesNotExist:
            logger.error(f"❌ User not found: {user_id}")
            return None
        except Exception as e:
            logger.error(f"❌ Error getting telegram_id: {str(e)}", exc_info=True)
            return None 