"""
URL configuration for recommendation_sys project.
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.shortcuts import redirect

import os
from django.conf import settings
from django.conf.urls.static import static


def root_view(request):
    """
    Root path handler:
    - Returns 200 OK for ELB health checker
    - Serves React app if it exists
    - Redirects to app home otherwise
    """
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    # Check if request is from AWS ELB health checker
    if "ELB-HealthChecker" in user_agent:
        return HttpResponse("OK", status=200)

    # Try to serve React app if it exists
    index_path = os.path.join(settings.BASE_DIR, "frontend", "dist", "index.html")
    if os.path.exists(index_path):
        with open(index_path) as f:
            return HttpResponse(f.read())

    # Fallback: redirect to Django app home
    return redirect("recom_sys:home")


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "", include("recom_sys_app.urls", namespace="recom_sys")
    ),  # App routes - handles all app URLs including home
]

# Serve media files (user uploads like profile images)
# In production, consider using S3 for better scalability
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=os.path.join(settings.BASE_DIR, "recom_sys_app", "static"),
    )
