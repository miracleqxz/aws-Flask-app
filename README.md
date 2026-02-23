# Guidy - Personal AI Movie Assistant

Guidy is an AI-powered movie recommendation platform deployed on AWS using Terraform. It features a modern web interface, a fast search engine, and an intelligent chat assistant that helps users find the perfect movie based on their mood or preferences.

I developed this project to explore the practical integration of LLMs into web applications and to practice creating, configuring, and maintaining a microservice architecture.

## Key Features

- **AI Agent & Semantic Search Engine**: Designed a conversational interface (powered by Google Gemini) paired with a high-performance Meilisearch backend. The system prevents LLM hallucinations through an autonomous "Function Calling" pipeline:
  1. The user sends a query (e.g., "I want a funny movie with Jim Carrey").
  2. The LLM translates this semantic request and predicts structured JSON search filters (e.g., `{"query": "comedy jim carrey"}`).
  3. The Python backend intercepts this call to query the typo-tolerant Meilisearch catalog and fetch third-party media (YouTube trailers).
  4. The LLM consumes the exact database records to formulate its human-friendly response, ensuring the reliability of recommendations.
- **Modern UI**: Developed a responsive, glassmorphism-inspired user interface with custom CSS animations and a split-screen chat view.

## Architecture & Infrastructure

The application is fully containerized and runs on AWS, utilizing a microservices-inspired architecture:

- **Compute**: Amazon ECS (Elastic Container Service) running on EC2 instances to orchestrate multiple Docker containers.
- **Routing**: Nginx acts as a reverse proxy, cleanly routing traffic between the Flask frontend and the isolated AI Agent service.
- **Data Layer**: 
  - **RDS PostgreSQL** for persistent movie data and user analytics.
  - **Redis** for chat session state and atomic API rate-limiting.
  - **Meilisearch** as a dedicated full-text search engine.
  - **Amazon S3** for secure storage and delivery of movie poster images.
- **Observability & Monitoring**: Integrated **VictoriaMetrics** for efficient time-series data storage and **Grafana** for real-time visualization of application metrics and traffic.
- **Asynchronous Processing**: AWS SQS and Lambda functions handle async search analytics and S3-to-Database synchronization pipelines.
- **Cost Optimization**: EventBridge cron rules trigger custom AWS Lambda functions to autonomously schedule the stopping and starting of instances overnight, drastically reducing AWS costs.
- **Infrastructure as Code (IaC)**: The entire AWS environment (VPC, ECS, RDS, IAM, etc.) is declaratively provisioned and managed via Terraform.
- **CI/CD**: GitHub Actions automates security scanning, Docker image builds (pushed to GHCR), and zero-downtime deployments to ECS.

## Tech Stack

- **Backend**: Python 3.12, Flask, Gunicorn
- **AI Integration**: Google Gemini API (Tool Calling / Function Calling)
- **Databases**: PostgreSQL (AWS RDS), Redis, Meilisearch
- **Frontend**: HTML5, CSS3, Vanilla JavaScript, Jinja2
- **Infrastructure**: AWS, Terraform, Docker, GitHub Actions, Nginx

## How to Deploy

Prerequisites: AWS CLI configured, Terraform installed, and Docker.

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars  # Edit with your credentials/keys
terraform init
terraform plan
terraform apply
```

Required environment variables in `.tfvars` include `gemini_api_key`, PostgreSQL credentials, and Meilisearch master keys. After applying, Terraform will output the public IP of the frontend Nginx load balancer to access the app.

## License

This is a personal learning project. Feel free to explore, fork, or use it for your own educational purposes.
