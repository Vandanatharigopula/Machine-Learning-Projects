# Book Recommender Deployment Runbook (EC2 + Docker)

This is the brief step-by-step process we followed to run the project on AWS EC2.

## 1) Launch EC2

- AMI: Ubuntu 22.04/24.04
- Instance: `t3.micro` (or bigger if needed)
- Key pair: create/download `.pem`
- Security Group inbound:
  - `SSH` port `22` from your IP
  - `HTTP` port `80` from `0.0.0.0/0`

## 2) SSH into EC2 from Windows

```powershell
ssh -i "C:\Users\tsaiv\Downloads\book-recommender-key.pem" ubuntu@YOUR_PUBLIC_IP
```

If key permission error appears on Windows:

```powershell
icacls "C:\Users\tsaiv\Downloads\book-recommender-key.pem" /inheritance:r
icacls "C:\Users\tsaiv\Downloads\book-recommender-key.pem" /grant:r "$($env:USERNAME):(R)"
```

## 3) Install Docker + Nginx on EC2

Run the rest in EC2 shell (`ubuntu@...$`):

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io nginx git
sudo usermod -aG docker ubuntu
newgrp docker
```

## 4) Clone project and run container

```bash
git clone https://github.com/Vandanatharigopula/Machine-Learning-Projects.git
cd Machine-Learning-Projects/Book-Recommendation-Project

docker build -t book-recommender .
docker rm -f book-api 2>/dev/null
docker run -d --restart unless-stopped --name book-api -p 127.0.0.1:8000:8000 book-recommender
```

## 5) Configure Nginx reverse proxy (port 80 -> 8000)

```bash
sudo tee /etc/nginx/sites-available/book-recommender <<'EOF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/book-recommender /etc/nginx/sites-enabled/book-recommender
sudo nginx -t && sudo systemctl reload nginx
```

## 6) Handle low-memory issue on `t3.micro` (important)

If logs show memory error during startup, add swap:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

Restart app:

```bash
docker restart book-api
```

## 7) Verification commands

```bash
docker ps
docker logs --tail 100 book-api
curl -I http://127.0.0.1:8000/docs
curl http://127.0.0.1:8000/
curl -I http://127.0.0.1
```

Public URLs:

- `http://YOUR_PUBLIC_IP/`
- `http://YOUR_PUBLIC_IP/docs`
- `http://YOUR_PUBLIC_IP/login`

## 8) Future code updates (redeploy)

```bash
cd ~/Machine-Learning-Projects/Book-Recommendation-Project
git pull
docker build -t book-recommender .
docker rm -f book-api
docker run -d --restart unless-stopped --name book-api -p 127.0.0.1:8000:8000 book-recommender
```

## 9) Windows vs Linux command note

- In **PowerShell** use: `2>$null`
- In **Linux/bash** use: `2>/dev/null`

Use Linux commands only after SSH into EC2.
