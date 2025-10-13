"""
URL configuration for recommendation_sys project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def health_check(request):
    """Health check for AWS ELB - returns 200 OK"""
    return HttpResponse("OK", status=200)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", health_check),  # Health check at root for ELB
    path("", include("recom_sys_app.urls")),  # App routes
]