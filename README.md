<div align="center">
  <!-- Insert Logo Here if available -->
  <h1>LeadMend 🚀</h1>

  <p>
    <a href="https://github.com/murad/leadmend/actions"><img src="https://img.shields.io/github/actions/workflow/status/murad/leadmend/ci.yml?style=flat-square&logo=github-actions&logoColor=white" alt="Build Status"></a>
    <a href="https://docs.project.com"><img src="https://img.shields.io/badge/docs-Sphinx-blue?style=flat-square&logo=sphinx&logoColor=white" alt="Docs"></a>
    <a href="https://astro.build"><img src="https://img.shields.io/badge/Framework-Astro-ff5a03?style=flat-square&logo=astro&logoColor=white" alt="Astro"></a>
    <a href="https://tailwindcss.com/"><img src="https://img.shields.io/badge/CSS-Tailwind%20v4-38B2AC?style=flat-square&logo=tailwind-css&logoColor=white" alt="Tailwind"></a>
    <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/API-FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
  </p>

  <p><em>The resilient gateway for high-integrity lead enrichment and intelligent routing.</em></p>
</div>

---

## 🎯 The "Why"

In the world of MarTech, lead data is often the most volatile asset. Traditional ingestion pipelines are brittle, frequently breaking when encountering malformed JSON, missing fields, or unexpected data types from diverse marketing sources.

**LeadMend** was built to solve the "Dirty Data" bottleneck. It implements a **Self-Healing Architecture** that:
1.  **Normalizes** incoming chaos into structured, reliable data.
2.  **Enriches** minimal inputs with deep firmographic insights.
3.  **Prioritizes** business value through algorithmic scoring.
4.  **Routes** leads to the right destination (Slack/CRM) based on real-time intelligence.

By shifting from "rejecting bad data" to "healing and valuing data," LeadMend ensures no high-value opportunity is lost to a technicality.

---

## 🏗️ High-Level Architecture

The system is designed as a modular suite of micro-services and specialized layers:

| Layer | Technology Stack | Responsibility |
| :--- | :--- | :--- |
| **Edge/API** | FastAPI (Python 3.11) | Resilient webhook ingestion & Pydantic validation. |
| **Core Logic** | Pydantic + Custom Services | Normalization, enrichment, deduplication, and scoring. |
| **State** | PostgreSQL (SQLAlchemy Async) | Persistent storage for leads and system state. |
| **Orchestration** | n8n | Complex CRM workflows and external API integrations. |
| **Dashboard** | Astro + React + Tailwind | High-performance, real-time visualization of lead flow. |
| **Development** | Docker Compose | Unified, reproducible environment for the entire stack. |

---

## ⚡ Quick Start

### 1. Prerequisites
Ensure you have **Docker** and **Docker Compose** installed.

### 2. Initialize Environment
```bash
# Clone the repository
git clone https://github.com/murad/leadmend.git
cd leadmend

# Setup environment variables
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

### 3. Launch the Stack
```bash
make dev
```
_This command initializes PostgreSQL, n8n, the Backend API, the Astro Frontend, and the Mock Enrichment service._

### 4. Access Points
- **Dashboard**: [http://localhost:3000](http://localhost:3000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Workflow Automation (n8n)**: [http://localhost:5678](http://localhost:5678)

---

## 📂 Structure

```text
├── .github/          # PR templates and strict CI workflow gates
├── backend/          # FastAPI application, business logic, and test suites
│   ├── app/          # Core source code (API, Services, Models)
│   └── tests/        # Pytest integration and unit tests
├── frontend/         # Astro + React + Tailwind CSS dashboard
├── mock_enrich/      # Simulated enrichment microservice for local testing
├── n8n/              # Pre-configured workflows for lead routing
├── db/               # Database initialization and migration scripts
├── docs/             # Sphinx-generated technical documentation
└── docker-compose.yml # Full-stack orchestration
```

---

## 🧪 Testing

We enforce a strict testing policy to maintain the integrity of the self-healing pipeline.

```bash
# Run the complete test suite
make test
```

---

## 🛡️ License

LeadMend is open-source software licensed under the [MIT License](LICENSE).
