from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Movie

def movie_list(request):
    """Display a paginated list of movies"""
    movies = Movie.objects.all()
    paginator = Paginator(movies, 20)  # Show 20 movies per page

    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'movies/movie_list.html', {'page_obj': page_obj})

def movie_detail(request, movie_id):
    """Display detailed information about a specific movie"""
    movie = get_object_or_404(Movie, id=movie_id)
    return render(request, 'movies/movie_detail.html', {'movie': movie})
