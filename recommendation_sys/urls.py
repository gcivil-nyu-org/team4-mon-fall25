"""
URL configuration for recommendation_sys project.
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def root_redirect(request):
    return redirect("login")

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", root_redirect),
    path("", include("recom_sys_app.urls")),  # ← Changed from "api/" to ""
]