import secrets
import logging
from django.core.mail import EmailMultiAlternatives, BadHeaderError
from django.conf import settings
from datetime import datetime
from smtplib import SMTPException

logger = logging.getLogger(__name__)

def generate_reset_code(length=6):
    return ''.join(secrets.choice('0123456789') for _ in range(length))

def send_reset_code_email(email, code):
    try:
        subject = 'SwiftCart Password Reset Code'
        from_email = settings.DEFAULT_FROM_EMAIL
        to = [email]

        current_year = datetime.now().year

        text_content = (
            f'Your SwiftCart password reset code is: {code}\n'
            f'If you did not request this, please change your login details and contact admin immediately.'
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; }}
            .email-container {{ max-width: 600px; margin: auto; background-color: #fff; padding: 20px; }}
            .code-box {{ font-size: 26px; font-weight: bold; background-color: #f9f9f9; padding: 10px; border: 2px dashed #4CAF50; text-align: center; }}
            .footer {{ background-color: #f4f4f4; padding: 10px; text-align: center; font-size: 12px; color: #888; }}
        </style>
        </head>
        <body>
            <div class="email-container">
                <h2>Password Reset Request</h2>
                <p>Use the verification code below to reset your password. This code will expire in <b>6 minutes</b>.</p>
                <div class="code-box">{code}</div>
                <p>If you did not request this change, please change your login details and contact admin immediately.</p>
                <div class="footer">&copy; {current_year} SwiftCart. All rights reserved.</div>
            </div>
        </body>
        </html>
        """

        msg = EmailMultiAlternatives(subject, text_content, from_email, to)
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

    except BadHeaderError as e:
        logger.error(f"Bad header error for {email}: {e}")
        raise e
    except SMTPException as e:
        logger.error(f"SMTP error for {email}: {e}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error for {email}: {e}")
        raise e
