# recom_sys_app/views_auth.py
from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import SignUpForm

def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("profile")
    else:
        form = SignUpForm()

    # Debug line to ensure the right form is used:
    # print("SIGNUP FORM CLASS:", form.__class__.__name__)

    return render(request, "recom_sys_app/signup.html", {"form": form})
