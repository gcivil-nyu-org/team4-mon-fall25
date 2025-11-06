# CineMatch AWS Deployment Guide - Fresh Setup

## Overview
This guide will help you set up a clean, standardized AWS deployment for CineMatch with:
- **Application Name**: `cinematch-app`
- **Region**: `us-east-1`
- **Environment**: `cinematch-production`
- **Components**: EC2, RDS PostgreSQL, ElastiCache Redis, Elastic Beanstalk

---

## Prerequisites
- AWS Account with admin access
- EB CLI installed ✅ (v3.25.1)
- AWS credentials configured ✅ (~/.aws/config)
- Git repository ready

---

# STEP 1: Create EC2 Key Pair for SSH Access

## 1.1 Via AWS Console:
1. Go to **EC2 Dashboard**: https://console.aws.amazon.com/ec2/
2. Ensure region is **US East (N. Virginia) us-east-1** (top-right dropdown)
3. Left sidebar → **Network & Security** → **Key Pairs**
4. Click **Create key pair**
   - Name: `cinematch-keypair`
   - Key pair type: `RSA`
   - Private key file format: `.pem` (for SSH)
5. Click **Create key pair** → File downloads automatically
6. **IMPORTANT**: Save `cinematch-keypair.pem` securely
7. Set permissions (in Git Bash or WSL):
   ```bash
   chmod 400 ~/Downloads/cinematch-keypair.pem
   mv ~/Downloads/cinematch-keypair.pem ~/.ssh/
   ```

---

# STEP 2: Create RDS PostgreSQL Database

## 2.1 Via AWS Console:

1. Go to **RDS Dashboard**: https://console.aws.amazon.com/rds/
2. Ensure region is **us-east-1**
3. Click **Create database**

### Database Settings:
- **Engine type**: PostgreSQL
- **Engine Version**: PostgreSQL 15.x or 16.x (latest stable)
- **Templates**: Free tier (if eligible) OR Production (for actual deployment)

### Settings:
- **DB instance identifier**: `cinematch-db`
- **Master username**: `cinematch_admin`
- **Master password**: `CineMatch2025!Secure` (save this!)
- **Confirm password**: `CineMatch2025!Secure`

### Instance Configuration:
- **DB instance class**:
  - Free tier: `db.t3.micro` (1 vCPU, 1 GB RAM)
  - Production: `db.t3.small` or higher
- **Storage type**: General Purpose SSD (gp3)
- **Allocated storage**: 20 GB (can auto-scale to 100 GB)

### Connectivity:
- **Virtual private cloud (VPC)**: Default VPC
- **Subnet group**: default
- **Public access**: **Yes** (needed for EB to connect)
- **VPC security group**: Create new
  - **New VPC security group name**: `cinematch-db-sg`
- **Availability Zone**: No preference

### Database Authentication:
- **Database authentication**: Password authentication

### Additional Configuration:
- **Initial database name**: `cinematch_db`
- **DB parameter group**: default.postgres15 (or 16)
- **Backup retention period**: 7 days
- **Encryption**: Enable (default)
- **Enable automated backups**: Yes
- **Enable deletion protection**: No (for now, enable later for production)

4. Click **Create database**
5. **Wait 5-10 minutes** for creation to complete
6. Once "Available", click on `cinematch-db` and note:
   - **Endpoint**: (e.g., `cinematch-db.xxxxxx.us-east-1.rds.amazonaws.com`)
   - **Port**: 5432

## 2.2 Configure Security Group for RDS:

1. Click on the DB instance → **Connectivity & security** tab
2. Under **Security**, click the security group name (cinematch-db-sg)
3. Click **Inbound rules** tab → **Edit inbound rules**
4. Click **Add rule**:
   - **Type**: PostgreSQL
   - **Protocol**: TCP
   - **Port**: 5432
   - **Source**: Custom → `0.0.0.0/0` (allows EB instances to connect)
   - **Description**: Allow EB instances
5. Click **Save rules**

**Note**: For production, you'll update this to only allow the EB security group after creating the environment.

---

# STEP 3: Create ElastiCache Redis (for WebSocket/Channels)

## 3.1 Via AWS Console:

1. Go to **ElastiCache Dashboard**: https://console.aws.amazon.com/elasticache/
2. Ensure region is **us-east-1**
3. Left sidebar → Click **Redis OSS caches**
4. Click **Create Redis OSS cache**

### Cache Settings:
- **Deployment option**: Design your own cache
- **Creation method**: Easy create OR Cluster cache
- **Name**: `cinematch-redis`
- **Engine version**: 7.1 (latest)
- **Port**: 6379 (default)
- **Parameter group**: default.redis7
- **Node type**:
  - Free tier/Dev: `cache.t3.micro` (0.5 GB)
  - Production: `cache.t3.small` or higher
- **Number of replicas**: 0 (for dev) or 1 (for production)

### Connectivity:
- **Network type**: IPv4
- **Subnet group**: Create new
  - **Name**: `cinematch-redis-subnet`
  - **VPC**: Default VPC
  - **Subnets**: Select all available
- **Availability zone placement**: No preference

### Advanced Settings:
- **Security groups**: Create new
  - **Name**: `cinematch-redis-sg`
- **Encryption at rest**: Enabled
- **Encryption in transit**: Disabled (easier for EB, but enable for production)

5. Click **Create**
6. **Wait 5-10 minutes** for creation
7. Once "Available", click on `cinematch-redis` and note:
   - **Primary endpoint**: (e.g., `cinematch-redis.xxxxxx.0001.use1.cache.amazonaws.com:6379`)

## 3.2 Configure Redis Security Group:

1. Go to **EC2 Dashboard** → **Security Groups**
2. Find `cinematch-redis-sg`
3. **Inbound rules** → **Edit inbound rules**
4. Add rule:
   - **Type**: Custom TCP
   - **Port**: 6379
   - **Source**: Custom → `0.0.0.0/0`
   - **Description**: Allow EB instances
5. **Save rules**

---

# STEP 4: Initialize Elastic Beanstalk Application

## 4.1 Via Command Line (EB CLI):

```bash
# Navigate to project directory
cd "c:\Users\siris\OneDrive\Desktop\NYU\3.Fall 2025\SOFTWARE ENGINEERING\CineMatch"

# Initialize new EB application
eb init

# Answer the prompts:
# 1. Select a default region: 1) us-east-1
# 2. Enter Application Name: cinematch-app
# 3. It appears you are using Python. Is this correct? Y
# 4. Select a platform version: 1) Python 3.11 running on 64bit Amazon Linux 2023
# 5. Do you wish to continue with CodeCommit? n
# 6. Do you want to set up SSH for your instances? Y
# 7. Select a keypair: cinematch-keypair (the one we created)
```

This creates `.elasticbeanstalk/config.yml` with proper settings.

---

# STEP 5: Update Environment Variable Configuration

## 5.1 Update `.ebextensions/03_env_vars.config`:

Create a proper config file with the actual values from RDS and Redis:

```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    DJANGO_SETTINGS_MODULE: recommendation_sys.settings
    SECRET_KEY: "django-insecure-CHANGE-THIS-IN-PRODUCTION"
    DEBUG: "False"
    ALLOWED_HOSTS: ".elasticbeanstalk.com,.us-east-1.elasticbeanstalk.com,localhost,127.0.0.1"

    # PostgreSQL RDS Configuration
    POSTGRES_DB: "cinematch_db"
    POSTGRES_USER: "cinematch_admin"
    POSTGRES_PASSWORD: "CineMatch2025!Secure"
    POSTGRES_HOST: "cinematch-db.XXXXXX.us-east-1.rds.amazonaws.com"  # UPDATE THIS
    POSTGRES_PORT: "5432"

    # Redis ElastiCache Configuration
    REDIS_HOST: "cinematch-redis.XXXXXX.0001.use1.cache.amazonaws.com"  # UPDATE THIS
    REDIS_PORT: "6379"

    # API Keys (get from team lead)
    GROQ_API_KEY: "your-groq-api-key"
    TMDB_TOKEN: "your-tmdb-bearer-token"
    TMDB_API_KEY: "your-tmdb-api-key"
    MOVIES_PATH: "movies.txt"
```

**Important**: Replace `XXXXXX` with actual endpoints from Step 2 and 3.

---

# STEP 6: Update Django Settings for Redis Channels

## 6.1 Ensure settings.py has Redis configuration:

The app needs to use Redis for Channels. Check `recommendation_sys/settings.py`:

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(
                os.getenv('REDIS_HOST', 'localhost'),
                int(os.getenv('REDIS_PORT', 6379))
            )],
        },
    },
}
```

---

# STEP 7: Create Elastic Beanstalk Environment

## 7.1 Via EB CLI:

```bash
# Create environment
eb create cinematch-production \
  --instance-type t3.small \
  --platform "python-3.11" \
  --region us-east-1 \
  --keyname cinematch-keypair \
  --enable-spot \
  --timeout 20

# This will:
# 1. Create EC2 instance(s)
# 2. Create load balancer
# 3. Create security groups
# 4. Deploy your application
# 5. Run migrations (via .ebextensions/01_django.config)
```

Wait 10-15 minutes for environment creation.

## 7.2 Alternative: Via AWS Console:

1. Go to **Elastic Beanstalk Console**: https://console.aws.amazon.com/elasticbeanstalk/
2. Ensure region is **us-east-1**
3. Find application `cinematch-app` (created by `eb init`)
4. Click **Create environment**
   - **Environment tier**: Web server environment
   - **Environment name**: `cinematch-production`
   - **Domain**: `cinematch-production` (or custom)
   - **Platform**: Python 3.11 running on 64bit Amazon Linux 2023
   - **Application code**: Sample application (we'll deploy later)
5. Click **Configure more options**

### Presets: High availability (for production) or Single instance (for testing)

### Edit Instances:
- **Instance type**: t3.small (minimum for WebSockets)
- **EC2 key pair**: cinematch-keypair

### Edit Capacity:
- **Environment type**: Single instance (dev) or Load balanced (prod)
- **Instances**: Min 1, Max 2
- **Instance type**: t3.small

### Edit Security:
- **EC2 key pair**: cinematch-keypair

6. Click **Create environment**

---

# STEP 8: Update Security Groups for Communication

After EB environment is created, we need to allow EB instances to access RDS and Redis.

## 8.1 Get EB Security Group ID:

1. Go to **EC2 Dashboard** → **Security Groups**
2. Find security group with name containing `cinematch-production` (e.g., `sg-xxxxxx`)
3. Note the **Security group ID** (e.g., `sg-0a1b2c3d4e5f6`)

## 8.2 Update RDS Security Group:

1. Find `cinematch-db-sg` security group
2. **Edit inbound rules**
3. Update the PostgreSQL rule:
   - **Source**: Change from `0.0.0.0/0` to the EB security group ID (sg-xxxxxx)
   - **Description**: Allow EB instances
4. **Save rules**

## 8.3 Update Redis Security Group:

1. Find `cinematch-redis-sg` security group
2. **Edit inbound rules**
3. Update the 6379 rule:
   - **Source**: Change from `0.0.0.0/0` to the EB security group ID
   - **Description**: Allow EB instances
4. **Save rules**

---

# STEP 9: Set Environment Variables in EB Console

## 9.1 Via AWS Console (Recommended for sensitive data):

1. Go to **Elastic Beanstalk** → `cinematch-production` environment
2. Left sidebar → **Configuration**
3. **Updates, monitoring, and logging** → **Edit**
4. Scroll to **Environment properties**
5. Add all variables from `.ebextensions/03_env_vars.config`:
   - SECRET_KEY
   - DEBUG = False
   - ALLOWED_HOSTS
   - POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
   - REDIS_HOST, REDIS_PORT
   - GROQ_API_KEY, TMDB_TOKEN, TMDB_API_KEY, MOVIES_PATH
6. Click **Apply**

## 9.2 Verify Configuration:

```bash
eb printenv
```

This should show all your environment variables.

---

# STEP 10: Deploy Application

## 10.1 Commit Latest Changes:

```bash
git add .
git commit -m "Configure for cinematch-app deployment in us-east-1"
```

## 10.2 Deploy to EB:

```bash
eb deploy cinematch-production
```

Wait 5-10 minutes. The deployment will:
1. Upload code to S3
2. Deploy to EC2 instances
3. Run migrations (via .ebextensions/01_django.config)
4. Collect static files
5. Restart Daphne server

## 10.3 Monitor Deployment:

```bash
# Check status
eb status

# View logs
eb logs

# Open application in browser
eb open
```

---

# STEP 11: Test SSH Access and Migrations

## 11.1 SSH into EC2 Instance:

```bash
eb ssh cinematch-production
```

Or manually:
```bash
ssh -i ~/.ssh/cinematch-keypair.pem ec2-user@<instance-ip>
```

## 11.2 Once Connected, Verify:

```bash
# Check if app is running
sudo supervisorctl status all

# Check Daphne process
ps aux | grep daphne

# Navigate to app directory
cd /var/app/current

# Check Python environment
source /var/app/venv/*/bin/activate

# Run migrations manually (if needed)
python manage.py migrate

# Create superuser (if needed)
python manage.py createsu

# Check database connection
python manage.py dbshell
# Then: \dt  (to list tables)
# Then: \q   (to quit)

# Check Redis connection
redis-cli -h <redis-endpoint> ping
# Should return: PONG

# View application logs
tail -f /var/log/eb-engine.log
tail -f /var/log/web.stdout.log

# Exit SSH
exit
```

---

# STEP 12: Test Group Chat Functionality

## 12.1 Via Browser:

1. Open application: `eb open` or visit the EB URL
2. Register/login as multiple users (use incognito windows)
3. Create a group session
4. Join from multiple browsers
5. Test:
   - ✅ Chat messages appear in real-time
   - ✅ Swiping works
   - ✅ Matches are detected
   - ✅ Notifications appear

## 12.2 Check WebSocket Connection:

In browser console (F12):
```javascript
// Should see WebSocket connection established
// ws://your-domain.elasticbeanstalk.com/ws/chat/<group_id>/
```

## 12.3 Troubleshooting Group Chat:

If group chat doesn't work, check:

```bash
# SSH into instance
eb ssh cinematch-production

# Check if Redis is accessible
redis-cli -h <REDIS_HOST> ping

# Check Daphne logs
sudo tail -f /var/log/web.stdout.log

# Check if Daphne is running on port 8000
sudo netstat -tlnp | grep 8000

# Restart application
sudo systemctl restart web.service
```

---

# STEP 13: Enable HTTPS (Optional but Recommended)

## 13.1 Via EB Console:

1. Go to **Configuration** → **Load balancer**
2. Click **Edit**
3. **Listeners** → **Add listener**:
   - **Port**: 443
   - **Protocol**: HTTPS
   - **SSL certificate**: Request from ACM or upload your own
4. Click **Apply**

---

# STEP 14: Set Up Custom Domain (Optional)

## 14.1 Via Route 53:

1. Register domain or use existing
2. Create hosted zone
3. Add CNAME record pointing to EB URL
4. Update ALLOWED_HOSTS to include your domain

---

# Summary of Resources Created

## AWS Resources:
- ✅ **Application**: `cinematch-app` (us-east-1)
- ✅ **Environment**: `cinematch-production` (us-east-1)
- ✅ **EC2 Instance**: t3.small with cinematch-keypair
- ✅ **RDS PostgreSQL**: `cinematch-db` (cinematch_db database)
- ✅ **ElastiCache Redis**: `cinematch-redis` (for WebSocket channels)
- ✅ **Security Groups**: cinematch-db-sg, cinematch-redis-sg, EB security group
- ✅ **Load Balancer**: (if using high availability)

## Endpoints:
- **Application URL**: `cinematch-production.us-east-1.elasticbeanstalk.com`
- **RDS Endpoint**: `cinematch-db.xxxxxx.us-east-1.rds.amazonaws.com:5432`
- **Redis Endpoint**: `cinematch-redis.xxxxxx.0001.use1.cache.amazonaws.com:6379`

## Credentials:
- **DB User**: cinematch_admin
- **DB Password**: CineMatch2025!Secure
- **DB Name**: cinematch_db
- **SSH Key**: ~/.ssh/cinematch-keypair.pem

---

# Quick Reference Commands

```bash
# Deploy application
eb deploy cinematch-production

# Check status
eb status

# View logs
eb logs

# SSH into instance
eb ssh cinematch-production

# Open in browser
eb open

# View environment variables
eb printenv

# Set environment variable
eb setenv KEY=VALUE

# Restart application
eb restart

# Terminate environment (CAREFUL!)
eb terminate cinematch-production
```

---

# Troubleshooting

## Issue: Migrations not running
**Solution**: SSH in and run manually:
```bash
eb ssh cinematch-production
cd /var/app/current
source /var/app/venv/*/bin/activate
python manage.py migrate
```

## Issue: Group chat not working
**Solution**: Check Redis connection and Daphne server
```bash
# Check Redis
redis-cli -h $REDIS_HOST ping

# Check Daphne process
ps aux | grep daphne

# Restart
sudo systemctl restart web.service
```

## Issue: Database connection errors
**Solution**: Verify security groups allow EB → RDS connection

## Issue: Static files not loading
**Solution**: Run collectstatic
```bash
python manage.py collectstatic --noinput
```

---

# Next Steps

1. ✅ Complete all steps above
2. ✅ Test all functionality (solo mode, group mode, chat)
3. ✅ Monitor logs for errors
4. ⚠️ Change SECRET_KEY to a secure random value
5. ⚠️ Enable HTTPS for production
6. ⚠️ Set up automated backups
7. ⚠️ Configure monitoring/alerting
8. ⚠️ Enable RDS deletion protection for production

---

**Good luck with your deployment!** 🚀
