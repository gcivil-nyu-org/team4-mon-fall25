"""
URL configuration for recommendation_sys project.
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

import os
from django.conf import settings
from django.conf.urls.static import static


def root_view(request):
    """
    Root path handler:
    - Returns 200 OK for ELB health checker
    - Serves React app for regular users
    """
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    # Check if request is from AWS ELB health checker
    if "ELB-HealthChecker" in user_agent:
        return HttpResponse("OK", status=200)

    # Serve React app
    index_path = os.path.join(settings.BASE_DIR, "frontend", "dist", "index.html")
    with open(index_path) as f:
        return HttpResponse(f.read())


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "", include("recom_sys_app.urls", namespace="recom_sys")
    ),  # App routes - MUST come first
    re_path(r"^.*$", root_view),  # Catch-all for React routes (SPA)
]
if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=os.path.join(settings.BASE_DIR, "recom_sys_app", "static"),
    )
