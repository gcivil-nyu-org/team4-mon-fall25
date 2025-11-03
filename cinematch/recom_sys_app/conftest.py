"""
Pytest configuration file for WebSocket tests.

This file contains fixtures and configurations shared across all tests.
"""
import pytest
import os
import django
from channels.testing import WebsocketCommunicator
from django.conf import settings

# Set Django settings module for tests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recommendation_sys.settings')

# Setup Django
django.setup()


@pytest.fixture(scope='session')
def channel_layers_setup():
    """
    Configure channel layers for tests.
    Uses InMemoryChannelLayer (no Redis required).
    """
    settings.CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer'
        }
    }


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Automatically enable database access for all tests.
    """
    pass


@pytest.fixture
def test_user(db):
    """
    Create a test user for use in tests.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    user = User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )
    return user


@pytest.fixture
def test_group(db, test_user):
    """
    Create a test group session with the test user as creator.
    """
    from recom_sys_app.models import GroupSession, GroupMember
    
    group = GroupSession.objects.create(
        group_code='TESTGRP',
        creator=test_user
    )
    
    # Ensure member exists
    GroupMember.objects.get_or_create(
        group_session=group,
        user=test_user,
        defaults={
            'role': GroupMember.Role.CREATOR,
            'is_active': True
        }
    )
    
    return group


@pytest.fixture
def authenticated_communicator(test_user, test_group):
    """
    Create an authenticated WebSocket communicator.
    """
    from recommendation_sys.asgi import application
    
    communicator = WebsocketCommunicator(
        application,
        f"/ws/chat/{test_group.group_code}/"
    )
    communicator.scope['user'] = test_user
    
    return communicator


@pytest.fixture(autouse=True)
def cleanup_groups(db):
    """
    Clean up test groups after each test.
    """
    yield
    from recom_sys_app.models import GroupSession
    GroupSession.objects.all().delete()


# Configure pytest-asyncio
@pytest.fixture(scope='session')
def event_loop_policy():
    """
    Set event loop policy for async tests.
    """
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


# Mark all tests as async-compatible
def pytest_collection_modifyitems(items):
    """
    Automatically mark tests with appropriate markers.
    """
    for item in items:
        if 'asyncio' in item.keywords:
            item.add_marker(pytest.mark.asyncio)
        if 'django_db' not in item.keywords:
            item.add_marker(pytest.mark.django_db)
