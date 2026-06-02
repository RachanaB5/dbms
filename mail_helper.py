import os
import smtplib
import threading
import logging
from dotenv import load_dotenv
load_dotenv(override=True)
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

logger = logging.getLogger(__name__)

# Directory to log sent HTML emails inside the workspace for easy testing & local verification
EMAILS_LOG_DIR = os.path.join(os.path.dirname(__file__), 'static', 'emails')
os.makedirs(EMAILS_LOG_DIR, exist_ok=True)

class MailHelper:
    @staticmethod
    def _send_async_email(to_email, subject, html_content):
        # 1. Log and save HTML email locally to static/emails/ for instant visual auditing
        try:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            safe_email = to_email.replace('@', '_at_').replace('.', '_')
            filename = f"{timestamp}_{safe_email}.html"
            filepath = os.path.join(EMAILS_LOG_DIR, filename)
            
            # Wrap in a beautiful frame for the visual log
            log_frame = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    .email-metadata {{
                        background: #f0f0fa;
                        border-bottom: 2px solid #e6e6fa;
                        padding: 15px;
                        font-family: monospace;
                        font-size: 0.9rem;
                        color: #483d8b;
                        border-radius: 8px 8px 0 0;
                    }}
                    .email-body {{
                        padding: 20px;
                        background: #ffffff;
                    }}
                </style>
            </head>
            <body style="margin: 20px; background: #fafafa; font-family: sans-serif;">
                <div style="max-width: 600px; margin: 0 auto; border: 1px solid #ddd; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); overflow:hidden;">
                    <div class="email-metadata">
                        <strong>TO:</strong> {to_email}<br>
                        <strong>SUBJECT:</strong> {subject}<br>
                        <strong>DATE:</strong> {datetime.utcnow().strftime('%b %d, %Y %H:%M:%S UTC')}
                    </div>
                    <div class="email-body">
                        {html_content}
                    </div>
                </div>
            </body>
            </html>
            """
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(log_frame)
            logger.info(f"HTML email logged locally: static/emails/{filename}")
        except Exception as e:
            logger.error(f"Failed to log HTML email locally: {e}")

        # 2. Attempt SMTP sending if environment variables are set
        smtp_server = os.environ.get('SMTP_SERVER')
        smtp_port = os.environ.get('SMTP_PORT', 587)
        smtp_user = os.environ.get('SMTP_USER')
        smtp_pass = os.environ.get('SMTP_PASS')
        sender_email = os.environ.get('SENDER_EMAIL', 'noreply@curiocart.com')

        if smtp_server and smtp_user and smtp_pass:
            try:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = sender_email
                msg['To'] = to_email

                part = MIMEText(html_content, 'html')
                msg.attach(part)

                with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_pass)
                    server.sendmail(sender_email, to_email, msg.as_string())
                logger.info(f"Email sent successfully to {to_email} via SMTP.")
            except Exception as e:
                logger.error(f"SMTP sending failed to {to_email}: {e}")
        else:
            logger.info("SMTP environment variables not configured. Skipping SMTP sending, logged locally only.")

    @classmethod
    def send_email(cls, to_email, subject, html_content):
        # Execute asynchronously in a background thread so the user experience is instant (zero latency!)
        thread = threading.Thread(target=cls._send_async_email, args=(to_email, subject, html_content))
        thread.daemon = True
        thread.start()

    @classmethod
    def send_welcome_email(cls, to_email, username):
        subject = "Welcome to curiocart - Experience Elegance!"
        html_content = f"""
        <div style="font-family: 'Poppins', sans-serif; color: #2f4f4f; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #6a5acd, #483d8b); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; color: white;">
                <h1 style="margin: 0; font-size: 2.2rem; font-weight: 800; text-transform: lowercase;">curiocart</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Curated elegance for your lifestyle</p>
            </div>
            <div style="padding: 30px; background: #ffffff; border: 1px solid #e6e6fa; border-radius: 0 0 8px 8px;">
                <h2 style="color: #483d8b; margin-top: 0;">Welcome, {username}!</h2>
                <p>We are absolutely thrilled to welcome you to the curiocart family. Our mission is to connect you with handcrafted, premium solutions spanning top electronics, dynamic fashion designs, educational readings, and beauty essentials.</p>
                
                <div style="background: #f8f8ff; border: 1.5px dashed #6a5acd; border-radius: 8px; padding: 20px; text-align: center; margin: 25px 0;">
                    <span style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: #20b2aa; display: block; margin-bottom: 5px;">Exclusive Welcome Treat</span>
                    <strong style="font-size: 1.8rem; color: #ff7f50; letter-spacing: 1px;">WELCOME20</strong>
                    <span style="font-size: 0.9rem; color: #556b2f; display: block; margin-top: 5px;">Enjoy a massive 20% OFF on your very first order!</span>
                </div>
                
                <p>Browse our sensational catalog, customize your profile, and feel free to reach out to our 24/7 client support desk whenever you need assistance.</p>
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="http://127.0.0.1:5000/products" style="display: inline-block; padding: 12px 30px; background: linear-gradient(to right, #6a5acd, #9370db); color: white; text-decoration: none; border-radius: 30px; font-weight: bold; box-shadow: 0 4px 15px rgba(106, 90, 205, 0.3);">Explore Catalog Now</a>
                </div>
            </div>
        </div>
        """
        cls.send_email(to_email, subject, html_content)

    @classmethod
    def send_order_confirmation_email(cls, to_email, username, order):
        subject = f"Order Confirmed! Receipt for Order #{order.id}"
        
        # Build items table rows
        items_rows = ""
        for item in order.items:
            prod_name = item.product.name if item.product else "Product"
            discount_text = f" ({item.discount_at_time}% OFF)" if item.discount_at_time else ""
            items_rows += f"""
            <tr style="border-bottom: 1px solid #e6e6fa;">
                <td style="padding: 10px 5px; color: #2f4f4f;">{prod_name}{discount_text}</td>
                <td style="padding: 10px 5px; text-align: center; color: #2f4f4f;">{item.quantity}</td>
                <td style="padding: 10px 5px; text-align: right; font-weight: 600; color: #483d8b;">₹{item.subtotal:.2f}</td>
            </tr>
            """

        html_content = f"""
        <div style="font-family: 'Poppins', sans-serif; color: #2f4f4f; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #20b2aa, #6a5acd); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; color: white;">
                <i class="fas fa-check-circle" style="font-size: 3rem; margin-bottom: 10px;"></i>
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 800;">Order Confirmed!</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Thank you for shopping at curiocart</p>
            </div>
            <div style="padding: 30px; background: #ffffff; border: 1px solid #e6e6fa; border-radius: 0 0 8px 8px;">
                <h3 style="color: #483d8b; margin-top: 0;">Hi {username},</h3>
                <p>We are delighted to inform you that your order has been received and confirmed. Our packaging desk is currently preparing your premium package for shipping.</p>
                
                <h4 style="color: #483d8b; border-bottom: 2px solid #e6e6fa; padding-bottom: 5px; margin-top: 30px;">Order Summary</h4>
                <div style="margin-bottom: 15px; font-size: 0.9rem;">
                    <strong>Order ID:</strong> #{order.id}<br>
                    <strong>Order Date:</strong> {order.created_at.strftime('%b %d, %Y %I:%M %p')}<br>
                    <strong>Status:</strong> {order.status.upper()}
                </div>
                
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 25px;">
                    <thead>
                        <tr style="border-bottom: 2px solid #e6e6fa; text-align: left; font-size: 0.9rem; color: #556b2f;">
                            <th style="padding: 5px;">Item</th>
                            <th style="padding: 5px; text-align: center;">Qty</th>
                            <th style="padding: 5px; text-align: right;">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_rows}
                        <tr>
                            <td colspan="2" style="padding: 15px 5px 5px; font-weight: 700; text-align: right; color: #2f4f4f;">TOTAL AMOUNT PAID:</td>
                            <td style="padding: 15px 5px 5px; text-align: right; font-weight: 800; font-size: 1.2rem; color: #6a5acd;">₹{order.total_amount:.2f}</td>
                        </tr>
                    </tbody>
                </table>
                
                <h4 style="color: #483d8b; border-bottom: 2px solid #e6e6fa; padding-bottom: 5px;">Delivery Details</h4>
                <p style="font-size: 0.95rem; line-height: 1.5; color: #556b2f;">
                    <strong>Recipient:</strong> {username}<br>
                    <strong>Shipping Address:</strong><br>
                    {order.shipping_address},<br>
                    {order.shipping_city}, {order.shipping_state} - {order.shipping_zip}
                </p>
                
                <div style="text-align: center; margin-top: 30px; border-top: 1px solid #e6e6fa; padding-top: 20px;">
                    <a href="http://127.0.0.1:5000/dashboard" style="display: inline-block; padding: 10px 25px; background: #20b2aa; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; box-shadow: 0 4px 15px rgba(32, 178, 170, 0.3);">Track Order on Dashboard</a>
                </div>
            </div>
        </div>
        """
        cls.send_email(to_email, subject, html_content)

    @classmethod
    def send_order_status_update_email(cls, to_email, username, order, status):
        subject = f"Order #{order.id} Status Update: {status.upper()}"
        
        tracking_info = ""
        if order.tracking_number:
            tracking_info = f"""
            <div style="background: #f8f8ff; border: 1.5px solid #20b2aa; border-radius: 8px; padding: 15px; margin: 20px 0;">
                <span style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: #20b2aa; display: block;">Tracking Registered</span>
                <strong style="font-size: 1.2rem; color: #483d8b;">{order.tracking_number}</strong>
                <span style="font-size: 0.85rem; color: #556b2f; display: block; margin-top: 2px;">Enter this code on standard courier pages to view shipping stages.</span>
            </div>
            """

        notes_info = ""
        if order.notes:
            notes_info = f"""
            <p style="background: #fafafa; border-left: 4px solid #6a5acd; padding: 10px 15px; font-style: italic; font-size: 0.95rem; color: #556b2f;">
                <strong>Desk Note:</strong> "{order.notes}"
            </p>
            """

        html_content = f"""
        <div style="font-family: 'Poppins', sans-serif; color: #2f4f4f; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #6a5acd, #20b2aa); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; color: white;">
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 800;">Shipping Update</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Order #{order.id} is now {status.upper()}</p>
            </div>
            <div style="padding: 30px; background: #ffffff; border: 1px solid #e6e6fa; border-radius: 0 0 8px 8px;">
                <h3 style="color: #483d8b; margin-top: 0;">Dear {username},</h3>
                <p>We are writing to provide a live status update regarding your curiocart order <strong>#{order.id}</strong>.</p>
                
                <div style="text-align: center; padding: 15px; margin: 20px 0; background: rgba(106, 90, 205, 0.1); border-radius: 10px;">
                    <span style="font-size: 0.9rem; color: #556b2f; font-weight: 600;">NEW STATUS</span>
                    <div style="font-size: 1.8rem; font-weight: 800; color: #483d8b; text-transform: uppercase; margin-top: 5px;">{status}</div>
                </div>

                {tracking_info}
                {notes_info}

                <p>If you have any questions or require custom shipment packaging revisions, feel free to connect with our support staff directly.</p>
                
                <div style="text-align: center; margin-top: 30px; border-top: 1px solid #e6e6fa; padding-top: 20px;">
                    <a href="http://127.0.0.1:5000/dashboard" style="display: inline-block; padding: 10px 25px; background: #6a5acd; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; box-shadow: 0 4px 15px rgba(106, 90, 205, 0.3);">View Dashboard History</a>
                </div>
            </div>
        </div>
        """
        cls.send_email(to_email, subject, html_content)

    @classmethod
    def send_password_reset_email(cls, to_email, username):
        subject = "Security Update: Password Reset Successful"
        html_content = f"""
        <div style="font-family: 'Poppins', sans-serif; color: #2f4f4f; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #ff7f50, #483d8b); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; color: white;">
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 800;">Security Update</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Password successfully modified</p>
            </div>
            <div style="padding: 30px; background: #ffffff; border: 1px solid #e6e6fa; border-radius: 0 0 8px 8px;">
                <h3 style="color: #483d8b; margin-top: 0;">Hello {username},</h3>
                <p>This email is to confirm that the password for your curiocart account associated with email <strong>{to_email}</strong> has been successfully updated.</p>
                
                <div style="background: #fff8f8; border-left: 4px solid #ff7f50; padding: 15px; margin: 20px 0; font-size: 0.95rem; color: #2f4f4f;">
                    <strong>Security Alert:</strong> If you did not request this password modification, please contact our support staff immediately to freeze your account auth states.
                </div>
                
                <p>If this change was performed by you, you may now securely log in using your newly configured credentials.</p>
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="http://127.0.0.1:5000/login" style="display: inline-block; padding: 10px 25px; background: linear-gradient(to right, #ff7f50, #ff6347); color: white; text-decoration: none; border-radius: 8px; font-weight: bold; box-shadow: 0 4px 15px rgba(255, 127, 80, 0.3);">Go to Login</a>
                </div>
            </div>
        </div>
        """
        cls.send_email(to_email, subject, html_content)

    @classmethod
    def send_login_notification_email(cls, to_email, username):
        subject = "Security Alert: New Login Detected"
        html_content = f"""
        <div style="font-family: 'Poppins', sans-serif; color: #2f4f4f; line-height: 1.6;">
            <div style="background: linear-gradient(135deg, #483d8b, #ff7f50); padding: 30px; text-align: center; border-radius: 8px 8px 0 0; color: white;">
                <h1 style="margin: 0; font-size: 1.8rem; font-weight: 800;">New Login Detected</h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Security Notification for your curiocart account</p>
            </div>
            <div style="padding: 30px; background: #ffffff; border: 1px solid #e6e6fa; border-radius: 0 0 8px 8px;">
                <h3 style="color: #483d8b; margin-top: 0;">Hi {username},</h3>
                <p>We detected a new login to your curiocart account associated with <strong>{to_email}</strong> on {datetime.utcnow().strftime('%b %d, %Y %I:%M %p UTC')}.</p>
                
                <div style="background: #f8f8ff; border: 1px solid #e6e6fa; border-radius: 8px; padding: 15px; margin: 20px 0; font-size: 0.95rem;">
                    <strong>Details:</strong><br>
                    • <strong>Platform / Device:</strong> Web Browser<br>
                    • <strong>Time:</strong> {datetime.utcnow().strftime('%b %d, %Y %I:%M %p UTC')}<br>
                    • <strong>Status:</strong> Successful Login
                </div>
                
                <p style="color: #556b2f;">If this was you, you can safely ignore this email. No action is required.</p>
                
                <div style="background: #fff8f8; border-left: 4px solid #ff7f50; padding: 12px; margin: 20px 0; font-size: 0.9rem; color: #2f4f4f;">
                    <strong>Did not recognize this activity?</strong><br>
                    Please change your password immediately on your profile dashboard to secure your account.
                </div>
                
                <div style="text-align: center; margin-top: 30px; border-top: 1px solid #e6e6fa; padding-top: 20px;">
                    <a href="http://127.0.0.1:5000/dashboard" style="display: inline-block; padding: 10px 25px; background: #483d8b; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; box-shadow: 0 4px 15px rgba(72, 61, 139, 0.3);">Go to Dashboard</a>
                </div>
            </div>
        </div>
        """
        cls.send_email(to_email, subject, html_content)
