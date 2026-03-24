# 🧠 AI Meeting Agent Pipeline

An **enterprise-grade multi-agent AI system** that transforms raw meeting transcripts into **structured, actionable, and secure workflow data**.

Built with a modular agent architecture, this system simulates how real organizations process meetings into decisions, tasks, and risk insights.

---

## ✨ Key Features

* 🤖 **5 specialized AI agents** working in sequence
* 📄 Converts unstructured text → structured JSON
* 🔐 Built-in **RBAC (role-based access control)**
* ⚠️ Detects **risks, blockers, and delays**
* 📊 Generates **monitoring insights & escalation actions**
* 🧾 Supports **JSON, Markdown, CSV exports**
* ⚡ Async pipeline (~40% faster execution)
* 🌐 CLI + API + Streamlit UI support

---

## 📌 Output Structure

The pipeline generates:

* **Meeting Summary** → concise overview
* **Decisions** → extracted with context & sensitivity
* **Tasks** → with owner, deadline, priority, dependencies
* **Unassigned Tasks** → flagged with reasons
* **Sensitivity Levels** → PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED
* **RBAC Roles** → access control per task
* **Masked Preview** → safe redacted text
* **Risks & Blockers** → with severity + solutions
* **Monitoring Insights** → reminders, escalations, delay predictions

---

## 🏗️ Architecture

```
Transcript
    │
    ▼
[Comprehension Agent] → Summary
    │
    ▼
[Extraction Agent] → Decisions + Tasks
    │
    ▼
[Classification Agent] → Sensitivity + RBAC
    │
    ▼
[Risk Agent] → Risks & Blockers
    │
    ▼
[Monitoring Agent] → Insights & Alerts
    │
    ▼
[Validator] → Final Structured JSON
```

---

## ⚙️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/meeting-agent-pipeline.git
cd meeting-agent-pipeline
```

### 2. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate     # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
GEMINI_API_KEY=your_api_key_here
```

---

## 🚀 Usage

### CLI

```bash
python -m cli.run examples/q3_product_hr_sync.txt --date 2025-07-14
```

Save output:

```bash
python -m cli.run examples/q3_product_hr_sync.txt --date 2025-07-14 > output.json
```

---

### Python API

```python
from src.pipeline import run_pipeline

transcript = """
Sarah: We need to finalize the client proposal by Friday.
James: I'll handle the backend work. Should be done by July 22nd.
Priya: HR will send the revised salary bands to James by Thursday. Keep those confidential.
"""

result = run_pipeline(transcript, meeting_date="2025-07-14")

print(result["meeting_summary"])
print(result["tasks"])
```

---

### 🌐 Streamlit UI

```bash
streamlit run ui/app.py
```

---

## 🧪 Testing

```bash
pytest tests/ -v
```

✔ Covers:

* Date normalization
* Schema validation
* Export + webhook logic

(No external API calls used in tests)

---

## 📂 Project Structure

```
meeting-agent-pipeline/
├── src/        # Core pipeline + agents  
├── cli/        # Command-line interface  
├── api/        # FastAPI backend  
├── ui/         # Streamlit frontend  
├── tests/      # Unit tests  
├── examples/   # Sample transcripts  
```

---

## 📤 Exporting Results

```python
from src.exporters import export_all

export_all(result, "outputs/", "meeting")
```

Outputs:

* JSON
* Markdown report
* CSV (tasks)

---

## ⚡ Async Pipeline

```python
from src.pipeline_async import run_pipeline_async_sync

result = run_pipeline_async_sync(transcript)
```

👉 ~40% faster via parallel agent execution

---

## 🔔 Webhook Integration

```env
WEBHOOK_ENABLED=true
WEBHOOK_URL=your_url
```

Supports:

* Slack notifications
* Event-based triggers

---

## 🔐 Sensitivity Levels

| Level        | Access     |
| ------------ | ---------- |
| PUBLIC       | Everyone   |
| INTERNAL     | Team       |
| CONFIDENTIAL | Managers   |
| RESTRICTED   | Admin / HR |

---

## 💡 Why this project?

This project demonstrates:

* Multi-agent system design
* LLM orchestration
* Real-world workflow automation
* Secure data handling (RBAC)
* Production-ready architecture (CLI + API + UI)

---

## 🧑‍💻 Author

**Mauli Kukreti**
B.Tech CSE | Aspiring Software Developer

---

## ⭐ Future Improvements

* OpenAI / multi-model fallback
* Real-time meeting ingestion
* Dashboard for analytics
* Deployment (AWS / Docker)
