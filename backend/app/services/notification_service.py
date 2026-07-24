"""
Notification Service for OIC NetRadar

Handles:
- SMS notifications via SMS gateway
- Email notifications via SMTP
- Retry logic for failed notifications
- Notification templates
"""

import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx
import json

from app.config import settings

logger = logging.getLogger(__name__)

class NotificationService:
    """
    Service for sending notifications via SMS and Email.
    
    Features:
    - SMS gateway integration with retry
    - SMTP email with templates
    - Notification status tracking
    - Fallback mechanism
    """
    
    def __init__(self):
        self.sms_gateway_url = settings.SMS_GATEWAY_URL
        self.sms_api_key = settings.SMS_API_KEY
        
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_from = settings.SMTP_FROM
        
        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        # Fallback notification channel
        self.fallback_webhook = getattr(settings, 'FALLBACK_WEBHOOK', None)
        
    async def send_sms(
        self,
        phone_number: str,
        message: str,
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send SMS notification with retry logic.
        
        Args:
            phone_number: Recipient phone number
            message: SMS message (max 160 chars)
            ticket_id: Optional ticket ID for tracking
            
        Returns:
            Dict with status and details
        """
        # Truncate message to 160 characters
        if len(message) > 160:
            message = message[:157] + "..."
        
        start_time = datetime.utcnow()
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"📱 Sending SMS attempt {attempt} to {phone_number}")
                
                if self.sms_gateway_url:
                    # Use configured SMS gateway
                    success = await self._send_via_gateway(phone_number, message)
                else:
                    # Fallback to logging (for development)
                    success = await self._send_via_log(phone_number, message)
                
                if success:
                    logger.info(f"✅ SMS sent to {phone_number} (attempt {attempt})")
                    return {
                        "success": True,
                        "attempt": attempt,
                        "phone_number": phone_number,
                        "ticket_id": ticket_id,
                        "sent_at": datetime.utcnow().isoformat() + "Z"
                    }
                else:
                    logger.warning(f"⚠️ SMS attempt {attempt} failed for {phone_number}")
                    
            except Exception as e:
                logger.error(f"❌ SMS error (attempt {attempt}): {e}")
            
            # Wait before retry (except last attempt)
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)
        
        # All retries failed - try fallback
        logger.error(f"❌ All SMS attempts failed for {phone_number}")
        
        # Try fallback notification channel
        if self.fallback_webhook:
            await self._send_fallback_alert(message, ticket_id)
        
        return {
            "success": False,
            "attempts": self.max_retries,
            "phone_number": phone_number,
            "ticket_id": ticket_id,
            "error": "All retry attempts failed"
        }
    
    async def _send_via_gateway(self, phone_number: str, message: str) -> bool:
        """Send SMS via external gateway."""
        try:
            payload = {
                "api_key": self.sms_api_key,
                "to": phone_number,
                "message": message,
                "sender": "NetRadar"
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.sms_gateway_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Check gateway-specific success indicator
                    return data.get("success", True)
                else:
                    logger.error(f"Gateway returned {response.status_code}: {response.text}")
                    return False
                    
        except httpx.TimeoutException:
            logger.error("SMS gateway timeout")
            return False
        except httpx.HTTPStatusError as e:
            logger.error(f"SMS gateway HTTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"SMS gateway error: {e}")
            return False
    
    async def _send_via_log(self, phone_number: str, message: str) -> bool:
        """Log SMS (development fallback)."""
        logger.info(f"📱 [SMS - DEV] To: {phone_number}")
        logger.info(f"📝 Message: {message}")
        return True
    
    async def _send_fallback_alert(self, message: str, ticket_id: Optional[str] = None):
        """Send fallback alert via webhook (e.g., Telegram, Slack)."""
        try:
            if not self.fallback_webhook:
                return
            
            payload = {
                "text": f"🚨 NetRadar Fallback Alert\nTicket: {ticket_id}\n{message}",
                "ticket_id": ticket_id
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(self.fallback_webhook, json=payload)
                logger.info("Fallback alert sent")
                
        except Exception as e:
            logger.error(f"Fallback alert failed: {e}")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None,
        ticket_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send email notification.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            ticket_id: Optional ticket ID for tracking
            
        Returns:
            Dict with status and details
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"📧 Sending email attempt {attempt} to {to_email}")
                
                success = await self._send_email_smtp(to_email, subject, body, html_body)
                
                if success:
                    logger.info(f"✅ Email sent to {to_email} (attempt {attempt})")
                    return {
                        "success": True,
                        "attempt": attempt,
                        "to_email": to_email,
                        "ticket_id": ticket_id,
                        "sent_at": datetime.utcnow().isoformat() + "Z"
                    }
                else:
                    logger.warning(f"⚠️ Email attempt {attempt} failed for {to_email}")
                    
            except Exception as e:
                logger.error(f"❌ Email error (attempt {attempt}): {e}")
            
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)
        
        logger.error(f"❌ All email attempts failed for {to_email}")
        return {
            "success": False,
            "attempts": self.max_retries,
            "to_email": to_email,
            "ticket_id": ticket_id,
            "error": "All retry attempts failed"
        }
    
    async def _send_email_smtp(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """Send email via SMTP."""
        if not self.smtp_host:
            # Development fallback
            logger.info(f"📧 [Email - DEV] To: {to_email}")
            logger.info(f"📝 Subject: {subject}")
            logger.info(f"📝 Body: {body[:200]}...")
            return True
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["From"] = self.smtp_from
            msg["To"] = to_email
            msg["Subject"] = subject
            msg["X-Priority"] = "1"  # High priority
            msg["X-MSMail-Priority"] = "High"
            
            # Add plain text
            msg.attach(MIMEText(body, "plain"))
            
            # Add HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_port == 587:
                    server.starttls()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)
            
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error: {e}")
            return False
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return False
    
    # ====================================================================
    # Notification Templates (Section 8)
    # ====================================================================
    
    def build_alert_message(
        self,
        device: Dict,
        diagnostic: Dict,
        ticket_id: str,
        level: int = 1,
        agent_name: Optional[str] = None,
        agent_phone: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Build notification message based on escalation level.
        
        Section 8 Requirements:
        - Level 1 (Network Agent): Full diagnostic + acknowledge link
        - SMS: Short format with hostname, IP, reason, ticket
        - Level 2 (Supervisor): Explicit escalation notification
        
        Returns:
            Dict with sms, email_subject, email_body, email_html
        """
        hostname = device.get("hostname", "Unknown")
        ip = device.get("ip_address", "Unknown")
        failure_reason = diagnostic.get("diagnostics", {}).get("failure_reason", "UNKNOWN")
        details = diagnostic.get("diagnostics", {}).get("details", "No details available")
        severity = diagnostic.get("impact_level", "MEDIUM")
        
        # Format failure reason for display
        reason_display = failure_reason.replace("_", " ").title()
        
        # Base URL for links
        base_url = getattr(settings, 'BASE_URL', 'https://netradar.oic.com.et')
        acknowledge_url = f"{base_url}/tickets/{ticket_id}/acknowledge"
        dashboard_url = f"{base_url}/dashboard"
        
        # SMS message (short format)
        sms_message = (
            f"NetRadar ALERT: {hostname} ({ip}) DOWN. "
            f"Reason: {reason_display}. "
            f"Ticket: {ticket_id[:8]}. "
            f"Severity: {severity}"
        )
        
        if level == 1:
            # Level 1: Network Agent Email
            email_subject = f"🚨 [NetRadar] ALERT: {hostname} ({ip}) - {reason_display}"
            email_body = self._build_level1_email(
                device, diagnostic, ticket_id, 
                acknowledge_url, dashboard_url
            )
            email_html = self._build_level1_email_html(
                device, diagnostic, ticket_id,
                acknowledge_url, dashboard_url
            )
        else:
            # Level 2: Supervisor/Manager Email
            email_subject = f"⚠️ [NetRadar] ESCALATED: {hostname} ({ip}) - UNACKNOWLEDGED"
            email_body = self._build_level2_email(
                device, diagnostic, ticket_id,
                agent_name, agent_phone,
                dashboard_url
            )
            email_html = self._build_level2_email_html(
                device, diagnostic, ticket_id,
                agent_name, agent_phone,
                dashboard_url
            )
        
        return {
            "sms": sms_message,
            "email_subject": email_subject,
            "email_body": email_body,
            "email_html": email_html
        }
    
    def _build_level1_email(
        self,
        device: Dict,
        diagnostic: Dict,
        ticket_id: str,
        acknowledge_url: str,
        dashboard_url: str
    ) -> str:
        """Build Level 1 email body (Network Agent)."""
        hostname = device.get("hostname", "Unknown")
        ip = device.get("ip_address", "Unknown")
        branch = device.get("branch_name", "Unknown")
        severity = diagnostic.get("impact_level", "MEDIUM")
        
        diag = diagnostic.get("diagnostics", {})
        failure_reason = diag.get("failure_reason", "UNKNOWN")
        details = diag.get("details", "No details available")
        root_cause = diag.get("root_cause_analysis", {})
        
        return f"""
================================================================================
🚨 NetRadar ALERT - Level 1
================================================================================

Severity: {severity}
Location: {branch} - {hostname} ({ip})
Ticket ID: {ticket_id}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

-------------------------------------------------------------------------------
ROOT CAUSE DIAGNOSTIC
-------------------------------------------------------------------------------

Failure Reason: {failure_reason.replace('_', ' ').title()}
Details: {details}

Diagnostic Details:
  - Ping Status: {diag.get('ping_status', 'UNKNOWN')}
  - Gateway Reachable: {root_cause.get('gateway_reachable', False)}
  - Gateway IP: {root_cause.get('gateway_ip', 'Unknown')}
  - Switch Port Status: {root_cause.get('switch_port_status', 'Unknown')}
  - Responding Ports: {', '.join([str(p['port']) for p in root_cause.get('responding_ports', [])])}
  - SNMP Available: {root_cause.get('snmp_available', False)}
  - Traceroute Last Hop: {root_cause.get('traceroute_last_hop', 'Unknown')}

-------------------------------------------------------------------------------
ACTION REQUIRED
-------------------------------------------------------------------------------

1. Acknowledge this alert: {acknowledge_url}
2. Investigate the issue using the diagnostic information above
3. If unable to resolve, escalate to IT Supervisor

View full dashboard: {dashboard_url}

================================================================================
This is an automated alert from OIC NetRadar Monitoring System
"""
    
    def _build_level1_email_html(
        self,
        device: Dict,
        diagnostic: Dict,
        ticket_id: str,
        acknowledge_url: str,
        dashboard_url: str
    ) -> str:
        """Build Level 1 email HTML body."""
        hostname = device.get("hostname", "Unknown")
        ip = device.get("ip_address", "Unknown")
        severity = diagnostic.get("impact_level", "MEDIUM")
        failure_reason = diagnostic.get("diagnostics", {}).get("failure_reason", "UNKNOWN")
        details = diagnostic.get("diagnostics", {}).get("details", "No details available")
        
        severity_colors = {
            "CRITICAL": "#dc3545",
            "HIGH": "#fd7e14",
            "MEDIUM": "#ffc107",
            "LOW": "#28a745"
        }
        color = severity_colors.get(severity, "#6c757d")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #1a1a2e; color: white; padding: 20px; text-align: center; }}
        .alert-box {{ border-left: 4px solid {color}; padding: 15px; margin: 20px 0; background-color: #f8f9fa; }}
        .severity-{severity.lower()} {{ color: {color}; font-weight: bold; }}
        .details {{ background-color: #f1f3f5; padding: 15px; margin: 10px 0; border-radius: 4px; }}
        .button {{ display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 4px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚨 OIC NetRadar Alert</h1>
            <p>Level 1 - Network Agent</p>
        </div>
        
        <div class="alert-box">
            <h2>Device: {hostname} ({ip})</h2>
            <p><strong>Severity:</strong> <span class="severity-{severity.lower()}">{severity}</span></p>
            <p><strong>Ticket ID:</strong> {ticket_id}</p>
            <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
        
        <h3>Root Cause Diagnostic</h3>
        <div class="details">
            <p><strong>Failure Reason:</strong> {failure_reason.replace('_', ' ').title()}</p>
            <p><strong>Details:</strong> {details}</p>
            <p><strong>Diagnostic:</strong> {diagnostic.get('diagnostics', {}).get('root_cause_analysis', {})}</p>
        </div>
        
        <h3>Action Required</h3>
        <p>1. <a href="{acknowledge_url}" class="button">Acknowledge Alert</a></p>
        <p>2. Investigate using the diagnostic information above</p>
        <p>3. If unable to resolve, escalate to IT Supervisor</p>
        
        <p><a href="{dashboard_url}">View Full Dashboard →</a></p>
        
        <div class="footer">
            This is an automated alert from OIC NetRadar Monitoring System
        </div>
    </div>
</body>
</html>
"""
    
    def _build_level2_email(
        self,
        device: Dict,
        diagnostic: Dict,
        ticket_id: str,
        agent_name: Optional[str],
        agent_phone: Optional[str],
        dashboard_url: str
    ) -> str:
        """Build Level 2 email body (Supervisor/Manager)."""
        hostname = device.get("hostname", "Unknown")
        ip = device.get("ip_address", "Unknown")
        branch = device.get("branch_name", "Unknown")
        severity = diagnostic.get("impact_level", "MEDIUM")
        
        diag = diagnostic.get("diagnostics", {})
        failure_reason = diag.get("failure_reason", "UNKNOWN")
        details = diag.get("details", "No details available")
        
        return f"""
================================================================================
⚠️ NetRadar ESCALATION - Level 2 (UNACKNOWLEDGED)
================================================================================

Severity: {severity}
Location: {branch} - {hostname} ({ip})
Ticket ID: {ticket_id}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

-------------------------------------------------------------------------------
ESCALATION NOTICE
-------------------------------------------------------------------------------

This alert was escalated because Level 1 (Network Agent) was unacknowledged.

Assigned Agent: {agent_name or 'Not assigned'}
Agent Phone: {agent_phone or 'Not available'}

-------------------------------------------------------------------------------
DIAGNOSTIC INFORMATION
-------------------------------------------------------------------------------

Failure Reason: {failure_reason.replace('_', ' ').title()}
Details: {details}

-------------------------------------------------------------------------------
ACTION REQUIRED
-------------------------------------------------------------------------------

1. This alert requires your immediate attention
2. Contact the Network Agent if available
3. Investigate and resolve the issue

View full dashboard: {dashboard_url}

================================================================================
This is an automated escalation from OIC NetRadar Monitoring System
"""
    
    def _build_level2_email_html(
        self,
        device: Dict,
        diagnostic: Dict,
        ticket_id: str,
        agent_name: Optional[str],
        agent_phone: Optional[str],
        dashboard_url: str
    ) -> str:
        """Build Level 2 email HTML body."""
        hostname = device.get("hostname", "Unknown")
        ip = device.get("ip_address", "Unknown")
        severity = diagnostic.get("impact_level", "MEDIUM")
        failure_reason = diagnostic.get("diagnostics", {}).get("failure_reason", "UNKNOWN")
        details = diagnostic.get("diagnostics", {}).get("details", "No details available")
        
        return f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #dc3545; color: white; padding: 20px; text-align: center; }}
        .alert-box {{ border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0; background-color: #f8f9fa; }}
        .escalation {{ background-color: #fff3cd; padding: 15px; margin: 10px 0; border-radius: 4px; border: 1px solid #ffc107; }}
        .details {{ background-color: #f1f3f5; padding: 15px; margin: 10px 0; border-radius: 4px; }}
        .button {{ display: inline-block; padding: 10px 20px; background-color: #dc3545; color: white; text-decoration: none; border-radius: 4px; }}
        .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ NetRadar Escalation</h1>
            <p>Level 2 - Supervisor/Manager</p>
        </div>
        
        <div class="alert-box">
            <h2>Device: {hostname} ({ip})</h2>
            <p><strong>Severity:</strong> {severity}</p>
            <p><strong>Ticket ID:</strong> {ticket_id}</p>
            <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
        </div>
        
        <div class="escalation">
            <h3>⚠️ ESCALATION NOTICE</h3>
            <p>This alert was escalated because Level 1 (Network Agent) was unacknowledged.</p>
            <p><strong>Assigned Agent:</strong> {agent_name or 'Not assigned'}</p>
            <p><strong>Agent Phone:</strong> {agent_phone or 'Not available'}</p>
        </div>
        
        <h3>Diagnostic Information</h3>
        <div class="details">
            <p><strong>Failure Reason:</strong> {failure_reason.replace('_', ' ').title()}</p>
            <p><strong>Details:</strong> {details}</p>
        </div>
        
        <h3>Action Required</h3>
        <p>1. This requires your immediate attention</p>
        <p>2. Contact the Network Agent if available</p>
        <p>3. Investigate and resolve the issue</p>
        
        <p><a href="{dashboard_url}" class="button">View Dashboard →</a></p>
        
        <div class="footer">
            This is an automated escalation from OIC NetRadar Monitoring System
        </div>
    </div>
</body>
</html>
"""
    
    def build_mass_outage_message(
        self,
        gateway_ip: str,
        affected_count: int,
        branch: str,
        ticket_id: str
    ) -> Dict[str, str]:
        """
        Build message for mass outage (Section 8.4).
        
        For Core Switch/VLAN segment failures, states the number of affected
        downstream devices instead of listing them individually.
        """
        sms_message = (
            f"NetRadar: MASS OUTAGE at {branch}. "
            f"Gateway {gateway_ip} DOWN. "
            f"{affected_count} devices affected. "
            f"Ticket: {ticket_id[:8]}"
        )
        
        email_subject = f"🚨 [NetRadar] MASS OUTAGE: {branch} - Gateway {gateway_ip} DOWN"
        email_body = f"""
================================================================================
🚨 NetRadar MASS OUTAGE ALERT
================================================================================

Location: {branch}
Gateway: {gateway_ip}
Status: DOWN
Affected Devices: {affected_count} devices

-------------------------------------------------------------------------------
DETAILS
-------------------------------------------------------------------------------

The gateway/router at {branch} is DOWN. This affects ALL devices in this segment.

DO NOT send individual alerts for downstream devices - this is a single,
coordinated response situation.

-------------------------------------------------------------------------------
ACTION REQUIRED
-------------------------------------------------------------------------------

1. Investigate gateway/router connectivity
2. Check power and network links at {branch}
3. Coordinate with local IT staff if needed

Ticket ID: {ticket_id}
Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}

================================================================================
This is an automated alert from OIC NetRadar Monitoring System
"""
        
        return {
            "sms": sms_message,
            "email_subject": email_subject,
            "email_body": email_body
        }