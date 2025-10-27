# Debugging Steps for AWS EB Deployment

## Current Issues Fixed:
1. ✅ Fixed `$PYTHONHOME` variable expansion (changed to `/var/app/venv/*/bin/activate`)
2. ✅ Added test script to verify database connectivity

## Issues to Debug:
1. Database connection failing during migrations
2. Need to verify RDS security group settings
3. Need to confirm actual database name format

---

## Option 1: Deploy and Check Logs

```bash
# Deploy the updated code
eb deploy

# If it fails, check logs
eb logs --all

# Check specific log files
# Look for: cfn-init-cmd.log for detailed migration errors
```

---

## Option 2: SSH into Instance for Manual Testing

### Step 1: SSH into the EB instance
```bash
eb ssh
```

### Step 2: Check Environment Variables
```bash
# Once inside the instance, check if environment variables are set
echo "POSTGRES_DB: $POSTGRES_DB"
echo "POSTGRES_HOST: $POSTGRES_HOST"
echo "POSTGRES_USER: $POSTGRES_USER"
echo "POSTGRES_PORT: $POSTGRES_PORT"

# If not set in shell, check the EB environment config
sudo cat /opt/elasticbeanstalk/deployment/env

# Or check what's actually loaded in Python
cd /var/app/current
source /var/app/venv/*/bin/activate
python -c "import os; print('POSTGRES_DB:', os.environ.get('POSTGRES_DB', 'NOT SET'))"
```

### Step 3: Test Database Connection
```bash
# Navigate to application directory
cd /var/app/staging

# Activate the virtual environment
source /var/app/venv/*/bin/activate

# Test database connection using our test script
python test_db_connection.py

# Or test directly with psql
PGPASSWORD="Cinematch303" psql -h cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com -U cinematch -d cinematch-db -c "\l"
```

### Step 4: Try Migrations Manually
```bash
cd /var/app/staging
source /var/app/venv/*/bin/activate

# Set environment variables manually if needed
export POSTGRES_DB=cinematch-db
export POSTGRES_USER=cinematch
export POSTGRES_PASSWORD=Cinematch303
export POSTGRES_HOST=cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com
export POSTGRES_PORT=5432

# Try migrations
python manage.py migrate --noinput

# If that works, try collectstatic
python manage.py collectstatic --noinput
```

### Step 5: Check Django Settings
```bash
cd /var/app/staging
source /var/app/venv/*/bin/activate

# Check what Django sees
python manage.py shell
```

Then in the Django shell:
```python
from django.conf import settings
print("Database config:")
print(settings.DATABASES['default'])
```

---

## Option 3: Check AWS RDS Security Group

The database connection might be blocked by the security group.

### Via AWS Console:
1. Go to **RDS Console** → **Databases** → `cinematch-db`
2. Click on the **VPC security groups** link
3. Check **Inbound rules**:
   - Should allow **PostgreSQL (port 5432)** from:
     - EB instance security group, OR
     - VPC CIDR range, OR
     - At minimum: the EB instance's private IP

### To find EB instance security group:
```bash
eb ssh

# Once inside:
curl http://169.254.169.254/latest/meta-data/security-groups
```

---

## Option 4: Simplify Database Configuration

If the hyphen in "cinematch-db" is causing issues, we might need to:

### Check actual database name in RDS:
```bash
# From EB instance:
PGPASSWORD="Cinematch303" psql -h cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com -U cinematch -d postgres -c "\l"
```

This will list all databases. Look for the actual name.

### If database doesn't exist, create it:
```bash
PGPASSWORD="Cinematch303" psql -h cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com -U cinematch -d postgres -c "CREATE DATABASE \"cinematch-db\";"
```

Note: Database names with hyphens must be quoted.

---

## Quick Fix If Security Group Is The Issue

1. Go to **EC2 Console** → **Security Groups**
2. Find the **EB instance security group** (usually named like `awseb-e-...`)
3. Copy its **Group ID** (e.g., `sg-xxxxx`)
4. Go to **RDS security group**
5. Add **Inbound rule**:
   - Type: PostgreSQL
   - Port: 5432
   - Source: [EB Security Group ID]

---

## Next Steps After Debugging

Once you identify the issue:

1. If it's a **security group issue**: Fix in AWS Console, then redeploy
2. If it's a **database name issue**: Update `.ebextensions/03_env_vars.config`
3. If it's a **credentials issue**: Update environment variables
4. Then run: `git add .`, `git commit -m "fix"`, `eb deploy`

---

## Helpful Commands Summary

```bash
# SSH into instance
eb ssh

# Check app logs
tail -f /var/log/web.stdout.log

# Check EB engine logs
sudo tail -f /var/log/eb-engine.log

# Restart the application
sudo systemctl restart web

# Check web service status
sudo systemctl status web
```
