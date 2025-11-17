# PlaudAI Uploader - Deployment Guide for server1-70TR000LUX

## 🚀 Quick Deployment

### Step 1: Connect to Server

```bash
ssh user@server1-70TR000LUX
```

### Step 2: Create Project Directory

```bash
cd /opt  # or your preferred location
sudo mkdir -p plaudai_uploader
sudo chown $USER:$USER plaudai_uploader
cd plaudai_uploader
```

### Step 3: Create Directory Structure

```bash
mkdir -p backend/services
mkdir -p frontend
mkdir -p logs
```

### Step 4: Upload Project Files

Copy all the generated files to the server:

```
plaudai_uploader/
├── backend/
│   ├── __init__.py              (empty file)
│   ├── config.py
│   ├── db.py
│   ├── models.py
│   ├── schemas.py
│   ├── main.py
│   └── services/
│       ├── __init__.py          (empty file)
│       ├── parser.py
│       └── uploader.py
├── frontend/
│   └── index.html
├── requirements.txt
├── .env.example
└── README.md
```

You can use `scp` or `rsync`:

```bash
# From your local machine
scp -r plaudai_uploader/ user@server1-70TR000LUX:/opt/
```

### Step 5: Create Environment File

```bash
cd /opt/plaudai_uploader
cp .env.example .env
nano .env
```

**Update these critical values:**
```
DB_HOST=server1-70TR000LUX  # or localhost if PostgreSQL is local
DB_PASSWORD=your_actual_postgres_password
GOOGLE_API_KEY=your_gemini_key_if_you_have_one
```

### Step 6: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 7: Verify Database Connection

```bash
# Test PostgreSQL connection
psql -h server1-70TR000LUX -U postgres -d surgical_command_center -c "SELECT version();"

# If this fails, check:
# 1. PostgreSQL is running: sudo systemctl status postgresql
# 2. User has access: Check pg_hba.conf
# 3. Database exists: psql -U postgres -l
```

### Step 8: Initialize Database Tables

The application will auto-create tables on first run, but you can verify:

```bash
# Start Python shell
python3
```

```python
from backend.db import init_db, check_connection

# Check connection
if check_connection():
    print("✅ Database connected!")
    init_db()
    print("✅ Tables created!")
else:
    print("❌ Database connection failed!")
```

### Step 9: Start the Backend Server

```bash
cd /opt/plaudai_uploader
source venv/bin/activate

# Development mode (with auto-reload)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Production mode (stable)
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Step 10: Test the API

```bash
# From another terminal
curl http://localhost:8000/

# Should return:
# {
#   "service": "PlaudAI Uploader",
#   "version": "1.0.0",
#   "status": "healthy",
#   ...
# }
```

### Step 11: Access the Frontend

Open your browser and navigate to:
```
file:///opt/plaudai_uploader/frontend/index.html
```

Or serve it with a simple HTTP server:
```bash
cd frontend
python3 -m http.server 8080
```

Then access: `http://server1-70TR000LUX:8080`

---

## 🔧 Production Setup with systemd

### Create systemd Service

```bash
sudo nano /etc/systemd/system/plaudai-uploader.service
```

Paste this configuration:

```ini
[Unit]
Description=PlaudAI Uploader API
After=network.target postgresql.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/opt/plaudai_uploader
Environment="PATH=/opt/plaudai_uploader/venv/bin"
ExecStart=/opt/plaudai_uploader/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Enable and Start Service

```bash
sudo systemctl daemon-reload
sudo systemctl enable plaudai-uploader
sudo systemctl start plaudai-uploader

# Check status
sudo systemctl status plaudai-uploader

# View logs
sudo journalctl -u plaudai-uploader -f
```

---

## 🌐 Nginx Reverse Proxy (Optional)

If you want to serve both frontend and backend through nginx:

```bash
sudo nano /etc/nginx/sites-available/plaudai
```

```nginx
server {
    listen 80;
    server_name server1-70TR000LUX;

    # Frontend
    location / {
        root /opt/plaudai_uploader/frontend;
        index index.html;
        try_files $uri $uri/ =404;
    }

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/plaudai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Update frontend `index.html` to use:
```javascript
const API_BASE = '/api';  // Instead of http://localhost:8000
```

---

## 🔍 Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Check if port is open
sudo ss -tulpn | grep 5432

# Test connection
psql -h localhost -U postgres -d surgical_command_center

# Check pg_hba.conf for authentication
sudo nano /etc/postgresql/*/main/pg_hba.conf
# Ensure this line exists:
# host    all             all             127.0.0.1/32            md5
```

### Port Already in Use

```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>
```

### Import Errors

```bash
# Ensure you're in the right directory and venv is activated
cd /opt/plaudai_uploader
source venv/bin/activate
python -c "import backend.main"
```

### View Application Logs

```bash
tail -f logs/plaudai_uploader.log
```

---

## 🔐 Security Checklist

- [ ] Change default PostgreSQL password
- [ ] Update `.env` with secure credentials
- [ ] Never commit `.env` to version control
- [ ] Set up firewall rules (allow only necessary ports)
- [ ] Enable SSL/TLS for production
- [ ] Implement authentication for API endpoints
- [ ] Regular database backups
- [ ] Monitor logs for suspicious activity

---

## 📊 Verify Installation

After deployment, test these endpoints:

```bash
# Health check
curl http://server1-70TR000LUX:8000/health

# Upload test
curl -X POST http://server1-70TR000LUX:8000/upload \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Test",
    "last_name": "Patient",
    "dob": "1980-01-01",
    "athena_mrn": "TEST001",
    "transcript_text": "Test transcript for femoral artery stenosis"
  }'

# Check stats
curl http://server1-70TR000LUX:8000/stats
```

---

## 📞 Support

For issues:
1. Check logs: `tail -f logs/plaudai_uploader.log`
2. Check service: `sudo systemctl status plaudai-uploader`
3. Check database: `psql -U postgres -d surgical_command_center`

---

## ✅ Next Steps

Once deployed:
1. Test with real PlaudAI transcripts
2. Verify PVI field extraction accuracy
3. Integrate with Surgical Command Center main UI
4. Set up automated backups
5. Configure monitoring and alerts