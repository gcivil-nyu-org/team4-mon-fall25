# CineMatch AWS Deployment Checklist

Use this checklist to track your deployment progress. Follow the detailed guide in [AWS_DEPLOYMENT_GUIDE.md](AWS_DEPLOYMENT_GUIDE.md).

---

## Pre-Deployment Cleanup

- [x] Deleted all old EB environments from AWS Console
- [x] Deleted all old EC2 instances from AWS Console
- [x] Deleted old EB configuration locally (`.elasticbeanstalk/`)
- [x] Updated `settings.py` for Redis support
- [x] Updated `.ebextensions/03_env_vars.config` template

---

## Step 1: EC2 Key Pair

- [ ] Created EC2 key pair named `cinematch-keypair` in us-east-1
- [ ] Downloaded `cinematch-keypair.pem` file
- [ ] Moved to `~/.ssh/cinematch-keypair.pem`
- [ ] Set permissions: `chmod 400 ~/.ssh/cinematch-keypair.pem`

**Key Name**: `cinematch-keypair`
**Location**: `~/.ssh/cinematch-keypair.pem`

---

## Step 2: RDS PostgreSQL Database

- [ ] Created RDS PostgreSQL instance in us-east-1
- [ ] Configured with public access enabled
- [ ] Created security group `cinematch-db-sg`
- [ ] Added inbound rule for PostgreSQL (port 5432)
- [ ] Database is "Available" status

**Record These Values:**
```
DB Identifier: cinematch-db
DB Name: cinematch_db
Master Username: cinematch_admin
Master Password: CineMatch2025!Secure
Endpoint: ___________________________________.us-east-1.rds.amazonaws.com
Port: 5432
Security Group: cinematch-db-sg
```

---

## Step 3: ElastiCache Redis

- [ ] Created Redis cluster in us-east-1
- [ ] Configured in default VPC
- [ ] Created security group `cinematch-redis-sg`
- [ ] Added inbound rule for Redis (port 6379)
- [ ] Redis cluster is "Available" status

**Record These Values:**
```
Cluster Name: cinematch-redis
Primary Endpoint: ___________________________________.0001.use1.cache.amazonaws.com:6379
Port: 6379
Security Group: cinematch-redis-sg
```

---

## Step 4: Update Configuration Files

- [ ] Updated `.ebextensions/03_env_vars.config` with RDS endpoint
- [ ] Updated `.ebextensions/03_env_vars.config` with Redis endpoint
- [ ] Verified all environment variables are set correctly
- [ ] Committed changes to git

**Update these lines in `.ebextensions/03_env_vars.config`:**
```yaml
POSTGRES_HOST: "YOUR-RDS-ENDPOINT-HERE"
REDIS_HOST: "YOUR-REDIS-ENDPOINT-HERE"
```

---

## Step 5: Initialize Elastic Beanstalk

- [ ] Ran `eb init` command
- [ ] Selected region: **us-east-1**
- [ ] Application name: **cinematch-app**
- [ ] Platform: **Python 3.11**
- [ ] Configured SSH with `cinematch-keypair`
- [ ] Verified `.elasticbeanstalk/config.yml` created

**Application Details:**
```
Application Name: cinematch-app
Region: us-east-1
Platform: Python 3.11 on Amazon Linux 2023
SSH Key: cinematch-keypair
```

---

## Step 6: Create EB Environment

- [ ] Ran `eb create cinematch-production` command
- [ ] Environment created successfully
- [ ] Load balancer created (if using)
- [ ] EC2 instances launched
- [ ] Application deployed
- [ ] Environment is "Green" status

**Environment Details:**
```
Environment Name: cinematch-production
URL: _____________________________________.us-east-1.elasticbeanstalk.com
Instance Type: t3.small
Status: Green
```

---

## Step 7: Update Security Groups

- [ ] Found EB security group ID (e.g., sg-xxxxxxxxx)
- [ ] Updated RDS security group inbound rule to EB security group
- [ ] Updated Redis security group inbound rule to EB security group
- [ ] Tested connectivity from EB to RDS
- [ ] Tested connectivity from EB to Redis

**Security Group IDs:**
```
EB Security Group: sg-_______________________
RDS Security Group: cinematch-db-sg (updated to allow EB SG)
Redis Security Group: cinematch-redis-sg (updated to allow EB SG)
```

---

## Step 8: Set Environment Variables

- [ ] Went to EB Console → Configuration → Environment Properties
- [ ] Set all environment variables (SECRET_KEY, DEBUG, etc.)
- [ ] Set POSTGRES_HOST with actual RDS endpoint
- [ ] Set REDIS_HOST with actual Redis endpoint
- [ ] Verified with `eb printenv`
- [ ] Applied configuration changes

---

## Step 9: Deploy Application

- [ ] Committed all code changes to git
- [ ] Ran `eb deploy cinematch-production`
- [ ] Deployment completed successfully
- [ ] Migrations ran automatically
- [ ] Static files collected
- [ ] Application started

**Verify Deployment:**
```bash
eb status              # Check status
eb logs                # Check for errors
eb open                # Open in browser
```

---

## Step 10: Test SSH and Migrations

- [ ] SSH'd into EC2: `eb ssh cinematch-production`
- [ ] Verified Daphne process running: `ps aux | grep daphne`
- [ ] Checked migrations: `python manage.py showmigrations`
- [ ] Ran migrations if needed: `python manage.py migrate`
- [ ] Created superuser: `python manage.py createsu`
- [ ] Tested database connection: `python manage.py dbshell`
- [ ] Tested Redis connection: `redis-cli -h $REDIS_HOST ping`

**Verification Results:**
- Daphne running: [ ] Yes [ ] No
- Migrations complete: [ ] Yes [ ] No
- Database accessible: [ ] Yes [ ] No
- Redis accessible: [ ] Yes [ ] No

---

## Step 11: Test Group Chat Functionality

- [ ] Opened application in browser
- [ ] Created test user account
- [ ] Created group session
- [ ] Joined group from different browser/incognito
- [ ] Tested chat messages (real-time)
- [ ] Tested swiping functionality
- [ ] Tested match detection
- [ ] Verified WebSocket connection in browser console

**Group Chat Test Results:**
- Chat messages work: [ ] Yes [ ] No
- Swiping works: [ ] Yes [ ] No
- Matches detected: [ ] Yes [ ] No
- WebSocket connected: [ ] Yes [ ] No

---

## Step 12: Production Hardening (Optional)

- [ ] Enabled HTTPS (SSL certificate via ACM)
- [ ] Changed SECRET_KEY to secure random value
- [ ] Updated security groups to restrict access
- [ ] Enabled RDS deletion protection
- [ ] Set up automated backups
- [ ] Configured CloudWatch monitoring
- [ ] Set up CloudWatch alarms
- [ ] Configured auto-scaling (if needed)

---

## Troubleshooting Commands

If something goes wrong, use these commands:

```bash
# View logs
eb logs

# SSH into instance
eb ssh cinematch-production

# Check application status
eb status

# View environment variables
eb printenv

# Restart application
eb restart

# Check Daphne process
ps aux | grep daphne

# Check database connection
python manage.py dbshell

# Check Redis connection
redis-cli -h $REDIS_HOST ping

# View Django logs
tail -f /var/log/web.stdout.log

# Run migrations manually
python manage.py migrate

# Create superuser
python manage.py createsu
```

---

## Common Issues and Solutions

### Issue: Group chat not working
**Solution:**
1. Verify REDIS_HOST environment variable is set
2. Check Redis security group allows EB instances
3. Test Redis connection: `redis-cli -h $REDIS_HOST ping`
4. Check Daphne logs: `tail -f /var/log/web.stdout.log`

### Issue: Database connection errors
**Solution:**
1. Verify POSTGRES_HOST is correct RDS endpoint
2. Check RDS security group allows EB instances
3. Test database connection: `python manage.py dbshell`
4. Verify credentials in environment variables

### Issue: Migrations not running
**Solution:**
1. SSH into instance
2. Run manually: `python manage.py migrate`
3. Check `.ebextensions/01_django.config` container commands

### Issue: Static files not loading
**Solution:**
1. Run: `python manage.py collectstatic --noinput`
2. Check STATIC_ROOT and WhiteNoise configuration

---

## Final Checklist

- [ ] Application URL is accessible
- [ ] Can register new users
- [ ] Can login/logout
- [ ] Solo mode works (swiping, recommendations)
- [ ] Group mode works (create, join)
- [ ] Group chat works (real-time messages)
- [ ] Group swiping works
- [ ] Matches are detected
- [ ] Admin panel accessible (/admin)
- [ ] All API endpoints working
- [ ] No errors in logs
- [ ] SSL/HTTPS enabled (production)
- [ ] Environment variables secured
- [ ] Database backups enabled

---

## Important URLs

- **Application**: https://_____________________________________.us-east-1.elasticbeanstalk.com
- **Admin Panel**: https://_____________________________________.us-east-1.elasticbeanstalk.com/admin
- **EB Console**: https://console.aws.amazon.com/elasticbeanstalk/home?region=us-east-1
- **RDS Console**: https://console.aws.amazon.com/rds/home?region=us-east-1
- **ElastiCache Console**: https://console.aws.amazon.com/elasticache/home?region=us-east-1
- **EC2 Console**: https://console.aws.amazon.com/ec2/home?region=us-east-1

---

**Deployment Date**: _______________
**Deployed By**: _______________
**Status**: [ ] In Progress [ ] Completed [ ] Issues

---

Good luck! 🚀
