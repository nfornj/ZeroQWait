# Password Reset Feature

## Overview
The password reset feature allows users to reset their password via email link.

## User Flow
1. User clicks "Forgot password?" link on the login page
2. User enters their email address on the forgot password page
3. If the email exists in the system, a password reset link is sent
4. User clicks the link in their email (or checks backend logs in development)
5. User enters a new password on the reset password page
6. User is redirected to login page with success message

## Implementation Details

### Backend Components

#### 1. Database Model
- **PasswordResetToken** (`backend/models.py`)
  - Stores password reset tokens with expiration (1 hour)
  - Fields: `id`, `user_id`, `token`, `created_at`, `expires_at`, `used`

#### 2. API Endpoints
- **POST /api/auth/forgot-password** (`backend/routers/auth.py`)
  - Request: `email` (query parameter)
  - Generates a secure token and sends reset email
  - Returns success message even if email doesn't exist (prevents email enumeration)

- **POST /api/auth/reset-password** (`backend/routers/auth.py`)
  - Request: `token`, `new_password` (query parameters)
  - Validates token (exists, not expired, not used)
  - Updates user password and marks token as used

#### 3. Email Utility
- **send_password_reset_email()** (`backend/email_utils.py`)
  - For development: Logs reset link to console
  - For production: Ready to integrate with email service (SendGrid, AWS SES, etc.)
  - Reset link format: `http://localhost:3000/reset-password?token={token}`

### Frontend Components

#### 1. Forgot Password Page
- **ForgotPasswordPage** (`frontend/src/pages/ForgotPasswordPage.tsx`)
  - User enters email address
  - Shows success message after submission
  - Provides link back to login page

#### 2. Reset Password Page
- **ResetPasswordPage** (`frontend/src/pages/ResetPasswordPage.tsx`)
  - Extracts token from URL query parameter
  - User enters new password and confirmation
  - Validates password match and minimum length (6 characters)
  - Shows success message and redirects to login

#### 3. Login Page Update
- **LoginPage** (`frontend/src/pages/LoginPage.tsx`)
  - Added "Forgot password?" link below password field

## Security Features
- **Secure token generation**: Uses `secrets.token_urlsafe(32)` for cryptographically secure tokens
- **Time-limited tokens**: Tokens expire after 1 hour
- **One-time use**: Tokens cannot be reused after password reset
- **Email enumeration prevention**: Returns same success message whether email exists or not
- **Password hashing**: Passwords are hashed with bcrypt before storage

## Testing in Development

### Requesting a Password Reset
```bash
curl -X POST "http://localhost:8000/api/auth/forgot-password?email=user@example.com"
```

### Check Backend Logs for Reset Link
```bash
docker-compose logs backend | grep -A 3 "PASSWORD RESET EMAIL"
```

Example output:
```
🔐 PASSWORD RESET EMAIL
📧 To: user@example.com
🔗 Link: http://localhost:3000/reset-password?token=ABC123...
```

### Copy the token from the link and use it to reset password
```bash
curl -X POST "http://localhost:8000/api/auth/reset-password?token=YOUR_TOKEN&new_password=newpass123"
```

## Production Setup

To enable email sending in production, update `backend/email_utils.py`:

1. **Install email service SDK** (e.g., SendGrid):
   ```bash
   pip install sendgrid
   ```

2. **Set environment variables**:
   ```bash
   export SENDGRID_API_KEY="your-api-key"
   export FRONTEND_URL="https://yourdomain.com"
   ```

3. **Uncomment the email sending code** in `send_password_reset_email()` function

## Routes
- `/forgot-password` - Forgot password page
- `/reset-password?token=...` - Reset password page with token
- `/api/auth/forgot-password` - Backend endpoint to request reset
- `/api/auth/reset-password` - Backend endpoint to reset password

## Database Migration
The `password_reset_tokens` table is automatically created by SQLAlchemy when the application starts. No manual migration is needed.
