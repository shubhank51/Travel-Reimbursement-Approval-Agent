# HCLTech GenAI Travel Reimbursement Approval Agent

This project contains a policy-grounded GenAI reimbursement evaluator that can be run as:

- a notebook prototype in `Shubhankar_Raj.ipynb`
- a Python CLI via `main.py`
- a Streamlit web app via `app.py`
- a Docker container for deployment

## What it does

The agent implements:

- policy retrieval
- receipt validation
- per-diem and category limit checks
- approval thresholds
- manual review routing
- Pydantic structured outputs
- decision audit trail and dashboard

## Quick start

```bash
pip install -r requirements.txt
```

### Run the notebook
Open `Shubhankar_Raj.ipynb` and run all cells.

### Run the CLI demo
```bash
python main.py
```

### Run the Streamlit app
```bash
streamlit run app.py
```

### Optional LLM mode
Set these environment variables if you want to use the OpenAI planner:

```bash
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-4o-mini
```

Without a key, the deterministic fallback logic runs end-to-end.

## Docker deployment

Build the image:

```bash
docker build -t travel-reimbursement-agent .
```

Run it:

```bash
docker run -p 8501:8501 --env-file .env.example travel-reimbursement-agent
```

Then open:

```text
http://localhost:8501
```

## Deployment ideas

- local development: Streamlit app
- API service: FastAPI wrapper around the same evaluator
- cloud deployment: Azure App Service or Azure Container Apps
- enterprise extension: add Azure OpenAI, document upload, OCR, and RBAC

## Verification

The core decision logic is covered by tests in `tests/test_travel_agent.py`.

```bash
pytest -q
```
