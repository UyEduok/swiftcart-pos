import secrets
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from datetime import datetime

def generate_reset_code(length=6):
    return ''.join(secrets.choice('0123456789') for _ in range(length))

def send_reset_code_email(email, code):
    subject = 'SwiftCart Password Reset Code'
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [email]

    # Auto year for footer
    current_year = datetime.now().year

    # Plain text fallback
    text_content = f'Your SwiftCart password reset code is: {code}\nIf you did not request this, please change your login details and contact admin immediately.'

    # HTML content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                padding: 0;
                margin: 0;
            }}
            .email-container {{
                max-width: 600px;
                margin: auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #4CAF50;
                padding: 20px;
                text-align: center;
            }}
            .header img {{
                max-width: 150px;
            }}
            .content {{
                padding: 20px;
                color: #333333;
            }}
            .code-box {{
                font-size: 26px;
                font-weight: bold;
                background-color: #f9f9f9;
                padding: 10px 20px;
                border: 2px dashed #4CAF50;
                text-align: center;
                margin: 20px 0;
                border-radius: 6px;
            }}
            .footer {{
                background-color: #f4f4f4;
                padding: 10px;
                text-align: center;
                font-size: 12px;
                color: #888888;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="logo-wrapper" style="background-color:#333; padding:20px; text-align:center;">
                <img src="http://localhost:5173/src/assets/home/design.png" alt="SwiftCart Logo" style="max-width:150px;">
            </div>

            <div class="content">
                <h2>Password Reset Request</h2>
                <p>We received a request to reset your SwiftCart account password.</p>
                <p>Use the verification code below to reset your password. This code will expire in <b>6 minutes</b>.</p>
                <div class="code-box">{code}</div>
                <p>If you did not request this change, please change your login details and contact admin immediately.</p>
                <p>Thank you,<br>The SwiftCart Team</p>
            </div>
            <div class="footer">
                &copy; {current_year} SwiftCart. All rights reserved.
            </div>
        </div>
    </body>
    </html>
    """

    # Create and send
    msg = EmailMultiAlternatives(subject, text_content, from_email, to)
    msg.attach_alternative(html_content, "text/html")
    msg.send()
