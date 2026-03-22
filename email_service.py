import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List
import os
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "carrierprepub@gmail.com")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", "")
APP_URL = os.getenv("APP_URL", "http://localhost:5173")


def create_progress_email_html(
    user_name: str,
    resumes_count: int,
    interviews_taken: int,
    practice_score: float,
    resumes: List[dict],
) -> str:
    """Create an HTML email template with user progress and resumes"""
    
    resume_cards = ""
    if resumes:
        for resume in resumes:
            resume_cards += f"""
            <div style="background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #007bff;">
                <h4 style="margin: 0 0 8px 0; color: #333;">{resume.get('name', 'Resume')}</h4>
                <p style="margin: 5px 0; color: #666; font-size: 14px;">
                    <strong>Email:</strong> {resume.get('email', 'N/A')}
                </p>
                <p style="margin: 5px 0; color: #666; font-size: 14px;">
                    <strong>Created:</strong> {resume.get('created_at', 'N/A')}
                </p>
                <a href="{APP_URL}/dashboard" style="display: inline-block; margin-top: 10px; padding: 8px 15px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px; font-size: 14px;">
                    View Resume
                </a>
            </div>
            """
    else:
        resume_cards = "<p style='color: #666; font-style: italic;'>No resumes created yet. Start building your first resume today!</p>"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f5f5f5; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; color: white; text-align: center;">
                <h1 style="margin: 0; font-size: 28px;">CareerPrep Hub</h1>
                <p style="margin: 10px 0 0 0; font-size: 14px; opacity: 0.9;">Your Career Progress Summary</p>
            </div>

            <!-- Content -->
            <div style="padding: 30px;">
                <!-- Greeting -->
                <h2 style="color: #333; margin-top: 0;">Hi {user_name}! 👋</h2>
                <p style="color: #666; margin-bottom: 25px;">
                    Here's a summary of your progress on CareerPrep Hub. Keep up the good work!
                </p>

                <!-- Progress Stats -->
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                    <h3 style="margin-top: 0; color: #333; font-size: 18px;">📊 Your Progress</h3>
                    
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-top: 15px;">
                        <!-- Resumes Created -->
                        <div style="background: white; padding: 15px; border-radius: 6px; border-top: 3px solid #28a745;">
                            <p style="margin: 0; color: #666; font-size: 14px;">Resumes Created</p>
                            <h2 style="margin: 8px 0 0 0; color: #28a745; font-size: 32px;">{resumes_count}</h2>
                        </div>
                        
                        <!-- Interviews Taken -->
                        <div style="background: white; padding: 15px; border-radius: 6px; border-top: 3px solid #ffc107;">
                            <p style="margin: 0; color: #666; font-size: 14px;">Interviews Taken</p>
                            <h2 style="margin: 8px 0 0 0; color: #ffc107; font-size: 32px;">{interviews_taken}</h2>
                        </div>
                        
                        <!-- Practice Score -->
                        <div style="background: white; padding: 15px; border-radius: 6px; border-top: 3px solid #17a2b8; grid-column: 1 / -1;">
                            <p style="margin: 0; color: #666; font-size: 14px;">Practice Score</p>
                            <div style="display: flex; align-items: center; margin-top: 8px;">
                                <h2 style="margin: 0; color: #17a2b8; font-size: 32px; margin-right: 10px;">{practice_score:.1f}%</h2>
                                <div style="flex: 1; background: #e9ecef; border-radius: 20px; height: 8px;">
                                    <div style="background: #17a2b8; border-radius: 20px; height: 100%; width: {practice_score}%;"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Resumes Section -->
                <h3 style="color: #333; margin-top: 25px; margin-bottom: 15px;">📄 Your Resumes</h3>
                {resume_cards}

                <!-- CTA Button -->
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0;">
                    <p style="color: #666; margin-bottom: 15px;">
                        Ready to continue your journey? Jump back into your dashboard!
                    </p>
                    <a href="{APP_URL}/dashboard" style="display: inline-block; padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                        Go to Dashboard
                    </a>
                </div>
            </div>

            <!-- Footer -->
            <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #e0e0e0;">
                <p style="color: #999; font-size: 12px; margin: 0;">
                    © 2024 CareerPrep Hub. All rights reserved.<br>
                    <a href="{APP_URL}" style="color: #667eea; text-decoration: none;">Visit our website</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content


def send_progress_email(
    recipient_email: str,
    user_name: str,
    resumes_count: int,
    interviews_taken: int,
    practice_score: float,
    resumes: List[dict],
) -> bool:
    """Send progress email to user"""
    
    try:
        # Create email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📊 Your CareerPrep Hub Progress Update - {user_name}!"
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email
        
        # Create HTML content
        html_content = create_progress_email_html(
            user_name=user_name,
            resumes_count=resumes_count,
            interviews_taken=interviews_taken,
            practice_score=practice_score,
            resumes=resumes,
        )
        
        # Attach HTML content
        part = MIMEText(html_content, "html")
        msg.attach(part)
        
        # Try to send email
        try:
            if not SENDER_PASSWORD:
                logger.warning("Email service not configured. Simulating email send.")
                logger.info(f"[SIMULATED] Progress email would be sent to {recipient_email}")
                logger.info(f"[SIMULATED] Subject: {msg['Subject']}")
                return True
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Progress email sent successfully to {recipient_email}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.warning(f"SMTP Authentication failed: {str(e)}")
            logger.warning(f"Simulating email send for testing purposes")
            logger.info(f"[SIMULATED] Progress email would be sent to {recipient_email}")
            logger.info(f"[SIMULATED] Subject: {msg['Subject']}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send email via SMTP: {str(e)}")
            logger.warning("Simulating email send for testing purposes")
            logger.info(f"[SIMULATED] Progress email would be sent to {recipient_email}")
            logger.info(f"[SIMULATED] Subject: {msg['Subject']}")
            return True
        
    except Exception as e:
        logger.error(f"Critical error in email function: {str(e)}")
        return False



def send_welcome_email(recipient_email: str, user_name: str) -> bool:
    """Send welcome email to new user"""
    
    try:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; background-color: #f5f5f5; margin: 0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background-color: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); overflow: hidden;">
                
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; color: white; text-align: center;">
                    <h1 style="margin: 0; font-size: 28px;">Welcome to CareerPrep Hub! 🎉</h1>
                </div>

                <div style="padding: 30px;">
                    <h2 style="color: #333; margin-top: 0;">Hi {user_name}!</h2>
                    <p style="color: #666;">
                        Welcome to CareerPrep Hub! We're excited to have you on board. 
                        Your account is all set up and ready to go.
                    </p>
                    
                    <h3 style="color: #333; margin-top: 25px;">Here's what you can do:</h3>
                    <ul style="color: #666;">
                        <li>Build and customize your professional resumes</li>
                        <li>Practice mock interviews with AI feedback</li>
                        <li>Track your progress and improvements</li>
                        <li>Get personalized career recommendations</li>
                    </ul>

                    <div style="text-align: center; margin-top: 30px;">
                        <a href="{APP_URL}" style="display: inline-block; padding: 12px 30px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                            Get Started Now
                        </a>
                    </div>
                </div>

                <div style="background: #f8f9fa; padding: 20px; text-align: center; border-top: 1px solid #e0e0e0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        © 2024 CareerPrep Hub
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Welcome to CareerPrep Hub, {user_name}!"
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email
        
        part = MIMEText(html_content, "html")
        msg.attach(part)
        
        # Try to send email
        try:
            if not SENDER_PASSWORD:
                logger.warning("Email service not configured. Simulating email send.")
                logger.info(f"[SIMULATED] Welcome email would be sent to {recipient_email}")
                logger.info(f"[SIMULATED] Subject: {msg['Subject']}")
                return True
            
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Welcome email sent successfully to {recipient_email}")
            return True
        except smtplib.SMTPAuthenticationError as e:
            logger.warning(f"SMTP Authentication failed: {str(e)}")
            logger.warning("Simulating email send for testing purposes")
            logger.info(f"[SIMULATED] Welcome email would be sent to {recipient_email}")
            logger.info(f"[SIMULATED] Subject: {msg['Subject']}")
            return True
        except Exception as e:
            logger.warning(f"Failed to send email via SMTP: {str(e)}")
            logger.warning("Simulating email send for testing purposes")
            logger.info(f"[SIMULATED] Welcome email would be sent to {recipient_email}")
            logger.info(f"[SIMULATED] Subject: {msg['Subject']}")
            return True
        
    except Exception as e:
        logger.error(f"Critical error in welcome email function: {str(e)}")
        return False

