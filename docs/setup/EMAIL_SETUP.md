# Email Configuration Setup

## Current Status

- Email utility code is implemented
- SMTP-based password reset flow exists
- Email credentials must come from local or deployment-managed secrets

## Gmail SMTP Configuration

The backend can send email via Gmail SMTP. Configuration belongs in `backend/.env` or deployment-managed secrets:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=your-email@example.com
EMAIL_PASSWORD=your-app-password
EMAIL_FROM=ZeroQwait <your-email@example.com>
FRONTEND_URL=http://localhost:3000
```

## Current Issue

Gmail is rejecting the app password with error:
```
535 5.7.8 Username and Password not accepted
```

## Steps to Fix

### Option 1: Verify App Password (Recommended)
1. Go to https://myaccount.google.com/apppasswords
2. Make sure you're signed in to `usvisachat@gmail.com`
3. **Important**: 2-Step Verification must be enabled first
   - Go to https://myaccount.google.com/security
   - Enable 2-Step Verification if not already enabled
4. Once 2-Step is enabled, go back to App Passwords
5. Create a new app password:
   - Select app: "Mail"
   - Select device: "Other (Custom name)"
   - Enter name: "ZeroQwait"
6. Copy the 16-character password (it will have spaces)
7. Update `backend/.env` with the password and keep it out of version control:
   ```env
   EMAIL_PASSWORD=abcdabcdabcdabcd
   ```
8. Restart backend:
   ```bash
   docker compose restart backend
   ```

### Option 2: Use Different Email Service

Instead of Gmail SMTP, you can use:

#### SendGrid (Recommended for Production)
- Free tier: 100 emails/day
- Sign up: https://sendgrid.com
- Get API key
- Update `backend/.env`:
  ```env
  SENDGRID_API_KEY=your_api_key
  ```
- Modify `email_utils.py` to use SendGrid SDK

#### AWS SES
- Very cheap: $0.10 per 1,000 emails
- More setup required

#### Mailgun
- Free tier: 5,000 emails/month
- Easy to set up

## Testing Email Functionality

### Via API
```bash
curl -X POST "http://localhost:8000/api/auth/forgot-password?email=test@example.com"
```

### Via Frontend
1. Go to http://localhost:3000/login
2. Click "Forgot password?"
3. Enter your email
4. Check the email inbox

### Check Logs
```bash
docker compose logs backend --tail=20
```

## Email Features Implemented

### 1. Password Reset
- Endpoint: `POST /api/auth/forgot-password`
- Sends styled HTML email with reset link
- Link expires in 1 hour
- Includes both plain text and HTML versions

### 2. Email Template
The email includes:
- Professional HTML styling
- Branded colors (#4a90e2)
- Clear call-to-action button
- Expiration notice
- Security reminder

## For Production

### Security Best Practices
1. **Never commit credentials** - Use environment variables
2. **Use app-specific passwords** - Never use main account password
3. **Enable 2-Step Verification** - Required for app passwords
4. **Rotate passwords regularly** - Change every 90 days
5. **Monitor email logs** - Watch for abuse

### Recommended Email Service
For production, switch from Gmail SMTP to a dedicated email service:
- **SendGrid**: Best for marketing + transactional
- **AWS SES**: Best for high volume, low cost
- **Postmark**: Best for transactional emails
- **Mailgun**: Good middle ground

### Rate Limits
Gmail SMTP limits:
- 500 emails per day
- 100-150 emails per hour

For a real app, you'll hit these quickly. Use a dedicated service instead.

## Code Location

- Email utility: `backend/email_utils.py`
- Usage in auth: `backend/routers/auth.py`
- Configuration: `backend/.env`

## Next Steps

1. ✅ Fix Gmail app password issue (follow Option 1 above)
2. ⏳ Test password reset flow end-to-end
3. ⏳ Add welcome email on registration (optional)
4. ⏳ Add email verification flow (optional)
5. ⏳ Switch to SendGrid/SES for production
