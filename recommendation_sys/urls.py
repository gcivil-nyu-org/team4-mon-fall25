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
    - Redirects to login for regular users
    """
    user_agent = request.META.get("HTTP_USER_AGENT", "")

    # Check if request is from AWS ELB health checker
    if "ELB-HealthChecker" in user_agent:
        return HttpResponse("OK", status=200)

    # Regular users: redirect based on authentication
    if request.user.is_authenticated:
        return redirect("recom_sys:profile")
    return redirect("recom_sys:login")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", root_view),  # Smart root handler
    path("", include("recom_sys_app.urls", namespace="recom_sys")),  # App routes
]
if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=os.path.join(settings.BASE_DIR, "recom_sys_app", "static"),
    )
