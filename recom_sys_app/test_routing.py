"""
Unit Tests for WebSocket Routing (routing.py)

Tests cover:
- WebSocket URL patterns
- URL pattern matching
- Consumer routing
"""

from django.test import TestCase
from recom_sys_app import routing


class RoutingTest(TestCase):
    """Test suite for WebSocket routing configuration"""

    def test_websocket_urlpatterns_exists(self):
        """Test that websocket_urlpatterns is defined"""
        self.assertTrue(hasattr(routing, "websocket_urlpatterns"))
        self.assertIsInstance(routing.websocket_urlpatterns, list)

    def test_websocket_urlpatterns_not_empty(self):
        """Test that websocket_urlpatterns has entries"""
        self.assertGreater(len(routing.websocket_urlpatterns), 0)

    def test_chat_url_pattern(self):
        """Test chat WebSocket URL pattern"""
        # Check that pattern exists
        patterns = routing.websocket_urlpatterns
        chat_patterns = [
            p for p in patterns if "chat" in str(p.pattern) or "ChatConsumer" in str(p)
        ]
        self.assertGreater(len(chat_patterns), 0)

    def test_match_url_pattern(self):
        """Test match WebSocket URL pattern"""
        # Check that pattern exists
        patterns = routing.websocket_urlpatterns
        match_patterns = [
            p
            for p in patterns
            if "match" in str(p.pattern) or "MatchConsumer" in str(p)
        ]
        self.assertGreater(len(match_patterns), 0)

    def test_routing_module_imports(self):
        """Test that routing module can be imported"""
        from recom_sys_app import routing

        self.assertIsNotNone(routing)
        self.assertTrue(hasattr(routing, "websocket_urlpatterns"))

    def test_consumers_imported(self):
        """Test that consumers module is imported"""
        # Check that consumers module is accessible
        import recom_sys_app.consumers

        self.assertIsNotNone(recom_sys_app.consumers)
