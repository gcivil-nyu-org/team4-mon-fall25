import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recommendation_sys.settings")
django.setup()

from django.test import RequestFactory
from recommendation_sys.urls import root_view

factory = RequestFactory()
request = factory.get("/")

try:
    response = root_view(request)
    print(f"Success! Response status: {response.status_code}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback

    traceback.print_exc()
