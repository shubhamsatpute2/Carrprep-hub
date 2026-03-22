# Email Configuration Guide - CareerPrep Hub

## Overview

CareerPrep Hub now includes a feature to send users their **progress summary and resume list via email**. This allows users to:
- View their complete progress metrics (resumes created, interviews taken, practice score)
- Get a formatted email with all their resume details
- Receive professional email summaries they can save and share

## Setting Up Email Service

### Prerequisites

- SMTP email service (Gmail, Outlook, S  return runner.run(main)
           ~~~~~~~~~~^^^^^^
  File "C:\Users\sneha\AppData\Local\Python\pythoncore-3.14-64\Lib\asyncio\runners.py", line 127, in run      
    return self._loop.run_until_complete(task)
           ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^
  File "C:\Users\sneha\AppData\Local\Python\pythoncore-3.14-64\Lib\asyncio\base_events.py", line 719, in run_until_complete
    return future.result()
           ~~~~~~~~~~~~~^^
  File "c:\Users\sneha\Downloads\CareerPrepHub-main (2)\.venv\Lib\site-packages\uvicorn\server.py", line 79, in serve
    await self._serve(sockets)
  File "c:\Users\sneha\Downloads\CareerPrepHub-main (2)\.venv\Lib\site-packages\uvicorn\server.py", line 86, in _serve
    config.load()
    ~~~~~~~~~~~^^
  File "c:\Users\sneha\Downloads\CareerPrepHub-main (2)\.venv\Lib\site-packages\uvicorn\config.py", line 441, in load
    self.loaded_app = import_from_string(self.app)
                      ~~~~~~~~~~~~~~~~~~^^^^^^^^^^
  File "c:\Users\sneha\Downloads\CareerPrepHub-main (2)\.venv\Lib\site-packages\uvicorn\importer.py", line 22, in import_from_string
    raise exc from None
  File "c:\Users\sneha\Downloads\CareerPrepHub-main (2)\.venv\Lib\site-packages\uvicorn\importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
  File "C:\Users\sneha\AppData\Local\Python\pythoncore-3.14-64\Lib\importlib\__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
           ~~~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "<frozen importlib._bootstrap>", line 1398, in _gcd_import
  File "<frozen importlib._bootstrap>", line 1371, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1342, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 938, in _load_unlocked
  File "<frozen importlib._bootstrap_external>", line 759, in exec_module
  File "<frozen importlib._bootstrap>", line 491, in _call_with_frames_removed
  File "C:\Users\sneha\Downloads\CareerPrepHub-main (2)\CareerPrepHub-main\backend\app.py", line 24, in <module>
    import httpx
ModuleNotFoundError: No module named 'httpx'endGrid, etc.)
- Email credentials with SMTP access enabled
- Backend running with environment variables configured

### Step-by-Step Setup

#### Option 1: Gmail (Recommended for Development)

1. **Create a Google Account** (if you don't have one)

2. **Enable 2-Factor Authentication**
   - Go to myaccount.google.com
   - Select "Security" in the left menu
   - Scroll down to "2-Step Verification" and enable it

3. **Generate App Password**
   - Go to myaccount.google.com
   - Select "Security" in the left menu
   - Under "App passwords", select Mail and Windows Computer
   - Google will generate a 16-character password
   - Copy this password (without spaces)

4. **Configure Environment Variables**
   Create or edit `.env` file in the backend directory:

   ```env
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SENDER_EMAIL=your-email@gmail.com
   SENDER_PASSWORD=your-16-char-app-password
   APP_URL=http://localhost:5173
   ```

#### Option 2: SendGrid (Recommended for Production)

1. **Create SendGrid Account**
   - Sign up at sendgrid.com
   - Verify email address

2. **Get API Key**
   - Go to Settings > API Keys
   - Create a new API Key
   - Copy the key (save it securely)

3. **Configure Environment Variables**
   ```env
   SMTP_SERVER=smtp.sendgrid.net
   SMTP_PORT=587
   SENDER_EMAIL=apikey
   SENDER_PASSWORD=SG.xxxxx_your_api_key_xxxxx
   APP_URL=http://localhost:5173
   ```

#### Option 3: Microsoft Outlook

1. **Get Your Credentials**
   - Email: your-email@outlook.com
   - Password: your-outlook-password

2. **Configure Environment Variables**
   ```env
   SMTP_SERVER=smtp.office365.com
   SMTP_PORT=587
   SENDER_EMAIL=your-email@outlook.com
   SENDER_PASSWORD=your-outlook-password
   APP_URL=http://localhost:5173
   ```

### Environment Variables Explained

| Variable | Description | Example |
|----------|-------------|---------|
| `SMTP_SERVER` | SMTP server address | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP port (usually 587 for TLS) | `587` |
| `SENDER_EMAIL` | Email address sending the emails | `noreply@example.com` |
| `SENDER_PASSWORD` | Password or app-specific password | `16-char-password` |
| `APP_URL` | Frontend URL for links in emails | `http://localhost:5173` |

## Features Implemented

### 1. Progress Email Endpoint
**Endpoint:** `POST /api/user/send-progress-email`

**Requires:** User authentication (Bearer token)

**Returns:**
```json
{
  "message": "Progress email sent successfully",
  "email": "user@example.com",
  "resumes_count": 2,
  "interviews_taken": 5,
  "practice_score": 75.5
}
```

### 2. Welcome Email
Automatically sent when user registers (if email service is configured)

### 3. Email Template
The progress email includes:
- User greeting
- Progress metrics cards (visual representation):
  - Resumes created (with count)
  - Interviews taken (with count)  
  - Practice score (with progress bar)
- List of all created resumes with details:
  - Resume name
  - Email on resume
  - Creation date
  - Link to view/edit
- Tips for improvement based on progress
- Call-to-action button to dashboard

## Frontend Components

### New Component: ProgressSummary

Located at: `frontend/src/components/ProgressSummary.jsx`

**Features:**
- Displays user's current progress metrics
- Shows formatted progress cards with emojis
- "Send Progress Email" button
- Success/error notifications
- Tips section based on user's progress
- Beautiful gradient design

**Access:** 
- Users can access via "My Progress" tab in navigation (📈)
- Only visible when logged in

### Sample Screenshot
```
┌─────────────────────────────────────────────┐
│  Your Progress Summary                      │
├─────────────────────────────────────────────┤
│  [📄 Resumes]  [🎤 Interviews]  [⭐ Score] │
│   Created: 2     Taken: 5        Score: 75%│
├─────────────────────────────────────────────┤
│  📧 Email Your Progress                     │
│  Send summary to your email...              │
│  [📧 Send Progress Email]                   │
└─────────────────────────────────────────────┘
```

## How to Use

### For Users:

1. **Register/Login** to CareerPrep Hub
2. **Navigate** to "My Progress" tab (📈) in the navigation bar
3. **View** your progress metrics on the page
4. **Click** "📧 Send Progress Email" button
5. **Receive** formatted email with:
   - Your progress summary
   - List of all your resumes
   - Links to view/edit resumes
   - Tips for improvement

### For Developers:

1. **Set up** environment variables (see Configuration above)
2. **Restart** backend server
3. **Test** by:
   ```bash
   # Terminal 1: Start backend with email configured
   cd backend
   python -m uvicorn app:app --reload
   
   # Terminal 2: Start frontend
   cd frontend
   npm run dev
   ```
4. **Create** test account and register
5. **Navigate** to My Progress tab
6. **Click** "Send Progress Email" to test

## Testing the Email Service

### Using Gmail Sandbox

Without SMTP credentials, emails won't be sent but won't cause errors:

```python
# email_service.py will log:
# "Email service not configured. Skipping email send."
```

### With Gmail App Password

1. Check backend logs for email send confirmations:
   ```
   INFO:     Email sent successfully to user@example.com
   ```

2. Verify receipt in user's email inbox

3. Check spam/junk folder if not in inbox

### Error Troubleshooting

| Error | Solution |
|-------|----------|
| `Connection refused` | Check SMTP_SERVER and SMTP_PORT are correct |
| `Authentication failed` | Verify SENDER_EMAIL and SENDER_PASSWORD |
| `No such module 'email'` | Python email module is built-in, no installation needed |
| `Email not received` | Check spam folder, verify configuration |

## Email Template Customization

To customize the email template, edit `backend/email_service.py`:

**Progress Email HTML:**
- Located in `create_progress_email_html()` function
- Modify colors, text, layout as needed
- Variables available:
  - `user_name`: Display user's full name
  - `resumes_count`: Number of resumes created
  - `interviews_taken`: Number of interviews completed
  - `practice_score`: Score percentage
  - `resumes`: List of resume objects with details
  - `APP_URL`: Frontend URL for links

**Example modification:**
```python
# Change email subject
msg["Subject"] = "Your Custom Subject Here"

# Change gradient color
background: linear-gradient(135deg, #your-color #another-color)
```

## Security Notes

⚠️ **Important Security Guidelines:**

1. **Never commit** `.env` file to version control
2. **Never log** sensitive credentials
3. **Use app-specific passwords** for Gmail (not main password)
4. **Rotate credentials** periodically
5. **Whitelist sender domain** in production
6. **Use SendGrid or similar** service for production (not personal email)

### Production Setup

For production deployment:

```env
# .env (production)
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SENDER_EMAIL=apikey
SENDER_PASSWORD=${SENDGRID_API_KEY}  # Set as environment secret
APP_URL=https://your-production-domain.com
```

## API Reference

### Send Progress Email

```
POST /api/user/send-progress-email
Authorization: Bearer {token}
Content-Type: application/json

Response (200 OK):
{
  "message": "Progress email sent successfully",
  "email": "user@example.com",
  "resumes_count": 2,
  "interviews_taken": 5,
  "practice_score": 75.5
}

Response (500 Error):
{
  "detail": "Failed to send email. Please check email configuration."
}
```

## Logs

Email service logs are printed to console:

```bash
# Successful send
INFO:     Email sent successfully to user@example.com

# Service not configured
WARNING: Email service not configured. Skipping email send.

# Error during send
ERROR:    Failed to send email to user@example.com: [error details]
```

## Roadmap

Future enhancements:
- [ ] Email notification on resume updates
- [ ] Weekly/monthly progress reports
- [ ] Email reminders for practice sessions
- [ ] Custom email templates per user
- [ ] Email scheduling (send at specific times)
- [ ] Email verification on registration
- [ ] Unsubscribe options

## Support

For issues with email functionality:

1. Check backend logs for error messages
2. Verify environment variables are set correctly
3. Test SMTP credentials with a simple script
4. Check spam/junk folders in email
5. Ensure 2FA and app passwords are enabled (Gmail)

---

**Last Updated:** March 1, 2026
**Version:** 1.0.0
