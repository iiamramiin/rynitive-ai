# Rynitive AI: CSV Shareability Checker

Upload a CSV, pay once, and get a PDF report by email that tells you whether the
dataset is safe to share: which columns hold personal data, which combinations of
columns could re-identify people, and what to change before sharing.

**Live site:** [rynitive.com](https://rynitive.com) · **Price:** $29 per dataset

## How it works

```
Landing page ──► POST /create-checkout ──► Stripe Checkout ──► payment
 (page/index.html)   saves CSV to temp          │
                                                ├─► GET /scan?session_id=...   (redirect after payment)
                                                └─► POST /webhook              (Stripe checkout.session.completed)
                                                          │
                                         scan (Presidio + heuristics) ──► PDF (ReportLab) ──► email (Resend)
```

1. The user picks a CSV (up to 20 MB) and enters an email on the landing page.
2. The API stores the file temporarily and creates a Stripe Checkout session. The file
   path, filename, and email travel in the session metadata.
3. After payment, the file is scanned, a PDF report is generated, and the report is
   emailed to the user. Temporary files are then deleted.

## What the scan checks

| Check | How |
|---|---|
| Direct identifiers | Microsoft Presidio with spaCy (`en_core_web_lg`): emails, phone numbers, SSNs, credit cards, IP addresses, names, locations, driver's licenses, passports, plus a custom medical-record-number recognizer. Findings below 0.75 confidence are dropped. |
| Column-name hints | Names such as `email`, `phone`, `ssn`, `patient_id` (direct) and `dob`, `zip`, `age`, `gender`, `race` (quasi-identifiers). |
| High-uniqueness columns | Columns where at least 85% of 30+ non-null values are unique. |
| Re-identification risk | Share of rows that are unique on the combination of all quasi-identifier columns. |
| False-positive filters | Product, supplier, and medical codes (ICD-10, CPT), money, dimensions, and common color/material words are skipped. |

Up to 100 values per column are sampled for Presidio, which keeps scans fast on large files.

### Readiness level

| Level | Rule |
|---|---|
| 🔴 RED | Direct-identifier columns with actual PII detected in the values |
| 🟡 YELLOW | 3+ quasi-identifiers, or combination uniqueness above 70%, or 3+ high-uniqueness columns |
| 🟢 GREEN | None of the above |

The report also lists risk factors (for example, small datasets under 100 rows) and
concrete fixes: columns to drop, age ranges instead of exact ages, 3-digit ZIP codes,
date shifting, hashing, or binning.

## Project layout

```
main.py               FastAPI app: checkout, Stripe webhook, post-payment scan, email delivery
scanner_enhanced.py   ShareabilityScanner: PII detection, quasi-identifiers, risk scoring
report_generator.py   PDF report (ReportLab) with logo, summary, per-column findings, recommendations
rynitive_logo.png     Logo used in the PDF
page/index.html       Landing page (static, hosted separately; calls the API)
requirements.txt      Python dependencies, including the spaCy model wheel
Procfile, railway.json   Railway deployment
render.yaml           Render deployment (alternative)
```

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Basic status |
| GET | `/health` | Health check: Stripe and Resend configured, temp dir present |
| POST | `/create-checkout` | Form fields `file` (CSV) and `email`. Returns `checkout_url` and `session_id` |
| POST | `/webhook` | Stripe webhook (`checkout.session.completed`); verifies the signature, then scans and emails |
| GET | `/scan?session_id=...` | Stripe success redirect; confirms payment, then scans and emails |
| POST | `/webhook/email` | Resend inbound-email webhook; forwards support emails to the owner's inbox |
| POST | `/test-scan` | Scan without payment. Only works when `ENVIRONMENT=development` |

## Configuration

Set these as environment variables (or in a local `.env` file, which is git-ignored):

| Variable | Description |
|---|---|
| `STRIPE_SECRET_KEY` | Stripe secret key |
| `STRIPE_PRICE_ID` | Stripe price for one scan |
| `STRIPE_WEBHOOK_SECRET` | Signing secret of the `/webhook` endpoint |
| `RESEND_API_KEY` | Resend API key |
| `RESEND_FROM_EMAIL` | Sender address on a verified Resend domain |
| `BASE_URL` | Public URL of this API |
| `SUCCESS_URL`, `CANCEL_URL` | Checkout redirect pages |
| `MAX_FILE_SIZE_MB` | Upload limit (default 20) |
| `ENVIRONMENT` | `development` enables `/test-scan`; use `production` when deployed |

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# .env with at least: ENVIRONMENT=development
python main.py                     # http://localhost:8000

curl http://localhost:8000/health
curl -F "file=@sample.csv" http://localhost:8000/test-scan
```

Run the scanner on its own with built-in sample data:

```bash
python scanner_enhanced.py
```

## Deploy

**Railway** (current): connect the GitHub repo. `railway.json` and `Procfile` start
`uvicorn main:app`. Add the environment variables above.

**Stripe**: create a webhook endpoint pointing to `https://<api-host>/webhook` for the
event `checkout.session.completed`, and copy its signing secret into `STRIPE_WEBHOOK_SECRET`.

**Resend**: verify the sending domain, set `RESEND_FROM_EMAIL`, and point inbound email
to `https://<api-host>/webhook/email` for support forwarding.

The spaCy `en_core_web_lg` model needs roughly 1 GB of RAM at runtime; size the
instance accordingly.

## Roadmap

- Process each paid order exactly once (webhook as the single trigger, idempotent by session id)
- Move scanning, PDF generation, and email to a background task so requests return immediately
- Expire uploads from abandoned checkouts automatically
- Word-level column-name matching to cut false positives (for example `status`, `image`)
- Per-column PII percentages based on the sampled values
- Unit tests for the scanner and report generator

## Author

**Ramin Rajaei** · [GitHub](https://github.com/iiamramiin)

## License

Proprietary. All rights reserved.
