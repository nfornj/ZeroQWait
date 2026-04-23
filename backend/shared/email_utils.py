"""
Email utility for sending password reset emails.
Uses Gmail SMTP for sending emails.
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://zeroqwait.com")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "usvisachat@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "ZeroQwait <usvisachat@gmail.com>")

def send_password_reset_email(email: str, reset_token: str):
    """
    Send password reset email with reset link via Gmail SMTP.
    """
    reset_link = f"{FRONTEND_URL}/reset-password?token={reset_token}"
    
    # Create email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Password Reset Request - ZeroQwait'
    msg['From'] = EMAIL_FROM
    msg['To'] = email
    
    # Create plain text and HTML versions
    text_content = f"""
    Password Reset Request
    
    You requested to reset your password for ZeroQwait.
    
    Click the link below to reset your password:
    {reset_link}
    
    This link will expire in 1 hour.
    
    If you didn't request this, please ignore this email.
    """
    
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
          <h2 style="color: #4a90e2;">Password Reset Request</h2>
          <p>You requested to reset your password for ZeroQwait.</p>
          <p>Click the button below to reset your password:</p>
          <div style="margin: 30px 0;">
            <a href="{reset_link}" 
               style="background-color: #4a90e2; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 4px; display: inline-block;">
              Reset Password
            </a>
          </div>
          <p style="color: #666; font-size: 14px;">This link will expire in 1 hour.</p>
          <p style="color: #666; font-size: 14px;">If you didn't request this, please ignore this email.</p>
        </div>
      </body>
    </html>
    """
    
    # Attach both versions
    part1 = MIMEText(text_content, 'plain')
    part2 = MIMEText(html_content, 'html')
    msg.attach(part1)
    msg.attach(part2)
    
    # Send email
    try:
        if not EMAIL_PASSWORD:
            # If no password configured, just log
            logger.info("=" * 80)
            logger.info("PASSWORD RESET EMAIL (Email not configured - logging only)")
            logger.info(f"To: {email}")
            logger.info(f"Reset Link: {reset_link}")
            logger.info("=" * 80)
            print(f"\n🔐 PASSWORD RESET EMAIL\n📧 To: {email}\n🔗 Link: {reset_link}\n")
            return True
        
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Password reset email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {str(e)}")
        # Log to console as fallback
        print(f"\n⚠️  EMAIL SEND FAILED\n📧 To: {email}\n🔗 Link: {reset_link}\n❌ Error: {str(e)}\n")
        # Still return True so the user gets the success message (security best practice)
        return True
