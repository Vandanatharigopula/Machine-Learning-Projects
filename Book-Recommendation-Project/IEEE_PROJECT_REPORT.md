# IEEE-Style Project Report

**Title:** Hybrid Book Recommendation System as a FastAPI Web Service with Dockerized AWS Deployment  
**Authors:** _[Your Name]_  
**Affiliation:** _[Your Institution / Organization]_  
**Email:** _[your-email@example.com]_

---

## Abstract

This project presents an end-to-end hybrid book recommendation system implemented as a production-oriented web service. The approach combines user-user collaborative filtering using cosine similarity with a lightweight engagement prediction model based on logistic regression. To improve recommendation signal quality, a preprocessing pipeline filters low-information records and applies a minimum rating-count threshold per book. The system is exposed through FastAPI endpoints for health, personalized recommendations, trending books, and user authentication workflows. Deployment is performed on an Amazon EC2 Linux instance using Docker and Nginx reverse proxy, with operational tuning for low-memory environments. Experimental behavior from runtime logs indicates that startup model construction is sensitive to instance memory constraints, which was mitigated through swap configuration. The resulting service provides accessible REST endpoints, scalable deployment primitives, and a practical baseline for further optimization in recommendation quality and model serving efficiency.

**Keywords:** recommender systems, collaborative filtering, FastAPI, Docker, AWS EC2, logistic regression

---

## I. Introduction

Book recommendation is a classical information filtering problem where systems must identify relevant items for users from sparse interaction histories. Traditional collaborative filtering performs well for personalized ranking but can suffer in sparse regions and cold-start contexts. To address this, the present work integrates collaborative filtering with a supervised engagement signal, creating a hybrid recommendation approach that balances neighborhood similarity with predicted user preference.

The objective of this project is to develop an API-first recommendation platform that can be:

1. Trained from CSV-based historical ratings data.
2. Served through web endpoints for direct integration with front-end clients.
3. Containerized and deployed on cloud infrastructure with reproducible steps.

---

## II. Problem Statement and Objectives

### A. Problem Statement

Given user-book-rating interactions and book metadata, design and deploy a recommendation service that returns relevant books for a target user while remaining operationally practical in a constrained cloud environment.

### B. Objectives

- Build robust preprocessing for real-world CSV schema variations.
- Generate user similarity and recommendation candidates from interaction data.
- Introduce an engagement prediction model to improve ranking confidence.
- Expose recommendations via a RESTful API with error handling and logging.
- Deploy the service on AWS EC2 using Docker and Nginx.
- Validate external accessibility through public HTTP endpoints.

---

## III. System Architecture

The implemented pipeline is organized into modular components:

1. **Data Processing Module (`src/data_processing.py`)**
   - Reads `books.csv` / `ratings.csv` with case-insensitive fallback names.
   - Renames source columns to standardized schema (`user_id`, `book_id`, `rating`, `title`, `author`).
   - Removes zero ratings and null records.
   - Applies minimum book rating frequency (`MIN_BOOK_RATINGS`).
   - Samples data for controlled startup cost.

2. **Model Module (`src/model.py`)**
   - Constructs user-book pivot matrix.
   - Computes full user-user cosine similarity matrix.
   - Trains logistic regression engagement classifier using engineered aggregate features:
     - user mean rating
     - book mean rating
     - book rating count

3. **Recommendation Module (`src/recommend.py`)**
   - Generates collaborative scores from neighborhood-weighted ratings.
   - Applies fallback scoring when collaborative signals are absent.
   - Blends normalized collaborative score with engagement probability.

4. **API Layer (`api/main.py`)**
   - Startup initialization and in-memory model state.
   - Endpoints:
     - `GET /` health
     - `GET /recommend/{user_id}`
     - `GET /trending`
     - authentication and UI routes (`/login`, `/signup`, `/app`)
   - Middleware for request timing and centralized exception logging.

5. **Deployment Layer**
   - Docker containerized application runtime.
   - Nginx reverse proxy exposing port 80.
   - AWS EC2 infrastructure and security-group network controls.

---

## IV. Methodology

### A. Data Preparation

The merged ratings-book dataset is cleaned to remove non-informative entries and improve recommendation stability. Filtering books below a minimum number of ratings reduces high-variance items and improves neighborhood consistency.

### B. Collaborative Filtering

Let \(R\) be the user-item matrix with missing values imputed to zero. User similarity is computed as:

\[
\text{sim}(u_i, u_j) = \frac{u_i \cdot u_j}{\|u_i\|\|u_j\|}
\]

Predicted collaborative score for unseen item \(b\) is derived from weighted neighbor ratings.

### C. Engagement Prediction

A binary target is constructed from rating thresholding (median fallback to global mean if needed), and logistic regression estimates \(P(\text{like} | \text{features})\). This captures interaction-level confidence beyond pure neighborhood correlation.

### D. Hybrid Ranking

Final ranking blends:

- normalized collaborative score (70%)
- engagement probability (30%)

Candidates below a minimum like-probability threshold are filtered where possible, with graceful fallback behavior.

---

## V. Implementation Details

### A. Technology Stack

- **Language:** Python 3.11
- **Data/ML:** pandas, scikit-learn
- **API Framework:** FastAPI, Uvicorn
- **Containerization:** Docker
- **Reverse Proxy:** Nginx
- **Cloud:** AWS EC2 (Ubuntu)

### B. Key Configuration

- `MIN_BOOK_RATINGS` environment variable controls preprocessing strictness.
- API initializes model artifacts at startup and stores them in application state.
- Request/response latency and exceptions are logged for observability.

### C. Frontend Integration

Static frontend pages are served by FastAPI routes and can consume recommendation APIs directly.

---

## VI. Deployment Procedure (End-to-End)

### A. Local Preparation

1. Ensure source project has `Dockerfile` and dependencies.
2. Build image:

```bash
docker build -t book-recommender .
```

### B. EC2 Provisioning

1. Launch Ubuntu EC2 instance.
2. Configure security-group inbound rules:
   - SSH 22 (trusted source)
   - HTTP 80 (`0.0.0.0/0`)
3. Connect via SSH with `.pem` key.

### C. Server Setup

```bash
sudo apt update && sudo apt install -y docker.io nginx git
sudo usermod -aG docker ubuntu
newgrp docker
```

### D. Application Deployment

```bash
git clone https://github.com/Vandanatharigopula/Machine-Learning-Projects.git
cd Machine-Learning-Projects/Book-Recommendation-Project
docker build -t book-recommender .
docker run -d --restart unless-stopped --name book-api -p 127.0.0.1:8000:8000 book-recommender
```

### E. Nginx Reverse Proxy

Nginx forwards external HTTP requests on port 80 to containerized FastAPI on localhost:8000.

### F. Low-Memory Mitigation

On `t3.micro`, model startup may fail due to memory pressure from dense similarity matrix allocation. Adding swap space (2 GB) stabilized startup and allowed successful model initialization.

---

## VII. Results and Observations

### A. Functional Validation

- `GET /` returned API health message.
- `GET /docs` successfully served Swagger UI.
- Nginx proxy successfully forwarded requests from public IPv4 to API.

### B. Operational Findings

- Initial startup failed with `numpy._ArrayMemoryError` while constructing a large similarity matrix.
- After swap allocation and container restart, startup completed successfully.
- Public browser access required HTTP 80 inbound security-group rule.

### C. Current Service Access

The application is externally reachable via EC2 public IP for root, login, and API docs endpoints.

---

## VIII. Limitations

- Full user-user similarity matrix scales poorly with user count (quadratic memory growth).
- Startup-time model training increases cold-start latency.
- No persistent precomputed model artifacts yet.
- Evaluation metrics (e.g., Precision@K, Recall@K) are not yet reported.

---

## IX. Future Work

- Replace full similarity with sparse/approximate nearest-neighbor methods.
- Persist model artifacts and processed matrices for fast startup.
- Add offline evaluation and online A/B experimentation framework.
- Introduce caching and pagination for high-traffic scenarios.
- Add CI/CD pipeline for automated test-build-deploy lifecycle.
- Configure domain, TLS (Certbot), and monitoring dashboards.

---

## X. Conclusion

This work demonstrates a practical, deployable hybrid recommendation pipeline combining collaborative filtering and engagement prediction within a modern API architecture. Beyond algorithmic functionality, the project captures critical production concerns including containerization, reverse proxy configuration, cloud networking, and memory-aware operations. The final system achieved successful cloud deployment and external access, establishing a strong baseline for scaling and model-quality improvements.

---

## References

[1] F. Ricci, L. Rokach, and B. Shapira, *Recommender Systems Handbook*, 2nd ed. Springer, 2015.  
[2] Y. Koren, R. Bell, and C. Volinsky, “Matrix factorization techniques for recommender systems,” *Computer*, vol. 42, no. 8, pp. 30-37, 2009.  
[3] Scikit-learn Developers, “scikit-learn: Machine Learning in Python,” [Online]. Available: https://scikit-learn.org/  
[4] FastAPI Documentation, [Online]. Available: https://fastapi.tiangolo.com/  
[5] Docker Documentation, [Online]. Available: https://docs.docker.com/  
[6] Amazon Web Services, “Amazon EC2 Documentation,” [Online]. Available: https://docs.aws.amazon.com/ec2/

---

## Appendix A: Re-Deployment Commands

```bash
cd ~/Machine-Learning-Projects/Book-Recommendation-Project
git pull
docker build -t book-recommender .
docker rm -f book-api
docker run -d --restart unless-stopped --name book-api -p 127.0.0.1:8000:8000 book-recommender
sudo systemctl reload nginx
```

