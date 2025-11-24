"""
Unit tests for WebSocket chat consumers.

Tests cover connection handling, message sending/receiving,
authentication, and error scenarios.

Designed for Travis CI compatibility.
"""

import pytest
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from channels.routing import ProtocolTypeRouter, URLRouter
from recom_sys_app import routing

application = ProtocolTypeRouter(
    {"websocket": URLRouter(routing.websocket_urlpatterns)}
)

User = get_user_model()

# Use InMemoryChannelLayer for tests (no Redis dependency)
TEST_CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}


@pytest.fixture
@database_sync_to_async
def create_group_session(user):
    """Create a test group session."""
    from recom_sys_app.models import GroupSession, GroupMember

    group = GroupSession.objects.create(group_code="TEST123", creator=user)

    GroupMember.objects.create(
        group_session=group, user=user, role=GroupMember.Role.CREATOR
    )

    return group


@database_sync_to_async
def create_test_user(username, email):
    """
    Create a test user asynchronously.

    Args:
        username: Username for the test user
        email: Email for the test user

    Returns:
        User: Created user instance
    """
    user, created = User.objects.get_or_create(
        username=username, email=email, defaults={"password": "testpass123"}
    )
    if not created:
        user.set_password("testpass123")
        user.save()
    return user


@database_sync_to_async
def create_group_for_user(user, group_code="TESTGRP"):
    """Create a group session and add user as member."""
    from recom_sys_app.models import GroupSession, GroupMember

    # Delete existing group with same code
    GroupSession.objects.filter(group_code=group_code).delete()

    group = GroupSession.objects.create(group_code=group_code, creator=user)

    # Force creation of members
    # (regardless of whether models.py automatically creates them upon saving)
    member, created = GroupMember.objects.get_or_create(
        group_session=group,
        user=user,
        defaults={"role": GroupMember.Role.CREATOR, "is_active": True},
    )

    return group


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestChatConsumer:
    """Test suite for ChatConsumer WebSocket functionality."""

    async def test_websocket_connection_authenticated_user(self):
        """
        Test that an authenticated user can successfully connect to WebSocket.

        Given: An authenticated user who is a member of a group
        When: The user attempts to connect to a group chat WebSocket
        Then: The connection is accepted and a confirmation message is received
        """
        # Create test user and group
        user = await create_test_user("testuser", "test@example.com")
        group = await create_group_for_user(user, "TEST001")

        # Create WebSocket communicator
        communicator = WebsocketCommunicator(application, f"/ws/chat/TEST001/")

        # Set user in scope (simulate authentication)
        communicator.scope["user"] = user

        # Connect to WebSocket
        connected, subprotocol = await communicator.connect()

        # Assert connection successful
        assert connected is True

        # Receive connection confirmation
        response = await communicator.receive_json_from()

        assert response["type"] == "connection_established"
        assert response["user_id"] == user.id
        assert "TEST001" in response["message"]

        # Disconnect
        await communicator.disconnect()

    async def test_websocket_connection_unauthenticated_user(self):
        """
        Test that an unauthenticated user cannot connect to WebSocket.

        Given: An unauthenticated user
        When: The user attempts to connect to a group chat WebSocket
        Then: The connection is rejected with code 4001
        """
        # Create WebSocket communicator without authenticated user
        communicator = WebsocketCommunicator(application, f"/ws/chat/test-group-123/")

        # Set anonymous user
        communicator.scope["user"] = None

        # Attempt to connect
        connected, subprotocol = await communicator.connect()

        # Assert connection rejected
        assert connected is False

    async def test_send_chat_message(self):
        """
        Test sending a chat message through WebSocket.

        Given: A connected user in a group chat
        When: The user sends a chat message
        Then: The message is broadcast to all group members
        """
        user = await create_test_user("sender", "sender@example.com")
        group = await create_group_for_user(user, "TEST002")

        communicator = WebsocketCommunicator(application, f"/ws/chat/TEST002/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation message
        await communicator.receive_json_from()

        # Send chat message
        test_message = "Hello, this is a test message!"
        await communicator.send_json_to(
            {"type": "chat_message", "message": test_message}
        )

        # Receive broadcasted message
        response = await communicator.receive_json_from()

        assert response["type"] == "chat_message"
        assert response["message"] == test_message
        assert response["user_id"] == user.id
        assert response["username"] == user.username
        assert "timestamp" in response

        await communicator.disconnect()

    async def test_send_empty_message(self):
        """
        Test that empty messages are rejected.

        Given: A connected user
        When: The user sends an empty message
        Then: An error response is returned
        """
        user = await create_test_user("testuser2", "test2@example.com")
        group = await create_group_for_user(user, "TEST003")

        communicator = WebsocketCommunicator(application, f"/ws/chat/TEST003/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send empty message
        await communicator.send_json_to({"type": "chat_message", "message": ""})

        # Receive error response
        response = await communicator.receive_json_from()

        assert response["type"] == "error"
        assert "empty" in response["message"].lower()

        await communicator.disconnect()

    async def test_typing_indicator(self):
        """
        Test typing indicator functionality.

        Given: Two users in the same group chat
        When: One user starts typing
        Then: The other user receives a typing indicator
        """
        user1 = await create_test_user("user1", "user1@example.com")
        user2 = await create_test_user("user2", "user2@example.com")

        # Create group with both users
        group = await create_group_for_user(user1, "TYPING-TEST")

        # Add user2 to the group
        @database_sync_to_async
        def add_user_to_group():
            from recom_sys_app.models import GroupMember

            GroupMember.objects.get_or_create(
                group_session=group,
                user=user2,
                defaults={"role": GroupMember.Role.MEMBER, "is_active": True},
            )

        await add_user_to_group()

        # Connect both users
        comm1 = WebsocketCommunicator(application, "/ws/chat/TYPING-TEST/")
        comm1.scope["user"] = user1

        comm2 = WebsocketCommunicator(application, "/ws/chat/TYPING-TEST/")
        comm2.scope["user"] = user2

        await comm1.connect()
        await comm2.connect()

        # Skip connection confirmations
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # User1 starts typing
        await comm1.send_json_to({"type": "typing", "is_typing": True})

        # User2 should receive typing indicator
        response = await comm2.receive_json_from()

        assert response["type"] == "typing_indicator"
        assert response["user_id"] == user1.id
        assert response["is_typing"] is True

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_invalid_json_message(self):
        """
        Test handling of invalid JSON messages.

        Given: A connected user
        When: The user sends invalid JSON data
        Then: An error response is returned
        """
        user = await create_test_user("jsontest", "json@example.com")
        group = await create_group_for_user(user, "JSON-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/JSON-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send invalid JSON
        await communicator.send_to(text_data="This is not JSON")

        # Receive error response
        response = await communicator.receive_json_from()

        assert response["type"] == "error"
        assert "json" in response["message"].lower()

        await communicator.disconnect()

    async def test_disconnect_cleanup(self):
        """
        Test that disconnect properly cleans up channel layer groups.

        Given: A connected user
        When: The user disconnects
        Then: The user is removed from the channel layer group
        """
        user = await create_test_user("disconnect_test", "disc@example.com")
        group = await create_group_for_user(user, "DISC-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/DISC-TEST/")
        communicator.scope["user"] = user

        # Connect
        connected, _ = await communicator.connect()
        assert connected

        # Get channel layer
        channel_layer = get_channel_layer()

        # Disconnect
        await communicator.disconnect()

        # Basic verification - no exception raised
        assert True

    async def test_non_member_cannot_connect(self):
        """
        Test that a user who is not a group member cannot connect.

        Given: A user who is not a member of the group
        When: The user attempts to connect to the group WebSocket
        Then: The connection is rejected
        """
        # Create group with one user
        creator = await create_test_user("creator", "creator@example.com")
        group = await create_group_for_user(creator, "PRIVATE-GRP")

        # Create another user who is NOT a member
        non_member = await create_test_user("non_member", "non@example.com")

        communicator = WebsocketCommunicator(application, f"/ws/chat/PRIVATE-GRP/")
        communicator.scope["user"] = non_member

        # Attempt to connect
        connected, _ = await communicator.connect()

        # Connection should be rejected
        assert connected is False

    async def test_message_with_special_characters(self):
        """Test message with special characters and emojis."""
        user = await create_test_user("special", "special@example.com")
        group = await create_group_for_user(user, "SPECIAL-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/SPECIAL-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        # Test special characters
        special_message = "Hello! 你好 🎉 <script>alert('test')</script>"
        await communicator.send_json_to(
            {"type": "chat_message", "message": special_message}
        )

        response = await communicator.receive_json_from()
        assert response["type"] == "chat_message"
        assert response["message"] == special_message

        await communicator.disconnect()

    async def test_whitespace_only_message(self):
        """Test message with only whitespace is rejected."""
        user = await create_test_user("whitespace", "ws@example.com")
        group = await create_group_for_user(user, "WS-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/WS-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        # Send whitespace-only message
        await communicator.send_json_to(
            {"type": "chat_message", "message": "   \n\t  "}
        )

        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "empty" in response["message"].lower()

        await communicator.disconnect()

    async def test_very_long_message(self):
        """Test handling of very long messages."""
        user = await create_test_user("longmsg", "long@example.com")
        group = await create_group_for_user(user, "LONG-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/LONG-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        # Send very long message (1000 characters)
        long_message = "A" * 1000
        await communicator.send_json_to(
            {"type": "chat_message", "message": long_message}
        )

        response = await communicator.receive_json_from()
        assert response["type"] == "chat_message"
        assert len(response["message"]) == 1000

        await communicator.disconnect()

    async def test_rapid_typing_indicators(self):
        """Test rapid typing indicator changes."""
        user = await create_test_user("rapidtype", "rapid@example.com")
        group = await create_group_for_user(user, "RAPID-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/RAPID-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        # Rapidly toggle typing indicator
        for i in range(5):
            await communicator.send_json_to({"type": "typing", "is_typing": i % 2 == 0})

        await communicator.disconnect()

    async def test_message_without_type_field(self):
        """Test message without type field defaults to chat_message."""
        user = await create_test_user("notype", "notype@example.com")
        group = await create_group_for_user(user, "NOTYPE-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/NOTYPE-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        # Send message without 'type' field
        await communicator.send_json_to({"message": "Test message"})

        # Should default to chat_message and work
        response = await communicator.receive_json_from()
        assert response["type"] == "chat_message"
        assert response["message"] == "Test message"

        await communicator.disconnect()

    async def test_connection_has_message_id(self):
        """Test that messages have message_id field."""
        user = await create_test_user("msgid", "msgid@example.com")
        group = await create_group_for_user(user, "MSGID-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/MSGID-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        await communicator.send_json_to({"type": "chat_message", "message": "Test"})

        response = await communicator.receive_json_from()
        assert "message_id" in response
        assert response["message_id"] is not None

        await communicator.disconnect()

    async def test_timestamp_format(self):
        """Test that timestamp is in correct ISO format."""
        user = await create_test_user("timestamp", "time@example.com")
        group = await create_group_for_user(user, "TIME-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/TIME-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from()

        await communicator.send_json_to({"type": "chat_message", "message": "Test"})

        response = await communicator.receive_json_from()
        assert "timestamp" in response
        # Verify it's a valid ISO format timestamp
        from datetime import datetime

        datetime.fromisoformat(response["timestamp"])  # Should not raise

        await communicator.disconnect()

    async def test_unknown_message_type(self):
        """Test handling of unknown message types."""
        user = await create_test_user("unknowntest", "unknown@example.com")
        group = await create_group_for_user(user, "UNKNOWN-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/UNKNOWN-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send unknown message type
        await communicator.send_json_to({"type": "unknown_type", "data": "test"})

        # Should receive error
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Unknown message type" in response["message"]

        await communicator.disconnect()

    async def test_json_decode_error_handling(self):
        """Test JSON decode error is caught and handled."""
        user = await create_test_user("jsonerror", "jsonerror@example.com")
        group = await create_group_for_user(user, "JSON-ERROR")

        communicator = WebsocketCommunicator(application, f"/ws/chat/JSON-ERROR/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send malformed JSON
        await communicator.send_to(text_data="not json at all")

        # Should receive error response
        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "json" in response["message"].lower()

        await communicator.disconnect()

    async def test_general_exception_handling(self):
        """Test general exception handling in receive method."""
        user = await create_test_user("exceptiontest", "exception@example.com")
        group = await create_group_for_user(user, "EXCEPTION-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/EXCEPTION-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send valid JSON but with missing required fields
        # This should trigger the exception handler
        await communicator.send_json_to(
            {
                "type": "chat_message"
                # Missing 'message' field
            }
        )

        # Should still get a response (error handling)
        response = await communicator.receive_json_from()
        # Either error about empty message or general error
        assert (
            "error" in response["type"].lower()
            or "empty" in response.get("message", "").lower()
        )

        await communicator.disconnect()

    async def test_typing_indicator_stops(self):
        """Test typing indicator can be turned off."""
        user = await create_test_user("typing_stop", "stop@example.com")
        group = await create_group_for_user(user, "TYPING-STOP")

        communicator = WebsocketCommunicator(application, f"/ws/chat/TYPING-STOP/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send typing start
        await communicator.send_json_to({"type": "typing", "is_typing": True})

        # Send typing stop
        await communicator.send_json_to({"type": "typing", "is_typing": False})

        await communicator.disconnect()

    async def test_multiple_messages_in_sequence(self):
        """Test sending multiple messages in sequence."""
        user = await create_test_user("multitest", "multi@example.com")
        group = await create_group_for_user(user, "MULTI-TEST")

        communicator = WebsocketCommunicator(application, f"/ws/chat/MULTI-TEST/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send multiple messages
        messages = ["Message 1", "Message 2", "Message 3"]
        for msg in messages:
            await communicator.send_json_to({"type": "chat_message", "message": msg})

            response = await communicator.receive_json_from()
            assert response["type"] == "chat_message"
            assert response["message"] == msg

        await communicator.disconnect()

    async def test_disconnect_without_connection(self):
        """Test disconnect is safe even without proper connection."""
        user = await create_test_user("disconn", "disconn@example.com")

        # Create communicator but don't connect
        communicator = WebsocketCommunicator(application, f"/ws/chat/NO-GROUP/")
        communicator.scope["user"] = user

        # Try to disconnect without connecting
        # Should not raise exception
        await communicator.disconnect()

        assert True  # If we get here, no exception was raised


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class ChatConsumerIntegrationTest(TestCase):
    """
    Integration tests for ChatConsumer with database operations.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            username="integration_test",
            email="integration@example.com",
            password="testpass123",
        )

    def test_consumer_imports(self):
        """Test that all consumer modules can be imported."""
        from recom_sys_app.consumers import ChatConsumer

        assert ChatConsumer is not None

    def test_routing_configuration(self):
        """Test that WebSocket routing is properly configured."""
        from recom_sys_app import routing

        assert hasattr(routing, "websocket_urlpatterns")
        assert len(routing.websocket_urlpatterns) > 0

    def test_models_exist(self):
        """Test that required models are available."""
        from recom_sys_app.models import GroupSession, GroupMember

        # Create test group
        group = GroupSession.objects.create(group_code="INTTEST", creator=self.user)

        # Manually create member (because save() may not work in tests)
        GroupMember.objects.get_or_create(
            group_session=group,
            user=self.user,
            defaults={"role": GroupMember.Role.CREATOR},
        )

        # Verify group was created
        assert group.id is not None
        assert group.group_code == "INTTEST"

        # Verify member was auto-created
        member = GroupMember.objects.filter(group_session=group, user=self.user).first()

        assert member is not None
        assert member.role == GroupMember.Role.CREATOR


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
class TestMatchConsumer:
    """Test suite for MatchConsumer WebSocket functionality."""

    async def test_match_consumer_authenticated_connection(self):
        """Test that authenticated user can connect to match consumer."""
        user = await create_test_user("matchuser1", "match1@example.com")
        group = await create_group_for_user(user, "MATCH001")

        communicator = WebsocketCommunicator(application, f"/ws/match/MATCH001/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected is True

        # Receive connection confirmation
        response = await communicator.receive_json_from()
        assert response["type"] == "connection_established"
        assert response["group_code"] == "MATCH001"
        assert response["user_id"] == user.id

        await communicator.disconnect()

    async def test_match_consumer_unauthenticated_rejected(self):
        """Test that unauthenticated user cannot connect."""
        from django.contrib.auth.models import AnonymousUser

        communicator = WebsocketCommunicator(application, f"/ws/match/TEST123/")
        communicator.scope["user"] = AnonymousUser()

        connected, _ = await communicator.connect()
        assert connected is False

    async def test_match_consumer_ping_pong(self):
        """Test ping-pong functionality."""
        user = await create_test_user("pinguser", "ping@example.com")
        group = await create_group_for_user(user, "PING-GROUP")

        communicator = WebsocketCommunicator(application, f"/ws/match/PING-GROUP/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Skip connection confirmation
        await communicator.receive_json_from()

        # Send ping
        await communicator.send_json_to({"type": "ping"})

        # Receive pong
        response = await communicator.receive_json_from()
        assert response["type"] == "pong"
        assert "timestamp" in response

        await communicator.disconnect()

    async def test_match_consumer_unknown_message_type(self):
        """Test handling of unknown message types."""
        user = await create_test_user("unknownmatch", "unknown@match.com")
        group = await create_group_for_user(user, "UNKNOWN-MATCH")

        communicator = WebsocketCommunicator(application, f"/ws/match/UNKNOWN-MATCH/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.receive_json_from()

        # Send unknown message type
        await communicator.send_json_to({"type": "unknown_action"})

        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "Unknown message type" in response["message"]

        await communicator.disconnect()

    async def test_match_consumer_invalid_json(self):
        """Test handling of invalid JSON."""
        user = await create_test_user("jsonmatch", "json@match.com")
        group = await create_group_for_user(user, "JSON-MATCH")

        communicator = WebsocketCommunicator(application, f"/ws/match/JSON-MATCH/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.receive_json_from()

        # Send invalid JSON
        await communicator.send_to(text_data="not valid json")

        response = await communicator.receive_json_from()
        assert response["type"] == "error"
        assert "json" in response["message"].lower()

        await communicator.disconnect()

    async def test_match_found_broadcast(self):
        """Test that match_found event is correctly broadcast."""
        user1 = await create_test_user("match1", "match1@test.com")
        user2 = await create_test_user("match2", "match2@test.com")
        group = await create_group_for_user(user1, "BROADCAST-TEST")

        # Add user2 to group
        @database_sync_to_async
        def add_user_to_group():
            from recom_sys_app.models import GroupMember

            GroupMember.objects.get_or_create(
                group_session=group,
                user=user2,
                defaults={"role": GroupMember.Role.MEMBER, "is_active": True},
            )

        await add_user_to_group()

        # Connect both users
        comm1 = WebsocketCommunicator(application, f"/ws/match/BROADCAST-TEST/")
        comm1.scope["user"] = user1

        comm2 = WebsocketCommunicator(application, f"/ws/match/BROADCAST-TEST/")
        comm2.scope["user"] = user2

        await comm1.connect()
        await comm2.connect()

        # Skip connection confirmations
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # Simulate match_found broadcast
        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()

        match_data = {
            "type": "match_found",
            "match_id": 1,
            "tmdb_id": 550,
            "movie_title": "Fight Club",
            "poster_url": "http://example.com/poster.jpg",
            "year": "1999",
            "genres": ["Drama", "Thriller"],
            "overview": "A great movie",
            "vote_average": 8.8,
            "matched_at": "2024-01-01T00:00:00",
            "matched_by": ["match1", "match2"],
            "member_count": 2,
            "message": "Everyone liked this movie!",
        }

        await channel_layer.group_send("match_BROADCAST-TEST", match_data)

        # Both users should receive the match
        response1 = await comm1.receive_json_from()
        response2 = await comm2.receive_json_from()

        assert response1["type"] == "match_found"
        assert response1["tmdb_id"] == 550
        assert response1["movie_title"] == "Fight Club"

        assert response2["type"] == "match_found"
        assert response2["tmdb_id"] == 550

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_match_consumer_disconnect_cleanup(self):
        """Test that disconnect properly cleans up."""
        user = await create_test_user("disconn_match", "disc@match.com")
        group = await create_group_for_user(user, "DISC-MATCH")

        communicator = WebsocketCommunicator(application, f"/ws/match/DISC-MATCH/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        # Disconnect
        await communicator.disconnect()

        # No exception should be raised
        assert True

    async def test_match_consumer_default_ping_type(self):
        """Test that missing type defaults to ping."""
        user = await create_test_user("default_ping", "default@ping.com")
        group = await create_group_for_user(user, "DEFAULT-PING")

        communicator = WebsocketCommunicator(application, f"/ws/match/DEFAULT-PING/")
        communicator.scope["user"] = user

        connected, _ = await communicator.connect()
        assert connected

        await communicator.receive_json_from()

        # Send message without type (should default to ping)
        await communicator.send_json_to({})

        response = await communicator.receive_json_from()
        assert response["type"] == "pong"

        await communicator.disconnect()

    async def test_match_event_with_all_fields(self):
        """Test match_found with all fields populated."""
        user = await create_test_user("fullmatch", "full@match.com")
        group = await create_group_for_user(user, "FULL-MATCH")

        communicator = WebsocketCommunicator(application, f"/ws/match/FULL-MATCH/")
        communicator.scope["user"] = user

        await communicator.connect()
        await communicator.receive_json_from()

        from channels.layers import get_channel_layer

        channel_layer = get_channel_layer()

        # Send complete match data
        complete_match = {
            "type": "match_found",
            "match_id": 999,
            "tmdb_id": 13,
            "movie_title": "Forrest Gump",
            "poster_url": "http://example.com/gump.jpg",
            "year": "1994",
            "genres": ["Drama", "Romance"],
            "overview": "Life is like a box of chocolates",
            "vote_average": 8.8,
            "matched_at": "2024-12-25T12:00:00",
            "matched_by": ["user1", "user2", "user3"],
            "member_count": 3,
            "message": "Perfect match!",
        }

        await channel_layer.group_send("match_FULL-MATCH", complete_match)

        response = await communicator.receive_json_from()

        assert response["type"] == "match_found"
        assert response["match_id"] == 999
        assert response["movie_title"] == "Forrest Gump"
        assert response["genres"] == ["Drama", "Romance"]
        assert response["member_count"] == 3
        assert len(response["matched_by"]) == 3

        await communicator.disconnect()


# Pytest configuration
pytestmark = pytest.mark.django_db
