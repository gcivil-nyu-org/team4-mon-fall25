# Quick Start Deployment Guide

**Fast track guide to get CineMatch deployed on AWS in ~30 minutes**

---

## Prerequisites Check

```bash
# 1. Check EB CLI installed
eb --version
# Should show: EB CLI 3.25.1

# 2. Check AWS credentials
cat ~/.aws/config
# Should show your AWS access keys

# 3. Check you're in the project directory
pwd
# Should be: c:\Users\siris\OneDrive\Desktop\NYU\3.Fall 2025\SOFTWARE ENGINEERING\CineMatch
```

---

## Part 1: AWS Console Setup (15 minutes)

### 1. Create EC2 Key Pair (2 min)
1. Go to: https://console.aws.amazon.com/ec2/
2. **Region dropdown (top-right)** → Select **US East (N. Virginia)**
3. Left menu → **Key Pairs** → **Create key pair**
   - Name: `cinematch-keypair`
   - Type: RSA
   - Format: .pem
4. Download → Save to `~/.ssh/cinematch-keypair.pem`
5. In Git Bash/WSL:
   ```bash
   chmod 400 ~/.ssh/cinematch-keypair.pem
   ```

### 2. Create RDS Database (5 min)
1. Go to: https://console.aws.amazon.com/rds/
2. **Ensure region is us-east-1** (top-right)
3. **Create database**
   - Engine: **PostgreSQL** (latest version)
   - Templates: **Free tier** (or Production)
   - DB instance identifier: `cinematch-db`
   - Master username: `cinematch_admin`
   - Master password: `CineMatch2025!Secure`
   - DB instance class: `db.t3.micro` (free tier) or `db.t3.small`
   - Storage: 20 GB
   - **Public access: Yes** ✅
   - VPC security group: Create new → `cinematch-db-sg`
   - Initial database name: `cinematch_db`
4. **Create database** → Wait ~5 min
5. **Copy the Endpoint** (looks like: `cinematch-db.xxxxx.us-east-1.rds.amazonaws.com`)

### 3. Configure RDS Security Group (1 min)
1. Click on database → **Connectivity & security** tab
2. Click security group name → **Inbound rules** → **Edit inbound rules**
3. **Add rule**:
   - Type: PostgreSQL
   - Source: 0.0.0.0/0
4. **Save rules**

### 4. Create ElastiCache Redis (5 min)
1. Go to: https://console.aws.amazon.com/elasticache/
2. **Ensure region is us-east-1**
3. **Redis OSS caches** → **Create Redis OSS cache**
   - Name: `cinematch-redis`
   - Engine version: 7.1
   - Node type: `cache.t3.micro`
   - Replicas: 0
   - Subnet group: Create new
   - Security groups: Create new → `cinematch-redis-sg`
4. **Create** → Wait ~5 min
5. **Copy the Primary Endpoint** (looks like: `cinematch-redis.xxxxx.0001.use1.cache.amazonaws.com:6379`)

### 5. Configure Redis Security Group (1 min)
1. Go to: https://console.aws.amazon.com/ec2/
2. Left menu → **Security Groups** → Find `cinematch-redis-sg`
3. **Inbound rules** → **Edit inbound rules**
4. **Add rule**:
   - Type: Custom TCP
   - Port: 6379
   - Source: 0.0.0.0/0
5. **Save rules**

---

## Part 2: Local Configuration (5 minutes)

### 6. Update Environment Config File

Edit `.ebextensions/03_env_vars.config`:

```bash
# Open in VS Code or your editor
code .ebextensions/03_env_vars.config
```

**Replace these two lines with your actual endpoints:**
```yaml
POSTGRES_HOST: "cinematch-db.XXXXX.us-east-1.rds.amazonaws.com"  # Paste your RDS endpoint here
REDIS_HOST: "cinematch-redis.XXXXX.0001.use1.cache.amazonaws.com"  # Paste your Redis endpoint here
```

**Save the file.**

---

## Part 3: Deploy with EB CLI (10 minutes)

### 7. Initialize EB Application

```bash
# Initialize (only need to do this once)
eb init

# Follow prompts:
# Region: 1 (us-east-1)
# Application name: cinematch-app
# Python?: Y
# Platform version: 1 (Python 3.11)
# CodeCommit?: n
# SSH?: Y
# Keypair: cinematch-keypair
```

### 8. Create and Deploy Environment

```bash
# Create environment and deploy in one command
eb create cinematch-production \
  --instance-type t3.small \
  --platform "python-3.11" \
  --region us-east-1 \
  --keyname cinematch-keypair
```

**This will take ~10 minutes.** It creates:
- EC2 instance(s)
- Load balancer
- Security groups
- Deploys your app
- Runs migrations automatically

### 9. Update Security Groups for Production

Once environment is created, we need to secure the connections:

```bash
# Get EB security group ID
eb ssh cinematch-production
# In SSH session, run:
curl http://169.254.169.254/latest/meta-data/security-groups
# Copy the security group name (e.g., sg-0abc123...)
exit
```

Or find it in AWS Console:
1. Go to: https://console.aws.amazon.com/ec2/
2. **Security Groups** → Find one with `cinematch-production` in name
3. Copy the **Security Group ID** (e.g., `sg-0abc123def456`)

**Update RDS Security Group:**
1. Find `cinematch-db-sg` → Edit inbound rules
2. Change PostgreSQL rule source from `0.0.0.0/0` to the EB security group ID

**Update Redis Security Group:**
1. Find `cinematch-redis-sg` → Edit inbound rules
2. Change port 6379 rule source from `0.0.0.0/0` to the EB security group ID

---

## Part 4: Verify Deployment (5 minutes)

### 10. Test the Application

```bash
# Check status
eb status

# View logs
eb logs

# Open in browser
eb open
```

### 11. Test Features

1. **Register a new user**
2. **Test Solo Mode**:
   - Select genres
   - Swipe on movies
   - Check recommendations work
3. **Test Group Mode**:
   - Create group session
   - Open in incognito/another browser
   - Join the group with code
   - **Test chat** - send messages (should appear in real-time)
   - **Test swiping** - swipe on same movie from both browsers
   - **Test match** - verify match notification appears

### 12. SSH and Verify Backend

```bash
# SSH into instance
eb ssh cinematch-production

# Check Daphne is running
ps aux | grep daphne

# Check database connection
cd /var/app/current
source /var/app/venv/*/bin/activate
python manage.py dbshell
# Type: \dt (should show tables)
# Type: \q (to quit)

# Check Redis connection
redis-cli -h $REDIS_HOST ping
# Should return: PONG

# View logs
tail -f /var/log/web.stdout.log

# Exit SSH
exit
```

---

## Troubleshooting

### Problem: Group chat not working

**Check #1: Is Redis configured?**
```bash
eb printenv | grep REDIS
# Should show REDIS_HOST and REDIS_PORT
```

**Check #2: Can app connect to Redis?**
```bash
eb ssh cinematch-production
redis-cli -h $REDIS_HOST ping
# Should return: PONG
```

**Check #3: Is Daphne running?**
```bash
ps aux | grep daphne
# Should show daphne process on port 8000
```

**Fix: Restart the app**
```bash
exit  # Exit SSH
eb restart
```

### Problem: Database errors

**Check RDS endpoint is correct:**
```bash
eb printenv | grep POSTGRES_HOST
# Should match your RDS endpoint
```

**Check database connection:**
```bash
eb ssh cinematch-production
cd /var/app/current
source /var/app/venv/*/bin/activate
python manage.py dbshell
```

**If can't connect, check security groups:**
1. RDS security group allows EB security group
2. Credentials are correct in environment variables

### Problem: Migrations not applied

**Run manually:**
```bash
eb ssh cinematch-production
cd /var/app/current
source /var/app/venv/*/bin/activate
python manage.py migrate
python manage.py createsu
exit
```

---

## Post-Deployment

### Get your URLs:
```bash
# Application URL
eb status | grep "CNAME"

# Or open directly
eb open
```

### Admin Panel:
```
URL: https://your-app-url.elasticbeanstalk.com/admin
Username: admin
Password: Cinematch303
```

---

## Clean Up (If you want to delete everything)

```bash
# Terminate EB environment
eb terminate cinematch-production

# Then in AWS Console:
# - Delete RDS database (cinematch-db)
# - Delete ElastiCache cluster (cinematch-redis)
# - Delete security groups (cinematch-db-sg, cinematch-redis-sg)
# - Delete key pair (cinematch-keypair)
```

---

## Summary

**What you created:**
- ✅ EC2 key pair for SSH
- ✅ RDS PostgreSQL database (cinematch-db)
- ✅ ElastiCache Redis (cinematch-redis)
- ✅ EB Application (cinematch-app)
- ✅ EB Environment (cinematch-production)
- ✅ Load balancer and security groups

**Endpoints:**
- App: `https://cinematch-production.us-east-1.elasticbeanstalk.com`
- Admin: `https://cinematch-production.us-east-1.elasticbeanstalk.com/admin`

**Credentials:**
- DB User: `cinematch_admin`
- DB Password: `CineMatch2025!Secure`
- Admin User: `admin`
- Admin Password: `Cinematch303`

---

**You're done! 🎉**

Test group chat by:
1. Creating a group
2. Joining from another browser
3. Sending messages - they should appear instantly!
