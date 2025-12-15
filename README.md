# CINEMATCH
Team 4 CineMatch Project Setup

![Preview](https://github.com/gcivil-nyu-org/team4-mon-fall25/blob/sirish/Preview.jpg?raw=true)

An Agentic AI movie recommendation system that suggests movies based on your preferences and group matching.

## CI/CD Status

### Master
[![Build Status](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25.svg?branch=main)](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25)
[![Coverage Status](https://coveralls.io/repos/github/gcivil-nyu-org/team4-mon-fall25/badge.svg?branch=main)](https://coveralls.io/github/gcivil-nyu-org/team4-mon-fall25?branch=main)

### Develop
[![Build Status](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25.svg?branch=develop)](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25)
[![Coverage Status](https://coveralls.io/repos/github/gcivil-nyu-org/team4-mon-fall25/badge.svg?branch=develop)](https://coveralls.io/github/gcivil-nyu-org/team4-mon-fall25?branch=develop)

## Project Description

CineMatch is a movie recommendation system that uses AI and machine learning to suggest movies based on user preferences. The system integrates with TMDb for movie data and provides personalized recommendations through solo mode, group matching sessions, and community-based discovery.

## Features

- **User Authentication & Profiles**: Secure user accounts with customizable profiles and profile images
- **AI-Powered Recommendations**: Personalized movie suggestions based on user preferences and viewing history
- **Solo Mode**: Individual movie discovery with genre-based and history-based recommendations
- **Group Matching**: Create private groups to find movies everyone will enjoy
- **Community Mode**: Join genre-based communities to discover movies with like-minded viewers
- **Real-Time Chat**: WebSocket-powered chat for group and community sessions
- **Movie Interactions**: Like, dislike, and mark movies as watched
- **Match Notifications**: Real-time notifications when all group members like the same movie

## System Architecture

### Overview

CineMatch is built on Django with a microservices-oriented architecture:

```
┌─────────────────┐
│   CloudFront    │  ← HTTPS/CDN Layer
│   (CDN/Proxy)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │        │
┌───▼───┐ ┌──▼────┐
│   EB  │ │  S3   │  ← Application & Storage
│ (Django│ │(Media)│
└───┬───┘ └───────┘
    │
┌───▼────┐  ┌──────┐
│  RDS   │  │Redis │  ← Data Layer
│(Postgres│  │(Cache)│
└────────┘  └──────┘
```

### Components

1. **Frontend**: Django templates with JavaScript for interactive UI
2. **Backend**: Django REST Framework for API endpoints
3. **Real-Time**: Django Channels with WebSocket support
4. **Data Source**: TMDb API for movie metadata
5. **Storage**: 
   - PostgreSQL (RDS) for structured data
   - S3 for media files (profile images)
   - Redis for caching and WebSocket channels
6. **Infrastructure**: AWS Elastic Beanstalk, CloudFront, S3

### Data Flow

**Recommendation Request Flow:**
```
User Request → Django View → RecommendationService
                                    ↓
                    ┌───────────────┴───────────────┐
                    │                               │
            Check Cache                    Query TMDb API
                    │                               │
                    └───────────────┬───────────────┘
                                    ↓
                        Filter & Rank Movies
                                    ↓
                            Return to User
```

**WebSocket Flow:**
```
Browser → CloudFront → EB (Daphne/ASGI) → Redis → WebSocket Consumer
                                                      ↓
                                            Broadcast to Group
```

## Recommendation System Architecture

### Solo Mode Recommendations

The system provides personalized recommendations for individual users through multiple strategies:

#### 1. **History-Based Recommendations** (Returning Users)
- **Genre Analysis**: Analyzes genres from the user's last 10 liked movies
- **Genre Frequency**: Counts genre occurrences to identify top preferences
- **Top Genres**: Selects the top 3 most frequent genres
- **TMDb Discovery**: Fetches high-rated movies (vote_average.desc) from those genres
- **Quality Filter**: Only includes movies with at least 100 votes

#### 2. **Profile-Based Recommendations** (New Users)
- **Onboarding Preferences**: Uses `favourite_genre1` and `favourite_genre2` from user profile
- **Genre Mapping**: Converts genre names to TMDb genre IDs
- **Popular Movies**: Fetches popular movies from selected genres
- **Fallback**: If no preferences set, returns general popular movies

#### 3. **Similar Movies**
- **TMDb Recommendations API**: Uses TMDb's recommendation endpoint for similar movies
- **Genre Matching**: Only returns movies that share at least 2 genres with the original
- **Quality Filters**:
  - Movies from 2000 or newer
  - Minimum 100 votes
  - Rating of 5.0 or higher
- **Scoring**: Sorts by genre match score and vote average

### Group Mode Recommendations

#### Private Groups
- **Group History Analysis**: Analyzes all liked movies from group members
- **Common Genres**: Extracts genres from group's liked movies (up to 10 most recent)
- **Genre Frequency**: Identifies top 3 genres preferred by the group
- **Collaborative Filtering**: Recommends movies that match group preferences
- **Match Detection**: Detects when all active members like the same movie

#### Community Groups
- **Genre Filtering**: Filters movies by the community's genre (e.g., Action, Horror)
- **TMDb Discovery**: Fetches movies from the specific genre
- **Member History**: Excludes movies already swiped by any community member
- **Popular Fallback**: Uses popular movies if genre filter fails

### Technical Implementation

- **Caching**: 1-hour cache for deck recommendations and movie details (24-hour cache)
- **TMDb Integration**: Uses TMDb API v3 for movie data, posters, and recommendations
- **Database**: Stores user interactions, group sessions, and swipe history
- **Performance**: Pagination support, efficient queries, and cache invalidation

## Production Deployment

### Infrastructure

- **Elastic Beanstalk**: Django application hosting with auto-scaling
- **CloudFront CDN**: Global content delivery with HTTPS support
- **S3 Storage**: Media file storage (profile images) with public read access
- **RDS PostgreSQL**: Production database
- **Redis**: WebSocket channel layer for real-time features

### Configuration

#### Environment Variables

**Required:**
- `SECRET_KEY`: Django secret key
- `DEBUG`: Set to `False` in production
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `POSTGRES_*`: Database connection settings
- `TMDB_TOKEN` or `TMDB_API_KEY`: TMDb API authentication

**Optional (Production):**
- `USE_HTTPS`: Set to `True` for HTTPS redirects
- `PRODUCTION_DOMAIN`: Elastic Beanstalk domain
- `CLOUDFRONT_DOMAIN`: CloudFront distribution domain
- `WEBSOCKET_HOST`: Direct EB domain for WebSocket connections
- `AWS_STORAGE_BUCKET_NAME`: S3 bucket for media files
- `AWS_S3_REGION_NAME`: S3 region (default: us-east-1)
- `AWS_S3_CUSTOM_DOMAIN`: Custom S3 domain (optional)

#### CloudFront Configuration

- **WebSocket Support**: Configure `/ws/*` behavior with:
  - Cache policy: `CachingDisabled`
  - Origin request policy: `AllViewer` (forwards all headers)
  - Behavior order: `/ws/*` must be before default `*` behavior

- **Media Files**: Configure `/media/*` behavior OR use S3:
  - Option 1: CloudFront behavior pointing to EB origin
  - Option 2: S3 bucket with CloudFront distribution (recommended)

#### S3 Media Storage (Recommended)

1. Create S3 bucket with public read access
2. Configure bucket policy for public read
3. Set IAM permissions for EB instance role
4. Set environment variables: `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`
5. Media files automatically upload to S3

### Recent Updates

- **SSL/HTTPS Support**: Full HTTPS configuration with CloudFront
- **S3 Integration**: Media files stored in S3 for scalability
- **WebSocket Fixes**: CloudFront WebSocket support for real-time chat
- **Profile Images**: Fixed upload and display issues
- **Mixed Content**: Resolved HTTP/HTTPS mixed content warnings
- **Code Quality**: Black formatting and Flake8 linting

## Installation

1. Clone the repository
   ```bash
   git clone https://github.com/gcivil-nyu-org/team4-mon-fall25.git
   cd team4-mon-fall25
   ```

2. Create a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate  # Windows
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables
   - Copy `.env.example` to `.env`
   - Fill in required values (see `.env.example` for details)

5. Run migrations
   ```bash
   python manage.py migrate
   ```

6. Create superuser (optional)
   ```bash
   python manage.py createsu
   ```

7. Start the development server
   ```bash
   python manage.py runserver
   ```

## Testing

Run tests with coverage:
```bash
coverage run --source='.' manage.py test
coverage report
```

View detailed coverage:
```bash
coverage html
open htmlcov/index.html  # Opens coverage report in browser
```

## Development

### Code Quality

- **Black**: Code formatting (run `black .` before committing)
- **Flake8**: Linting (run `flake8` to check code style)
- **Pytest**: Testing framework

### Key Components

- **`recom_sys_app/services.py`**: Core recommendation logic
- **`recom_sys_app/views*.py`**: View handlers for different modes
- **`recom_sys_app/consumers.py`**: WebSocket consumers for real-time features
- **`recom_sys_app/models.py`**: Database models
- **`recommendation_sys/settings.py`**: Django configuration

## Build History

View full build history at: https://app.travis-ci.com/github/gcivil-nyu-org/team4-mon-fall25/builds

## License

This project is part of the GCivil NYU course work.
