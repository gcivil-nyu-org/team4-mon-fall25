from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

def register_view(request):
    if request.user.is_authenticated:
        return redirect('movies:movie_list')

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            login(request, user)
            return redirect('movies:movie_list')
    else:
        form = UserCreationForm()

    return render(request, 'accounts/register.html', {'form': form})

def landing_view(request):
    if request.user.is_authenticated:
        return redirect('movies:movie_list')
    return render(request, 'accounts/landing.html')
