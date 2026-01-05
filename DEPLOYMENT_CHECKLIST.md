# Week 3 - Deployment Checklist

## ✅ Files Created for Railway Deployment

### Configuration Files
- [x] `requirements.txt` - Updated with Railway-compatible dependencies
- [x] `Procfile` - Railway startup command
- [x] `railway.json` - Railway build configuration
- [x] `.env.example` - Environment variables template
- [x] `.gitignore` - Ignore sensitive files

### Updated Code Files
- [x] `main.py` - Updated with temp directory and PORT config
- [x] `report_generator_simple_ramin.py` - Updated with temp directory

---

## 📋 Pre-Deployment Verification

### 1. Copy Files to Your Project
Copy these files from the downloads to your project directory:

```
your-project/
├── main.py                              (REPLACE)
├── report_generator_simple_ramin.py     (REPLACE)
├── scanner_enhanced.py                  (KEEP - don't change)
├── requirements.txt                     (REPLACE)
├── Procfile                             (NEW)
├── railway.json                         (NEW)
├── .env.example                         (NEW)
├── .gitignore                           (NEW/UPDATE)
└── .env                                 (KEEP - your local env file)
```

### 2. Test Locally First (IMPORTANT!)

Before deploying, test that everything still works:

```bash
# Activate your venv (if using one)
# Install updated requirements
pip install -r requirements.txt

# Run locally
python main.py
```

**Test the health endpoint:**
```bash
# In another terminal
curl http://localhost:8000/health
```

You should see:
```json
{
  "status": "healthy",
  "temp_dir": "/path/to/temp/rynitive_uploads",
  "temp_dir_exists": true
}
```

### 3. Key Changes Made

**main.py:**
- Line 19: Added `import tempfile`
- Line 66: Changed TEMP_DIR to use system temp
  ```python
  TEMP_DIR = Path(tempfile.gettempdir()) / "rynitive_uploads"
  ```
- Line 93: Added temp_dir to health check
- Line 365: Changed port to use environment variable
  ```python
  PORT = int(os.getenv("PORT", 8000))
  ```

**report_generator_simple_ramin.py:**
- Line 14: Added `import tempfile`
- Line 24-27: Changed REPORT_DIR to use system temp
  ```python
  REPORT_DIR = Path(tempfile.gettempdir()) / "rynitive_reports"
  ```

---

## 🚀 Next Steps

Once you've verified locally:

1. **Commit to Git** (if using GitHub)
   ```bash
   git add .
   git commit -m "Week 3: Railway deployment configuration"
   git push
   ```

2. **Ready for Step 2: Railway Account Setup**
   - Sign up at railway.app
   - Connect GitHub account
   - Deploy project

---

## 📝 Environment Variables You'll Need

When you deploy to Railway, you'll need these environment variables:

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=noreply@yourdomain.com
BASE_URL=https://your-app.railway.app
SUCCESS_URL=https://yourdomain.com/success
CANCEL_URL=https://yourdomain.com/
MAX_FILE_SIZE_MB=20
ENVIRONMENT=production
```

**Note:** Don't worry about the Stripe variables yet since you haven't set up Stripe.
For initial deployment, you can skip them or use placeholder values.

---

## ⚠️ Important Notes

1. **Railway Storage:** Railway uses ephemeral storage - files uploaded/generated are temporary
   - This is perfect for your use case (scan → email → delete)
   - No persistent storage costs

2. **Testing Endpoint:** The `/test-scan` endpoint is disabled in production
   - Only works when `ENVIRONMENT=development`
   - Remove completely before launch if you prefer

3. **File Size Limit:** Currently 20MB (configurable via MAX_FILE_SIZE_MB)

4. **Keep scanner_enhanced.py unchanged** - it's already production-ready

---

## 🎯 Success Criteria

Before moving to Step 2, verify:
- [ ] All files copied to your project
- [ ] Local test successful (app runs on port 8000)
- [ ] Health endpoint returns status "healthy"
- [ ] No import errors
- [ ] Ready to commit to Git (if using)

**Time estimate:** 15-20 minutes for verification

---

## Next: Step 2 - Railway Setup & Deployment

Reply with "Step 1 verified" when you've tested locally and are ready to set up Railway!
