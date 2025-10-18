"""
URL configuration for recommendation_sys project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from django.shortcuts import redirect

def root_view(request):
    """
    Root path handler:
    - Returns 200 OK for ELB health checker
    - Redirects to login for regular users
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    # Check if request is from AWS ELB health checker
    if 'ELB-HealthChecker' in user_agent:
        return HttpResponse("OK", status=200)

    # Regular users: redirect based on authentication
    if request.user.is_authenticated:
        return redirect("profile")
    return redirect("login")

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", root_view),  # Smart root handler
    path("", include("recom_sys_app.urls", namespace='recom_sys')),  # App routes
]