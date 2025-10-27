# CINEMATCH
Team 4 CineMatch Project Setup

![Preview](https://github.com/gcivil-nyu-org/team4-mon-fall25/blob/sirish/Preview.jpg?raw=true)
An Agentic AI movie recommendation system that suggests you movies based on your previous liking : )

## CI/CD Status

### Build Status
[![Build Status](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25.svg?branch=main)](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25)
[![Build Status](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25.svg?branch=develop)](https://app.travis-ci.com/gcivil-nyu-org/team4-mon-fall25)

### Test Coverage
[![Coverage Status](https://coveralls.io/repos/github/gcivil-nyu-org/team4-mon-fall25/badge.svg?branch=main)](https://coveralls.io/github/gcivil-nyu-org/team4-mon-fall25?branch=main)
[![Coverage Status](https://coveralls.io/repos/github/gcivil-nyu-org/team4-mon-fall25/badge.svg?branch=develop)](https://coveralls.io/github/gcivil-nyu-org/team4-mon-fall25?branch=develop)

## Code Quality Tools

Our CI/CD pipeline includes:
- **Black**: Code formatting
- **Flake8**: Linting
- **Bandit**: Security vulnerability scanning
- **Coverage**: Test coverage reporting (85%+)

## Project Description

CineMatch is a movie recommendation system that uses AI to suggest movies based on user preferences. The system integrates with TMDb for movie data and uses machine learning to provide personalized recommendations.

## Features

- User authentication and profiles
- AI-powered movie recommendations
- Group movie matching sessions
- User interactions (like, dislike, watch later)
- Personalized recommendations based on preferences

## Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate virtual environment: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Set up environment variables (see `.env.example`)
6. Run migrations: `python manage.py migrate`
7. Start the server: `python manage.py runserver`

## Testing

Run tests with coverage:
```bash
coverage run --source='.' manage.py test
coverage report
```

## Build History

View full build history at: https://app.travis-ci.com/github/gcivil-nyu-org/team4-mon-fall25/builds
