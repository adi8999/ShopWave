#!/bin/bash
# EC2 Setup Script for ShopWave Backend

set -e

echo "🚀 Starting ShopWave EC2 Setup..."

# 1. Update system packages
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx git curl libpq-dev

# 2. Setup project directory
mkdir -p ~/shopwave
cd ~/shopwave/backend

# 3. Create virtual environment & install dependencies
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn uvicorn

echo "✅ Python virtual environment and dependencies installed."

# 4. Create systemd service file
cat <<EOF | sudo tee /etc/systemd/system/shopwave.service
[Unit]
Description=ShopWave FastAPI Backend Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/shopwave/backend
Environment="PATH=/home/ubuntu/shopwave/backend/venv/bin"
EnvironmentFile=/home/ubuntu/shopwave/backend/.env
ExecStart=/home/ubuntu/shopwave/backend/venv/bin/gunicorn main:app -w 2 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 5. Configure Nginx Reverse Proxy
cat <<EOF | sudo tee /etc/nginx/sites-available/shopwave
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

# Enable site & restart Nginx
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/shopwave /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Reload systemd and start ShopWave
sudo systemctl daemon-reload
sudo systemctl enable shopwave
sudo systemctl restart shopwave

echo "🎉 ShopWave backend setup complete and running behind Nginx on port 80!"
