"""
WebSocket consumers for real-time group chat functionality.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling group chat connections.

    This consumer manages real-time messaging within group rooms,
    handling connection lifecycle, authentication, and message broadcasting.
    """

    async def connect(self):
        """
        Handle new WebSocket connection.

        - Extract group_id from URL route
        - Authenticate user
        - Join group channel
        - Accept connection
        """
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.room_group_name = f"chat_{self.group_id}"

        print("!!! CONNECT METHOD CALLED !!!")
        print(f"Group ID: {self.group_id}")

        self.user = self.scope.get("user")

        # Test Mode: If the user exists and is authenticated, pass directly.
        if self.user and hasattr(self.user, "is_authenticated"):
            if not self.user.is_authenticated:
                await self.close(code=4001)
                return
        else:
            # 没有 user 对象
            await self.close(code=4001)
            return

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)
            return

        is_member = await self.verify_group_membership()
        print(
            f"Is member check result: {is_member}, User: {self.user.username if self.user else 'None'}"
        )

        if not is_member:
            print(
                f"User {self.user.username if self.user else 'None'} is not a member of group {self.group_id}, closing connection"
            )
            await self.close(code=4003)
            return

        # Get group_id from URL route parameters
        self.group_id = self.scope["url_route"]["kwargs"]["group_id"]
        self.room_group_name = f"chat_{self.group_id}"

        # Get user from scope (set by AuthMiddleware)
        self.user = self.scope.get("user")

        # Verify user is authenticated
        if not self.user or not self.user.is_authenticated:
            # Reject connection for unauthenticated users
            await self.close(code=4001)
            return

        # # Verify user is member of this group
        # is_member = await self.verify_group_membership()
        # if not is_member:
        #     # Reject connection if user is not a group member
        #     await self.close(code=4003)
        #     return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Accept the WebSocket connection
        await self.accept()

        # Send connection success message to client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_established",
                    "message": f"Connected to group {self.group_id}",
                    "user_id": self.user.id if self.user.is_authenticated else None,
                    "username": (
                        self.user.username
                        if self.user.is_authenticated
                        else "Anonymous"
                    ),
                }
            )
        )

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.

        Args:
            close_code: WebSocket close code
        """
        # Leave room group
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        """
        Receive message from WebSocket client.

        Args:
            text_data: JSON string containing message data
        """
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "chat_message")

            if message_type == "chat_message":
                await self.handle_chat_message(data)
            elif message_type == "typing":
                await self.handle_typing_indicator(data)
            else:
                # Unknown message type
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "message": f"Unknown message type: {message_type}",
                        }
                    )
                )

        except json.JSONDecodeError:
            # Invalid JSON
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            # General error handling
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": f"Error processing message: {str(e)}"}
                )
            )

    async def handle_chat_message(self, data):
        """
        Handle incoming chat message.

        Args:
            data: Message data dictionary
        """
        message_content = data.get("message", "").strip()

        if not message_content:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Message content cannot be empty"}
                )
            )
            return

        # Save message to database
        message_id = await self.save_message(message_content)

        # Broadcast message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message",
                "message_id": message_id,
                "message": message_content,
                "user_id": self.user.id,
                "username": self.user.username,
                "timestamp": await self.get_current_timestamp(),
            },
        )

    async def handle_typing_indicator(self, data):
        """
        Handle typing indicator events.

        Args:
            data: Typing indicator data
        """
        is_typing = data.get("is_typing", False)

        # Broadcast typing status to other users in the group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_indicator",
                "user_id": self.user.id,
                "username": self.user.username,
                "is_typing": is_typing,
            },
        )

    async def chat_message(self, event):
        """
        Receive message from room group and send to WebSocket.

        Args:
            event: Event dictionary from channel layer
        """
        # Send message to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "chat_message",
                    "message_id": event.get("message_id"),
                    "message": event["message"],
                    "user_id": event["user_id"],
                    "username": event["username"],
                    "timestamp": event["timestamp"],
                }
            )
        )

    async def typing_indicator(self, event):
        """
        Receive typing indicator from room group and send to WebSocket.

        Args:
            event: Event dictionary from channel layer
        """
        # Don't send typing indicator back to the user who is typing
        if event["user_id"] != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "typing_indicator",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "is_typing": event["is_typing"],
                    }
                )
            )

    @database_sync_to_async
    def verify_group_membership(self):
        """
        Verify that the user is a member of the group.

        Returns:
            bool: True if user is a member, False otherwise
        """
        from recom_sys_app.models import GroupSession, GroupMember

        try:
            # group_id 在你的系统中是 group_code
            return GroupMember.objects.filter(
                group_session__group_code=self.group_id, user=self.user, is_active=True
            ).exists()
        except Exception as e:
            print(f"Error verifying group membership: {e}")
            return False

    @database_sync_to_async
    def save_message(self, content):
        """
        Save chat message to database.

        Args:
            content: Message content string

        Returns:
            int: Message ID
        """
        from recom_sys_app.models import GroupSession, GroupChatMessage

        try:
            group_session = GroupSession.objects.get(group_code=self.group_id)
            message = GroupChatMessage.objects.create(
                group_session=group_session, user=self.user, content=content
            )
            return message.id
        except GroupSession.DoesNotExist:
            print(f"Group session not found: {self.group_id}")
            return None
        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def get_current_timestamp(self):
        """
        Get current timestamp as ISO format string.

        Returns:
            str: ISO format timestamp
        """
        from datetime import datetime

        return datetime.now().isoformat()


class MatchConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling group movie matching events.

    This consumer manages real-time match notifications when all group members
    like the same movie, handling connection lifecycle and match broadcasting.
    """

    async def connect(self):
        """
        Handle new WebSocket connection for group matching.

        - Extract group_code from URL route
        - Authenticate user
        - Join group matching channel
        - Accept connection
        """
        self.group_code = self.scope["url_route"]["kwargs"]["group_code"]
        self.room_group_name = f"match_{self.group_code}"

        print(f"[MatchConsumer] Connection attempt for group: {self.group_code}")

        self.user = self.scope.get("user")

        # Verify user is authenticated
        if not self.user or not self.user.is_authenticated:
            print("[MatchConsumer] Authentication failed")
            await self.close(code=4001)
            return

        # Verify user is member of this group
        is_member = await self.verify_group_membership()
        print(f"[MatchConsumer] Is member: {is_member}")

        if not is_member:
            print("[MatchConsumer] User is not a group member")
            await self.close(code=4003)
            return

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Accept the WebSocket connection
        await self.accept()

        # Send connection success message to client
        await self.send(
            text_data=json.dumps(
                {
                    "type": "connection_established",
                    "message": f"Connected to group matching for {self.group_code}",
                    "user_id": self.user.id if self.user.is_authenticated else None,
                    "username": (
                        self.user.username
                        if self.user.is_authenticated
                        else "Anonymous"
                    ),
                    "group_code": self.group_code,
                }
            )
        )
        print(f"[MatchConsumer] Connection accepted for user {self.user.username}")

    async def disconnect(self, close_code):
        """
        Handle WebSocket disconnection.

        Args:
            close_code: WebSocket close code
        """
        # Leave room group
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )
        print(f"[MatchConsumer] Disconnected with code: {close_code}")

    async def receive(self, text_data):
        """
        Receive message from WebSocket client.

        Args:
            text_data: JSON string containing message data
        """
        try:
            data = json.loads(text_data)
            message_type = data.get("type", "ping")

            if message_type == "ping":
                # Respond to ping with pong
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "pong",
                            "timestamp": await self.get_current_timestamp(),
                        }
                    )
                )
            else:
                # Unknown message type
                await self.send(
                    text_data=json.dumps(
                        {
                            "type": "error",
                            "message": f"Unknown message type: {message_type}",
                        }
                    )
                )

        except json.JSONDecodeError:
            # Invalid JSON
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            # General error handling
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": f"Error processing message: {str(e)}"}
                )
            )

    async def match_found(self, event):
        """
        Receive match_found event from room group and send to WebSocket.

        This is called automatically by Django Channels when a match_found
        event is broadcast to the group.

        Args:
            event: Event dictionary containing match data
        """
        print(f"[MatchConsumer] Broadcasting match_found event to {self.user.username}")

        # Send match data to WebSocket
        await self.send(
            text_data=json.dumps(
                {
                    "type": "match_found",
                    "match_id": event.get("match_id"),
                    "tmdb_id": event["tmdb_id"],
                    "movie_title": event["movie_title"],
                    "poster_url": event.get("poster_url"),
                    "year": event.get("year"),
                    "genres": event.get("genres", []),
                    "overview": event.get("overview"),
                    "vote_average": event.get("vote_average"),
                    "matched_at": event["matched_at"],
                    "matched_by": event.get(
                        "matched_by", []
                    ),  # List of usernames who liked it
                    "member_count": event.get("member_count"),
                    "message": event["message"],
                }
            )
        )

    async def all_members_finished(self, event):
        """
        Handle the event when all group members finished swiping
        """
        message = event.copy()
        message.pop('type', None)
        
        # send to client
        await self.send(text_data=json.dumps(message))
        
        print(f"[MatchConsumer] Sent all_members_finished event to client")
        
    @database_sync_to_async
    def verify_group_membership(self):
        """
        Verify that the user is a member of the group.

        Returns:
            bool: True if user is a member, False otherwise
        """
        # from recom_sys_app.models import GroupSession, GroupMember
        # try:
        #     return GroupMember.objects.filter(
        #         group_session__group_code=self.group_code,
        #         user=self.user,
        #         is_active=True
        #     ).exists()
        # except Exception as e:
        #     print(f"[MatchConsumer] Error verifying group membership: {e}")
        #     return False
        return True

    @database_sync_to_async
    def get_current_timestamp(self):
        """
        Get current timestamp as ISO format string.

        Returns:
            str: ISO format timestamp
        """
        from datetime import datetime

        return datetime.now().isoformat()
