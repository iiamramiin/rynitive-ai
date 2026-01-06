# Render.com Deployment Guide for Rynitive AI

## ✅ Files Added for Render

1. **render.yaml** - Render configuration (replaces railway.json)
2. **build.sh** - Build script for dependencies and spaCy model
3. This guide

## 🚀 Deployment Steps

### Step 1: Add Files to GitHub

```bash
# Add the new Render files
git add render.yaml build.sh

# Commit
git commit -m "Add Render.com deployment configuration"

# Push to GitHub
git push origin main
```

### Step 2: Create Web Service on Render

1. Go to: https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Click **"Connect a repository"**
4. Find and select: **rynitive-ai**

### Step 3: Configure the Service

Render should auto-detect settings from `render.yaml`, but verify:

- **Name:** `rynitive-ai` (or your choice)
- **Runtime:** Python 3
- **Build Command:** `./build.sh` or use render.yaml's buildCommand
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Plan:** Free

### Step 4: Add Environment Variables

Click **"Advanced"** → **"Environment Variables"** and add:

```
RESEND_API_KEY=re_65KZhC9q_BixnJkBaWeeumWfWyLLkX11k
RESEND_FROM_EMAIL=onboarding@resend.dev
ENVIRONMENT=production
MAX_FILE_SIZE_MB=20
```

**Stripe placeholders (add these for now, we'll set up Stripe later):**
```
STRIPE_SECRET_KEY=sk_test_placeholder
STRIPE_PRICE_ID=price_placeholder
STRIPE_WEBHOOK_SECRET=whsec_placeholder
```

### Step 5: Deploy

1. Click **"Create Web Service"**
2. Wait for build (5-10 minutes first time)
3. Watch build logs

### Step 6: Get Your URL

Once deployed, you'll get a URL like:
```
https://rynitive-ai.onrender.com
```

### Step 7: Test

Test your health endpoint:
```bash
curl https://your-app.onrender.com/health
```

Should return:
```json
{
  "status": "healthy",
  "timestamp": "...",
  "stripe_configured": false,
  "resend_configured": true
}
```

## 🔧 Render Free Tier Limitations

- ⚠️ **Spins down after 15 minutes of inactivity**
- ⚠️ **First request after spin-down takes 30-60 seconds** (cold start)
- ✅ Perfect for MVP testing
- ✅ No time limit on free tier
- ✅ No credit card required

## 💡 Important Notes

1. **Cold Starts:** Free tier apps "sleep" after 15 min inactivity
   - First request wakes it up (30-60 sec delay)
   - Subsequent requests are fast
   - For production, upgrade to paid tier ($7/month, no sleep)

2. **Build Time:** First deployment takes 5-10 minutes (downloading spaCy model)
   - Subsequent deployments are faster (~2-3 minutes)

3. **Logs:** Access logs via Render dashboard → Your service → Logs tab

## 🎯 Next Steps After Deployment

1. ✅ Verify /health endpoint works
2. ✅ Test local /test-scan endpoint (if ENVIRONMENT=development)
3. 🔜 Set up Stripe payment integration
4. 🔜 Create simple landing page
5. 🔜 First customer test!

## 📞 Troubleshooting

**Build fails:**
- Check build logs in Render dashboard
- Most common: spaCy model download timeout (just redeploy)

**Service won't start:**
- Check environment variables are set
- Check logs for specific errors

**Health check fails:**
- Verify PORT environment variable (Render sets this automatically)
- Check startCommand uses $PORT

## 🔐 Security Checklist

- ✅ Private GitHub repository
- ✅ .env file not committed
- ✅ Environment variables set in Render dashboard
- ✅ Render has access to only rynitive-ai repo

---

**Once deployed, your API will be live at: https://your-app-name.onrender.com**
