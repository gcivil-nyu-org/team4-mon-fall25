# CineMatch - Teammate Setup & Deployment Guide

This guide will help you set up the CineMatch project locally and deploy changes to AWS Elastic Beanstalk.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Environment Variables & Credentials](#environment-variables--credentials)
4. [Running Locally](#running-locally)
5. [AWS Deployment](#aws-deployment)
6. [Common Issues & Troubleshooting](#common-issues--troubleshooting)

---

## Prerequisites

Install the following on your machine:

- **Python 3.11+** ([Download](https://www.python.org/downloads/))
- **Git** ([Download](https://git-scm.com/downloads))
- **PostgreSQL** (optional for local dev) ([Download](https://www.postgresql.org/download/))
- **AWS CLI** ([Installation Guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html))
- **AWS EB CLI** ([Installation Guide](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3-install.html))

---

## Local Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd CineMatch
git checkout develop
```

### 2. Create a Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Local Environment File

Create a `.env` file in the project root (same directory as `manage.py`):

```bash
# Copy the template
cp .env.example .env  # or create manually
```

**Ask your team lead for these values:**

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (leave as SQLite for local development)
# Or use PostgreSQL if you prefer:
# POSTGRES_DB=cinematch_local
# POSTGRES_USER=your_username
# POSTGRES_PASSWORD=your_password
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432

# TMDB API (Required - ask team lead)
TMDB_API_KEY=your-tmdb-api-key
TMDB_TOKEN=your-tmdb-bearer-token

# Groq API (Optional - for AI features)
GROQ_API_KEY=your-groq-api-key

# Redis (leave blank for local - uses InMemory)
# REDIS_HOST=
# REDIS_PORT=6379
```

### 5. Run Database Migrations

```bash
python manage.py migrate
```

### 6. Create a Superuser (Optional)

```bash
python manage.py createsuperuser
```

---

## Environment Variables & Credentials

### What You Need from Team Lead

Your team lead should provide you with:

#### 1. **API Keys** (add to `.env`):
   - `TMDB_API_KEY` - The Movie Database API key
   - `TMDB_TOKEN` - TMDB bearer token
   - `GROQ_API_KEY` - Groq AI API key (optional)

#### 2. **AWS Credentials** (for deployment only):
   - AWS Access Key ID
   - AWS Secret Access Key
   - AWS Region: `us-east-1`

#### 3. **AWS Resources Info**:
   - RDS Database credentials (PostgreSQL)
   - ElastiCache Redis endpoint
   - Elastic Beanstalk environment name: `cinematch-production`

#### 4. **SSH Key** (for debugging deployed instances):
   - `cinematch-keypair.pem` file (store in `~/.ssh/`)

### Setting Up AWS CLI

After receiving AWS credentials from your team lead:

```bash
aws configure
```

Enter:
- AWS Access Key ID: `<provided-by-team-lead>`
- AWS Secret Access Key: `<provided-by-team-lead>`
- Default region name: `us-east-1`
- Default output format: `json`

---

## Running Locally

### Start the Development Server

```bash
python manage.py runserver
```

Visit: [http://localhost:8000](http://localhost:8000)

### Running with Daphne (for WebSocket testing)

```bash
daphne -b 0.0.0.0 -p 8000 recommendation_sys.asgi:application
```

### Running Tests

```bash
python manage.py test
```

With coverage:
```bash
coverage run --source='.' manage.py test
coverage report
```

---

## AWS Deployment

### 1. Initialize EB CLI (First Time Only)

```bash
eb init
```

- Select region: `us-east-1`
- Select application: `cinematch-app`
- Choose Python 3.11

### 2. Set Up SSH (First Time Only)

Store the SSH key provided by your team lead:

**Windows:**
```bash
mkdir %USERPROFILE%\.ssh
copy cinematch-keypair.pem %USERPROFILE%\.ssh\
```

**Mac/Linux:**
```bash
mkdir -p ~/.ssh
cp cinematch-keypair.pem ~/.ssh/
chmod 400 ~/.ssh/cinematch-keypair.pem
```

### 3. Development Workflow

#### Step 1: Make Your Changes

Edit code, test locally, ensure everything works.

#### Step 2: Commit Your Changes

```bash
git add .
git commit -m "Description of your changes"
```

#### Step 3: Push to GitHub

```bash
git push origin develop
```

#### Step 4: Deploy to AWS

**Important:** Only deploy after your changes are tested locally!

```bash
eb deploy
```

Wait for deployment to complete (usually 2-3 minutes).

#### Step 5: Verify Deployment

```bash
eb status
eb health
```

Visit the production URL:
```
https://cinematch-production.eba-gnyn8qdp.us-east-1.elasticbeanstalk.com
```

### 4. Checking Logs

View recent application logs:
```bash
eb logs
```

SSH into the instance:
```bash
eb ssh
```

Check real-time logs (while SSH'd in):
```bash
sudo tail -f /var/log/web.stdout.log
```

### 5. Environment Variables on AWS

**DO NOT commit API keys to GitHub!**

To update environment variables on AWS:

```bash
eb setenv TMDB_API_KEY=your-key SECRET_KEY=your-secret
```

Or use the AWS Elastic Beanstalk console:
1. Go to AWS Console > Elastic Beanstalk
2. Select `cinematch-production` environment
3. Configuration > Software > Environment properties
4. Add/Edit variables

---

## Common Issues & Troubleshooting

### Issue: Database Connection Error

**Local:**
- Check if PostgreSQL is running
- Verify credentials in `.env`
- Try using SQLite (comment out POSTGRES variables)

**Production:**
- Verify RDS credentials in EB environment variables
- Check RDS security group allows connections from EB

### Issue: WebSocket Not Connecting

**Local:**
- Use Daphne instead of runserver: `daphne -b 0.0.0.0 -p 8000 recommendation_sys.asgi:application`
- Check browser console for connection errors

**Production:**
- WebSockets use InMemoryChannelLayer (single instance only)
- Check logs: `eb logs` or `eb ssh` then `sudo tail -f /var/log/web.stdout.log`

### Issue: Static Files Not Loading

**Local:**
```bash
python manage.py collectstatic
```

**Production:**
- Static files are served by WhiteNoise automatically
- Check `STATIC_ROOT` and `STATIC_URL` in settings.py

### Issue: EB Deploy Fails

1. Check git status: `git status`
2. Ensure all changes are committed
3. Check EB health: `eb health`
4. Review logs: `eb logs`
5. Try redeploying: `eb deploy`

### Issue: Module Not Found

```bash
pip install -r requirements.txt
```

If deploying:
```bash
git add requirements.txt
git commit -m "Update requirements"
eb deploy
```

### Issue: Permission Denied (SSH Key)

**Windows:**
- Ensure key is in `C:\Users\<YourName>\.ssh\`

**Mac/Linux:**
```bash
chmod 400 ~/.ssh/cinematch-keypair.pem
```

---

## Important Notes

1. **Never commit sensitive data:**
   - `.env` file is gitignored
   - Never hardcode API keys
   - Use environment variables

2. **Test before deploying:**
   - Run tests: `python manage.py test`
   - Test locally with production-like settings
   - Review changes with team

3. **Deployment best practices:**
   - Deploy during low-traffic times
   - Announce deployments to team
   - Monitor logs after deployment
   - Keep team informed of changes

4. **Code review:**
   - Create pull requests for major changes
   - Get code reviewed before merging to develop
   - Test thoroughly before deploying

5. **Database migrations:**
   - Always run migrations locally first
   - Check migration files before deploying
   - Migrations run automatically on EB deploy

---

## Quick Reference Commands

### Local Development
```bash
# Activate virtual environment
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate      # Windows

# Run server
python manage.py runserver

# Run tests
python manage.py test

# Make migrations
python manage.py makemigrations
python manage.py migrate
```

### Git Workflow
```bash
# Check status
git status

# Stage and commit
git add .
git commit -m "Your message"

# Push to GitHub
git push origin develop

# Pull latest changes
git pull origin develop
```

### AWS Deployment
```bash
# Check status
eb status

# Deploy
eb deploy

# View logs
eb logs

# SSH into instance
eb ssh

# Set environment variable
eb setenv KEY=value
```

---

## Getting Help

- **Team Lead:** Contact for credentials and AWS access
- **Documentation:** Check `AWS_DEPLOYMENT_GUIDE.md` for detailed AWS setup
- **Django Docs:** [https://docs.djangoproject.com/](https://docs.djangoproject.com/)
- **Elastic Beanstalk Docs:** [https://docs.aws.amazon.com/elasticbeanstalk/](https://docs.aws.amazon.com/elasticbeanstalk/)

---

## Team Collaboration Best Practices

1. **Communication:**
   - Notify team before deploying
   - Share what you're working on
   - Ask questions early

2. **Version Control:**
   - Pull latest changes before starting work: `git pull origin develop`
   - Commit often with clear messages
   - Resolve conflicts promptly

3. **Code Quality:**
   - Write tests for new features
   - Follow existing code style
   - Comment complex logic
   - Update documentation

4. **Deployment:**
   - Deploy tested code only
   - Monitor deployment success
   - Be ready to rollback if issues arise
   - Document any manual configuration changes

---

**Last Updated:** 2025-11-06
**Environment:** cinematch-production (us-east-1)
**Django Version:** 5.2.7
**Python Version:** 3.11
