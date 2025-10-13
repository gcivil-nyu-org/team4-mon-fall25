# CineMatch AWS EC2 Deployment Guide

## Prerequisites
- EC2 Instance: i-07e4c40c63b3e2cb2 (cinematch-prod)
- RDS PostgreSQL: cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com
- Database: cinematch-db
- User: cinematch
- Password: Cinematch303

## Step 1: Connect to EC2 Instance

```bash
ssh -i /path/to/your-key.pem ubuntu@<EC2-PUBLIC-IP>
```

## Step 2: Install Dependencies on EC2

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11 and pip
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install PostgreSQL client
sudo apt install postgresql-client -y

# Install nginx (web server)
sudo apt install nginx -y

# Install supervisor (process manager)
sudo apt install supervisor -y
```

## Step 3: Clone Repository on EC2

```bash
# Create application directory
sudo mkdir -p /var/www/cinematch
sudo chown $USER:$USER /var/www/cinematch
cd /var/www/cinematch

# Clone the repository
git clone https://github.com/gcivil-nyu-org/team4-mon-fall25.git .
git checkout tester
```

## Step 4: Set Up Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 5: Configure Environment Variables

```bash
# Create .env file
nano .env
```

Paste the following content:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=<EC2-PUBLIC-IP>,<EC2-PUBLIC-DNS>,localhost,127.0.0.1

# AWS RDS PostgreSQL Database
POSTGRES_DB=your-database-name
POSTGRES_USER=your-database-user
POSTGRES_PASSWORD=your-database-password
POSTGRES_HOST=your-rds-endpoint.region.rds.amazonaws.com
POSTGRES_PORT=5432

# API Keys (Get from your team's secure storage)
GROQ_API_KEY=your-groq-api-key
TMDB_TOKEN=your-tmdb-token
TMDB_API_KEY=your-tmdb-api-key

# Movies Path
MOVIES_PATH=movies.txt
```

**Note:** Get the actual values for SECRET_KEY, database credentials, and API keys from your team's secure storage or AWS Secrets Manager.

## Step 6: Run Database Migrations

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run migrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic --noinput
```

## Step 7: Configure Gunicorn

Create Gunicorn systemd service file:

```bash
sudo nano /etc/systemd/system/cinematch.service
```

Paste the following:

```ini
[Unit]
Description=Gunicorn daemon for CineMatch
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/cinematch
Environment="PATH=/var/www/cinematch/venv/bin"
EnvironmentFile=/var/www/cinematch/.env
ExecStart=/var/www/cinematch/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/var/www/cinematch/cinematch.sock \
    --timeout 120 \
    --access-logfile /var/log/cinematch/access.log \
    --error-logfile /var/log/cinematch/error.log \
    recommendation_sys.wsgi:application

[Install]
WantedBy=multi-user.target
```

Create log directory:

```bash
sudo mkdir -p /var/log/cinematch
sudo chown ubuntu:www-data /var/log/cinematch
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable cinematch
sudo systemctl start cinematch
sudo systemctl status cinematch
```

## Step 8: Configure Nginx

Create Nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/cinematch
```

Paste the following:

```nginx
server {
    listen 80;
    server_name <EC2-PUBLIC-IP> <EC2-PUBLIC-DNS>;

    client_max_body_size 20M;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /var/www/cinematch/staticfiles/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/cinematch/cinematch.sock;
        proxy_read_timeout 120s;
        proxy_connect_timeout 120s;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/cinematch /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Step 9: Configure Security Group

Make sure your EC2 security group allows:
- Inbound HTTP (port 80) from 0.0.0.0/0
- Inbound HTTPS (port 443) from 0.0.0.0/0 (if using SSL)
- Inbound SSH (port 22) from your IP

## Step 10: Test Deployment

Visit your EC2 public IP or DNS in a browser:
```
http://<EC2-PUBLIC-IP>
```

## Useful Commands

### View Gunicorn logs
```bash
sudo journalctl -u cinematch -f
tail -f /var/log/cinematch/error.log
```

### Restart services
```bash
sudo systemctl restart cinematch
sudo systemctl restart nginx
```

### Update deployment
```bash
cd /var/www/cinematch
git pull origin tester
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart cinematch
```

### Database operations
```bash
# Connect to RDS database
PGPASSWORD="Cinematch303" psql -h cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com -U cinematch -d cinematch-db

# Run migrations
python manage.py migrate

# Create database backup
pg_dump -h cinematch-db.cwdagky2eta9.us-east-1.rds.amazonaws.com -U cinematch -d cinematch-db > backup.sql
```

## Troubleshooting

### Check if Gunicorn is running
```bash
sudo systemctl status cinematch
ps aux | grep gunicorn
```

### Check Nginx status
```bash
sudo systemctl status nginx
sudo nginx -t
```

### Check database connectivity
```bash
source venv/bin/activate
python manage.py check --database default
```

### Permission issues
```bash
sudo chown -R ubuntu:www-data /var/www/cinematch
sudo chmod -R 755 /var/www/cinematch
```
