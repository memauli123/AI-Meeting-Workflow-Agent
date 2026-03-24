# Meeting Agent Pipeline

An enterprise-grade multi-agent AI system that converts raw meeting transcripts into structured, secure, and actionable workflow JSON.

## What it does

Runs 5 specialized agents in sequence on any meeting transcript and returns:

| Output field | Description |
|---|---|
| `meeting_summary` | 3–4 line concise summary |
| `decisions[]` | Every decision with context and sensitivity |
| `tasks[]` | Actionable tasks with owner, deadline, priority, dependencies |
| `sensitivity` | PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED per item |
| `allowed_roles[]` | RBAC access control per task |
| `masked_preview` | Redacted version safe for unauthorized viewers |
| `unassigned_tasks[]` | Items with no owner and reason |
| `risks_or_blockers[]` | Detected risks with severity and suggested solutions |
| `monitoring_insights` | Delay predictions, overdue flags, REMINDER/ESCALATION/REASSIGN actions |

## Agent architecture

```
Transcript
    │
    ▼
[Agent 1] Comprehension   →  meeting_summary
    │
    ▼
[Agent 2] Extraction      →  decisions[], tasks[], unassigned_tasks[]
    │
    ▼
[Agent 3] Classification  →  sensitivity, allowed_roles[], masked_preview
    │
    ▼
[Agent 4] Risk Detection  →  risks_or_blockers[]
    │
    ▼
[Agent 5] Monitoring      →  monitoring_insights{}
    │
    ▼
[Validator] Schema check  →  validated JSON output
```

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/meeting-agent-pipeline.git
cd meeting-agent-pipeline
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set your API key
```bash
cp .env.example .env
# Edit .env and add your Anthropic API key
```

The pipeline uses the `ANTHROPIC_API_KEY` environment variable. You can also export it directly:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

### From the command line
```bash
# Run on a transcript file
python -m src.pipeline examples/q3_product_hr_sync.txt

# With a meeting date (resolves relative deadlines like "Friday" → "2025-07-18")
python -m src.pipeline examples/q3_product_hr_sync.txt 2025-07-14

# Save output to a file
python -m src.pipeline examples/q3_product_hr_sync.txt 2025-07-14 > output.json
```

### From Python
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

## Running tests
```bash
pytest tests/ -v
```

Tests cover:
- Date normalization (relative → absolute ISO dates)
- Schema validation (all required fields, valid enum values)

No API calls are made during tests — all test cases use local logic only.

## Project structure

```
meeting-agent-pipeline/
├── src/
│   ├── pipeline.py              # Sequential orchestrator (5 agents)
│   ├── pipeline_async.py        # Async orchestrator (~40% faster)
│   ├── batch.py                 # Batch-process folders of transcripts
│   ├── config.py                # Central config (env vars + .env)
│   ├── exporters.py             # Export to JSON / Markdown / CSV
│   ├── webhook.py               # Webhook notifier + Slack formatter
│   ├── agents/
│   │   ├── comprehension_agent.py
│   │   ├── extraction_agent.py
│   │   ├── classification_agent.py
│   │   ├── risk_agent.py
│   │   └── monitoring_agent.py
│   └── utils/
│       ├── date_normalizer.py
│       └── schema_validator.py
├── api/
│   └── server.py                # FastAPI REST server
├── cli/
│   └── run.py                   # Rich terminal CLI
├── ui/
│   └── app.py                   # Streamlit web UI
├── examples/
│   ├── q3_product_hr_sync.txt
│   └── client_proposal_short.txt
├── tests/
│   ├── test_pipeline.py
│   ├── test_extended.py
│   └── test_exporters_and_webhook.py
├── .github/workflows/ci.yml     # GitHub Actions CI
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── CONTRIBUTING.md
└── README.md
```

## Export formats

```bash
# Export to Markdown report
python -m src.pipeline examples/q3_product_hr_sync.txt > /dev/null  # or use API

# From Python
from src.exporters import export, export_all

export(result, "markdown", "outputs/report.md")
export(result, "csv",      "outputs/tasks.csv")
export_all(result, "outputs/", "my_meeting")  # writes .json, .md, .csv
```

## Batch processing

```bash
# Process a whole folder of transcripts
python -m src.batch --input transcripts/ --output outputs/batch/ --date 2025-07-14

# With parallel workers and all export formats
python -m src.batch --input transcripts/ --workers 6 --format all
```

## Async pipeline (faster)

```python
from src.pipeline_async import run_pipeline_async_sync

result = run_pipeline_async_sync(transcript, meeting_date="2025-07-14")
```

Agents 1 and 2 run concurrently, then agents 3 and 4 run concurrently — typically ~40% faster than sequential.

## Webhooks

```bash
# Enable in .env
WEBHOOK_ENABLED=true
WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
WEBHOOK_ON_EVENTS=pipeline_complete,high_risk_detected,restricted_detected
```

```python
from src.webhook import notify_from_env, to_slack_blocks

# Auto-fire based on .env config
notify_from_env(result)

# Or format as Slack Block Kit and POST manually
blocks = to_slack_blocks(result)
```

## Sensitivity & RBAC

| Level | Examples | Allowed roles |
|---|---|---|
| `PUBLIC` | General announcements | ALL |
| `INTERNAL` | Sprint plans, onboarding | TEAM, MANAGER |
| `CONFIDENTIAL` | Client deals, budgets, vendor contracts | MANAGER, ADMIN |
| `RESTRICTED` | Salary, compensation, HR/legal | ADMIN, HR |

Every task also carries a `masked_preview` — a redacted version of the title that is safe to show to users who lack access.

## Notes

- All agents call `claude-sonnet-4-20250514` by default. You can change the `model` parameter in any agent's `__init__`.
- The pipeline makes 6 sequential API calls per transcript (one per agent + 2 classification passes).
- Date normalization requires passing `meeting_date` as `YYYY-MM-DD`. Without it, relative deadlines like "Friday" are preserved as-is.
