"""OVH Email client for sending emails via SMTP."""
import syslog
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from typing import List, Optional, Dict, Tuple
import ovh


class OVHEmailClient:
    """Client for sending emails through SMTP (with fallback to OVH API for domain info)."""
    
    def __init__(
        self,
        application_key: Optional[str] = None,
        application_secret: Optional[str] = None,
        consumer_key: Optional[str] = None,
        endpoint: str = "ovh-eu",
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
    ):
        """
        Initialize OVH email client.
        
        Args:
            application_key: OVH application key (optional, for domain info only)
            application_secret: OVH application secret (optional, for domain info only)
            consumer_key: OVH consumer key (optional, for domain info only)
            endpoint: OVH API endpoint (default: ovh-eu)
            smtp_host: SMTP server hostname (e.g., ssl0.ovh.net)
            smtp_port: SMTP server port (587 for STARTTLS, 465 for SSL)
            smtp_user: SMTP username (usually full email address)
            smtp_password: SMTP password
        """
        # OVH API client (for domain info only) - optional
        if application_key and application_secret and consumer_key:
            self.client = ovh.Client(
                endpoint=endpoint,
                application_key=application_key,
                application_secret=application_secret,
                consumer_key=consumer_key,
            )
        else:
            self.client = None
        
        # SMTP configuration
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port or 587
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
    
    def send_email(
        self,
        sender: str,
        to: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        inline_images: Optional[List[Tuple[str, bytes, str]]] = None,
        dry_run: bool = False,
    ) -> bool:
        """
        Send an email via SMTP.

        Args:
            sender: Sender email address
            to: List of recipient email addresses
            subject: Email subject
            body_text: Plain text body (optional)
            body_html: HTML body (optional)
            cc: List of CC recipients (optional)
            bcc: List of BCC recipients (optional)
            inline_images: List of (content_id, image_data, mime_subtype) tuples for inline images
            dry_run: If True, don't make actual SMTP calls
            
        Returns:
            True if email sent successfully, False otherwise
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                f"[DRY RUN] Would send email from {sender} to {', '.join(to)}",
            )
            return True
            
        # Validate sender
        if "@" not in sender:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Invalid sender email: {sender}",
            )
            return False
        
        # Validate recipients
        if not to or len(to) == 0:
            syslog.syslog(
                syslog.LOG_ERR,
                "No recipients specified",
            )
            return False
        
        # Check SMTP configuration
        if not self.smtp_host or not self.smtp_user or not self.smtp_password:
            syslog.syslog(
                syslog.LOG_ERR,
                "SMTP not configured (missing host, user, or password)",
            )
            return False
            
        try:
            # Create message
            from email.utils import formatdate, make_msgid

            if inline_images:
                # Use related > alternative structure for inline images
                msg = MIMEMultipart('related')
                msg_alt = MIMEMultipart('alternative')
                msg.attach(msg_alt)
            else:
                msg = MIMEMultipart('alternative')
                msg_alt = msg

            msg['From'] = sender
            msg['To'] = ', '.join(to)
            msg['Subject'] = subject
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain=sender.split('@')[1] if '@' in sender else 'mail.local')

            if cc:
                msg['Cc'] = ', '.join(cc)

            # Add body (at least one is required)
            if not body_html and not body_text:
                raise ValueError("At least one of body_text or body_html must be provided")

            if body_text:
                part_text = MIMEText(body_text, 'plain', 'utf-8')
                msg_alt.attach(part_text)

            if body_html:
                part_html = MIMEText(body_html, 'html', 'utf-8')
                msg_alt.attach(part_html)

            # Attach inline images
            if inline_images:
                for content_id, image_data, subtype in inline_images:
                    img = MIMEImage(image_data, _subtype=subtype)
                    img.add_header('Content-ID', f'<{content_id}>')
                    img.add_header('Content-Disposition', 'inline', filename=f'{content_id}.{subtype}')
                    msg.attach(img)
            
            # Prepare recipient list (to + cc + bcc)
            all_recipients = to.copy()
            if cc:
                all_recipients.extend(cc)
            if bcc:
                all_recipients.extend(bcc)
            
            # Send email via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()  # Upgrade to secure connection
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(sender, all_recipients, msg.as_string())
            
            syslog.syslog(
                syslog.LOG_INFO,
                f"Successfully sent email to {', '.join(to)} via SMTP",
            )
            return True
            
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to send email via SMTP: {e}",
            )
            return False
    
    def list_email_domains(self, dry_run: bool = False) -> List[str]:
        """
        List all email domains available in the OVH account.
        
        Args:
            dry_run: If True, don't make actual API calls
        
        Returns:
            List of domain names
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                "[DRY RUN] Would list email domains",
            )
            return []
        
        if not self.client:
            syslog.syslog(
                syslog.LOG_WARNING,
                "OVH API client not configured, cannot list domains",
            )
            return []
            
        try:
            domains = self.client.get("/email/domain")
            return domains
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to list email domains: {e}",
            )
            return []
    
    def get_domain_info(self, domain: str, dry_run: bool = False) -> Optional[Dict]:
        """
        Get information about a specific email domain.
        
        Args:
            domain: Domain name
            dry_run: If True, don't make actual API calls
            
        Returns:
            Domain information dict if successful, None otherwise
        """
        if dry_run:
            syslog.syslog(
                syslog.LOG_INFO,
                f"[DRY RUN] Would get info for domain: {domain}",
            )
            return None
        
        if not self.client:
            syslog.syslog(
                syslog.LOG_WARNING,
                "OVH API client not configured, cannot get domain info",
            )
            return None
            
        try:
            info = self.client.get(f"/email/domain/{domain}")
            return info
        except Exception as e:
            syslog.syslog(
                syslog.LOG_ERR,
                f"Failed to get domain info for {domain}: {e}",
            )
            return None
