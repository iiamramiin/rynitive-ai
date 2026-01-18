"""
Rynitive AI - CSV Shareability Checker API
FastAPI backend with Stripe payment and email delivery
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
import os
import uuid
import pandas as pd
import stripe
import resend
from pathlib import Path
from dotenv import load_dotenv
import logging
from datetime import datetime
import tempfile
import base64
import resend


# Import our scanner and report generator
from scanner_enhanced import ShareabilityScanner
from report_generator import generate_report

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Rynitive AI - CSV Shareability Checker",
    description="Instant PII detection and shareability analysis for CSV datasets",
    version="1.0.0"
)

# CORS middleware (allow frontend to call API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "noreply@rynitive.ai")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
SUCCESS_URL = os.getenv("SUCCESS_URL", "http://localhost:3000/success")
CANCEL_URL = os.getenv("CANCEL_URL", "http://localhost:3000/")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "20"))

# Initialize Stripe
stripe.api_key = STRIPE_SECRET_KEY

# Initialize Resend
resend.api_key = RESEND_API_KEY

# Temporary file storage - use system temp for Railway compatibility
TEMP_DIR = Path(tempfile.gettempdir()) / "rynitive_uploads"
TEMP_DIR.mkdir(exist_ok=True)

# Initialize scanner
scanner = ShareabilityScanner()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Rynitive AI - CSV Shareability Checker",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "stripe_configured": bool(STRIPE_SECRET_KEY),
        "resend_configured": bool(RESEND_API_KEY),
        "temp_dir": str(TEMP_DIR),
        "temp_dir_exists": TEMP_DIR.exists()
    }


def validate_csv_file(file: UploadFile) -> tuple[bool, str]:
    """
    Validate uploaded file
    Returns: (is_valid, error_message)
    """
    # Check extension
    if not file.filename.lower().endswith('.csv'):
        return False, "Only CSV files are allowed"
    
    # Check file size (will be checked during read)
    # We'll validate size when reading the file
    
    return True, ""


def save_temp_file(file: UploadFile) -> Path:
    """
    Save uploaded file temporarily
    Returns: Path to saved file
    """
    # Generate unique filename
    unique_id = str(uuid.uuid4())
    file_path = TEMP_DIR / f"{unique_id}_{file.filename}"
    
    # Save file
    with open(file_path, "wb") as f:
        content = file.file.read()
        
        # Check size
        if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB"
            )
        
        f.write(content)
    
    return file_path


def cleanup_temp_file(file_path: Path):
    """Delete temporary file"""
    try:
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temp file: {e}")


@app.post("/create-checkout")
async def create_checkout(
    file: UploadFile = File(...),
    email: str = Form(...)
):
    """
    Create Stripe checkout session
    1. Validate file
    2. Save temporarily
    3. Create Stripe checkout
    4. Return checkout URL
    """
    
    logger.info(f"Checkout request from: {email}")
    
    # Validate email
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    
    # Validate file
    is_valid, error = validate_csv_file(file)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error)
    
    try:
        # Save file temporarily
        file_path = save_temp_file(file)
        logger.info(f"File saved: {file_path}")
        
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='payment',
            success_url='https://web-production-d94542.up.railway.app/scan?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=CANCEL_URL,
            customer_email=email,
            metadata={
                'file_path': str(file_path),
                'filename': file.filename,
                'email': email
            }
        )
        
        logger.info(f"Checkout session created: {checkout_session.id}")
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id
        }
        
    except Exception as e:
        logger.error(f"Error creating checkout: {e}")
        # Cleanup on error
        if 'file_path' in locals():
            cleanup_temp_file(file_path)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events
    Process payment confirmation and send report
    """
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle checkout.session.completed event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        
        logger.info(f"Payment successful for session: {session['id']}")
        
        # Get metadata
        file_path = session['metadata'].get('file_path')
        filename = session['metadata'].get('filename')
        email = session['metadata'].get('email')
        
        if not all([file_path, filename, email]):
            logger.error("Missing metadata in webhook")
            return JSONResponse({"status": "error", "message": "Missing metadata"})
        
        # Process the file
        try:
            await process_and_send_report(
                file_path=Path(file_path),
                filename=filename,
                email=email
            )
        except Exception as e:
            logger.error(f"Error processing report: {e}")
            # Send error email
            send_error_email(email, filename, str(e))
        finally:
            # Always cleanup temp file
            cleanup_temp_file(Path(file_path))
    
    return JSONResponse({"status": "success"})

@app.get("/scan")
async def scan_after_payment(session_id: str):
    """
    Handle redirect after successful payment
    Verify payment and process the file
    """
    
    logger.info(f"Scan request with session: {session_id}")
    
    try:
        # Retrieve the session from Stripe
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Check if payment was successful
        if session.payment_status != 'paid':
            raise HTTPException(status_code=400, detail="Payment not completed")
        
        # Get metadata
        file_path = session.metadata.get('file_path')
        filename = session.metadata.get('filename')
        email = session.metadata.get('email')
        
        if not all([file_path, filename, email]):
            raise HTTPException(status_code=400, detail="Missing file information")
        
        # Process the file
        await process_and_send_report(
            file_path=Path(file_path),
            filename=filename,
            email=email
        )
        
        # Return success page (HTML)
        return HTMLResponse(content="""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color: #10b981;">✓ Payment Successful!</h1>
            <p style="font-size: 1.2em;">Your CSV is being analyzed...</p>
            <p>You'll receive your report via email in 30-60 seconds.</p>
            <p style="margin-top: 40px;">
                <a href="https://rynitive.com" style="color: #8b5cf6; text-decoration: none;">← Back to Home</a>
            </p>
        </body>
        </html>
        """)
        
    except Exception as e:
        logger.error(f"Error in scan endpoint: {e}")
        return HTMLResponse(content="""
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1 style="color: #ef4444;">Error Processing Request</h1>
            <p>Please contact support@rynitive.com</p>
        </body>
        </html>
        """)

async def process_and_send_report(file_path: Path, filename: str, email: str):
    """
    Process CSV file and send PDF report via email
    """
    
    logger.info(f"Processing file: {filename} for {email}")
    
    try:
        # Load CSV
        df = pd.read_csv(file_path)
        logger.info(f"CSV loaded: {len(df)} rows, {len(df.columns)} columns")
        
        # Scan for PII
        scan_results = scanner.scan_csv(df, filename)
        logger.info(f"Scan complete. Readiness: {scan_results['readiness_level']}")
        
        # Generate PDF report
        pdf_path = generate_report(scan_results)
        logger.info(f"PDF generated: {pdf_path}")
        
        # Send email with PDF
        send_report_email(
            to_email=email,
            filename=filename,
            pdf_path=pdf_path,
            readiness_level=scan_results['readiness_level']
        )
        
        logger.info(f"Report sent successfully to {email}")
        
        # Cleanup PDF after sending
        cleanup_temp_file(Path(pdf_path))
        
    except Exception as e:
        logger.error(f"Error in process_and_send_report: {e}")
        raise


def send_report_email(to_email: str, filename: str, pdf_path: str, readiness_level: str):
    """
    Send PDF report via email using Resend
    """
    
    # Read PDF file and encode
    with open(pdf_path, 'rb') as f:
        pdf_content = base64.b64encode(f.read()).decode('utf-8')  # ✅ Base64 string!
    
    # Determine subject line based on readiness
    subject_suffix = {
        'RED': '🔴 Action Required',
        'YELLOW': '🟡 Review Recommended',
        'GREEN': '🟢 Low Risk Detected'
    }.get(readiness_level, '')
    
    subject = f"Your CSV Shareability Report - {subject_suffix}"
    
    # Email body
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #7c3aed;">Your Shareability Report is Ready!</h1>
            
            <p>Thank you for using Rynitive Checker. We've analyzed your dataset <strong>{filename}</strong>.</p>
            
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="margin-top: 0;">Quick Summary</h2>
                <p style="font-size: 1.1em;">
                    <strong>Shareability Level:</strong> 
                    <span style="color: {'#991b1b' if readiness_level == 'RED' else '#92400e' if readiness_level == 'YELLOW' else '#065f46'}">
                        {readiness_level}
                    </span>
                </p>
                <p><em>See the attached PDF for complete analysis and recommendations.</em></p>
            </div>
            
            <h3>What's in Your Report:</h3>
            <ul>
                <li>PII detection results (emails, phones, names, SSNs, etc.)</li>
                <li>Quasi-identifier analysis (age, ZIP, gender combinations)</li>
                <li>Re-identification risk assessment</li>
                <li>Specific recommendations for your dataset</li>
            </ul>
            
            <div style="background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0;">
                <p style="margin: 0;"><strong>⚠️ Important:</strong> This is an automated analysis tool. 
                For regulated data (HIPAA/GDPR), please consult your compliance team before sharing.</p>
            </div>
            
            <p>Questions? Reply to this email or contact us at <a href="mailto:support@rynitive.com">support@rynitive.com</a></p>
            
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
            
            <p style="font-size: 0.9em; color: #6b7280;">
                <strong>Rynitive</strong><br>
                Fast privacy scans for datasets<br>
                <a href="https://rynitive.com">rynitive.com</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    try:
        # Send email via Resend
        response = resend.Emails.send({
            "from": RESEND_FROM_EMAIL,
            "to": to_email,
            "subject": subject,
            "html": html_body,
            "attachments": [{
                "filename": f"shareability_report_{datetime.now().strftime('%Y%m%d')}.pdf",
                "content": pdf_content  # ✅ Now it's a string!
            }]
        })
        
        logger.info(f"Email sent successfully: {response}")
        
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise


def send_error_email(to_email: str, filename: str, error_message: str):
    """
    Send error notification email
    """
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h1 style="color: #dc2626;">Processing Error</h1>
            
            <p>We encountered an error while processing your file <strong>{filename}</strong>.</p>
            
            <div style="background: #fee2e2; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0;"><strong>Error:</strong> {error_message}</p>
            </div>
            
            <p>Your payment has been processed. We'll investigate this issue and send you the report as soon as possible.</p>
            
            <p>If you have questions, please contact <a href="mailto:support@rynitive.com">support@rynitive.com</a> 
            with your file name and this error message.</p>
            
            <p>We apologize for the inconvenience.</p>
            
            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
            
            <p style="font-size: 0.9em; color: #6b7280;">
                <strong>Rynitive</strong><br>
                <a href="https://rynitive.com">rynitive.com</a>
            </p>
        </div>
    </body>
    </html>
    """
    
    try:
        resend.Emails.send({
            "from": RESEND_FROM_EMAIL,
            "to": to_email,
            "subject": "Error Processing Your CSV - Rynitive",
            "html": html_body
        })
        logger.info(f"Error email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send error email: {e}")


# For local testing
@app.post("/test-scan")
async def test_scan(file: UploadFile = File(...)):
    """
    Test endpoint - scan without payment (for development only)
    Remove this in production!
    """
    
    if os.getenv("ENVIRONMENT") != "development":
        raise HTTPException(status_code=403, detail="Endpoint disabled in production")
    
    file_path = save_temp_file(file)
    
    try:
        df = pd.read_csv(file_path)
        results = scanner.scan_csv(df, file.filename)
        
        return {
            "filename": file.filename,
            "readiness_level": results['readiness_level'],
            "pii_count": results['pii_count'],
            "direct_identifiers": results['direct_identifier_columns'],
            "quasi_identifiers": results['quasi_identifiers'],
            "recommendations": results['recommendations'][:3]
        }
    finally:
        cleanup_temp_file(file_path)

@app.post("/webhook/email")
async def receive_email(request: Request):
    """Handle incoming emails and forward to Gmail"""
    try:
        payload = await request.json()
        
        # Log the full payload to see structure
        logger.info(f"Webhook payload: {payload}")
        
        # Try different possible data structures
        email_data = payload.get('data', payload)
        
        from_email = email_data.get('from', {})
        if isinstance(from_email, dict):
            from_address = from_email.get('email', 'Unknown')
        else:
            from_address = from_email
        
        to_email = email_data.get('to', [])
        if isinstance(to_email, list) and len(to_email) > 0:
            to_address = to_email[0].get('email', '') if isinstance(to_email[0], dict) else to_email[0]
        else:
            to_address = str(to_email)
        
        subject = email_data.get('subject', 'No Subject')
        html_content = email_data.get('html', email_data.get('html_body', ''))
        text_content = email_data.get('text', email_data.get('text_body', ''))
        
        # Forward to your Gmail
        resend.Emails.send({
            "from": "noreply@rynitive.com",
            "to": "iiamramiin@gmail.com",
            "subject": f"Support: {subject}",
            "html": f"""
                <h3>New Support Email</h3>
                <p><strong>From:</strong> {from_address}</p>
                <p><strong>To:</strong> {to_address}</p>
                <p><strong>Subject:</strong> {subject}</p>
                <hr>
                <h4>Message:</h4>
                {html_content or text_content or '<p>No content</p>'}
            """
        })
        
        return {"status": "received"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        logger.error(f"Full error: {str(e)}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    PORT = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=PORT)
