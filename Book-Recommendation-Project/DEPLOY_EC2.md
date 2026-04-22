# Deploy Book Recommender on Amazon EC2 (Free Tier)

This guide runs the FastAPI app in Docker on a small Ubuntu instance and exposes it on port 80 with Nginx.

## Prerequisites

- AWS account
- Your repo cloned or pushed to GitHub: [Machine-Learning-Projects](https://github.com/Vandanatharigopula/Machine-Learning-Projects)
- Local `data/` CSV paths must match `src/data_processing.py` (`data/books.csv` and `data/ratings.csv`). On Linux, filenames are case-sensitive; rename files if needed.

## 1. Launch EC2

1. AWS Console → **EC2** → **Launch instance**
2. **Name:** book-recommender
3. **AMI:** Ubuntu Server 22.04 LTS (64-bit x86)
4. **Instance type:** `t2.micro` or `t3.micro` (Free Tier eligible)
5. **Key pair:** Create new → download `.pem`
6. **Network settings:** Allow **SSH (22)** from My IP; allow **HTTP (80)** from **Anywhere** (`0.0.0.0/0`)
7. **Storage:** 8–30 GiB gp3 is enough
8. Launch instance

Note the **Public IPv4 address**.

## 2. Connect over SSH

```bash
chmod 400 your-key.pem
ssh -i your-key.pem ubuntu@YOUR_PUBLIC_IP
```

## 3. Install Docker and Nginx

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io nginx git
sudo usermod -aG docker ubuntu
```

Log out and SSH back in so `docker` works without `sudo`, or use `sudo docker` for the commands below.

## 4. Clone and build

```bash
git clone https://github.com/Vandanatharigopula/Machine-Learning-Projects.git
cd Machine-Learning-Projects/Book-Recommendation-Project
```

If your CSVs use different names (e.g. `Books.csv`), fix paths or rename:

```bash
cd data
[ -f Books.csv ] && [ ! -f books.csv ] && ln -s Books.csv books.csv || true
[ -f Ratings.csv ] && [ ! -f ratings.csv ] && ln -s Ratings.csv ratings.csv || true
cd ..
```

Build and run:

```bash
docker build -t book-recommender .
docker rm -f book-api 2>/dev/null
docker run -d --restart unless-stopped --name book-api -p 127.0.0.1:8000:8000 book-recommender
```

Check:

```bash
curl -s http://127.0.0.1:8000/ | head
```

First startup loads CSVs and trains models; wait 30–90 seconds if the request times out once.

## 5. Nginx reverse proxy (port 80)

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
sudo ln -sf /etc/nginx/sites-available/book-recommender /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Open in a browser:

- `http://YOUR_PUBLIC_IP/login`
- `http://YOUR_PUBLIC_IP/docs`

## 6. Optional: HTTPS

Point a domain’s **A record** to the instance IP, then on the server install Certbot and obtain a certificate for your domain (many tutorials: “nginx certbot ubuntu 22.04”).

## 7. Environment variables

You can pass settings into the container:

```bash
docker rm -f book-api
docker run -d --restart unless-stopped --name book-api \
  -e MIN_BOOK_RATINGS=50 \
  -p 127.0.0.1:8000:8000 \
  book-recommender
```

## Troubleshooting

- **502 Bad Gateway:** Container not ready or crashed. Run `docker logs book-api`.
- **Out of memory:** Use a larger instance or reduce `sample_size` in `load_and_process_data` for production builds.
- **Import errors in container:** Build must run from `Book-Recommendation-Project` (this Dockerfile sets `WORKDIR /app` and copies `api`, `src`, `frontend`, `data`).
