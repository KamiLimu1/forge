"""Email service for sending notifications."""

import logging
from typing import Any

import resend

from forge.core.config import settings

logger = logging.getLogger(__name__)


def _get_resend_client() -> bool:
    """Initialize Resend client if API key is configured."""
    if settings.RESEND_API_KEY:
        resend.api_key = settings.RESEND_API_KEY
        return True
    return False


async def send_email(
    to: str | list[str],
    subject: str,
    html: str,
    text: str | None = None,
) -> dict[str, Any] | None:
    """Send an email using Resend.

    Args:
        to: Recipient email address(es).
        subject: Email subject.
        html: HTML body content.
        text: Optional plain text body.

    Returns:
        Resend response dict or None if email service not configured.
    """
    if not _get_resend_client():
        logger.warning("Email service not configured, skipping email to %s", to)
        return None

    try:
        params: resend.Emails.SendParams = {
            "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM_ADDRESS}>",
            "to": [to] if isinstance(to, str) else to,
            "subject": subject,
            "html": html,
        }
        if text:
            params["text"] = text

        response = resend.Emails.send(params)
        logger.info("Email sent successfully to %s", to)
        return response
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        raise


async def send_invitation_email(
    to: str,
    first_name: str,
    invitation_token: str,
) -> dict[str, Any] | None:
    """Send an invitation email to a new user.

    Args:
        to: Recipient email address.
        first_name: Recipient's first name.
        invitation_token: The invitation token.

    Returns:
        Resend response or None if email service not configured.
    """
    activation_url = f"{settings.FRONTEND_URL}/activate?token={invitation_token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Welcome to KamiLimu Forge</h1>
        </div>
        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
            <p>Hi {first_name},</p>
            <p>You have been invited to join the KamiLimu Forge platform. Click the button below to activate your account and set your password.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{activation_url}" style="background: #667eea; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">Activate Account</a>
            </div>
            <p style="color: #666; font-size: 14px;">This invitation link will expire in {settings.INVITATION_TOKEN_EXPIRE_DAYS} days.</p>
            <p style="color: #666; font-size: 14px;">If you didn't expect this invitation, you can safely ignore this email.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #999; font-size: 12px;">KamiLimu - Forging the next generation of tech professionals</p>
        </div>
    </body>
    </html>
    """

    text = f"""
    Welcome to KamiLimu Forge

    Hi {first_name},

    You have been invited to join the KamiLimu Forge platform.

    Click the link below to activate your account and set your password:
    {activation_url}

    This invitation link will expire in {settings.INVITATION_TOKEN_EXPIRE_DAYS} days.

    If you didn't expect this invitation, you can safely ignore this email.

    --
    KamiLimu - Forging the next generation of tech professionals
    """

    return await send_email(
        to=to,
        subject="You're Invited to KamiLimu Forge",
        html=html,
        text=text,
    )


async def send_password_reset_email(
    to: str,
    first_name: str,
    reset_token: str,
) -> dict[str, Any] | None:
    """Send a password reset email.

    Args:
        to: Recipient email address.
        first_name: Recipient's first name.
        reset_token: The password reset token.

    Returns:
        Resend response or None if email service not configured.
    """
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Password Reset Request</h1>
        </div>
        <div style="background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px;">
            <p>Hi {first_name},</p>
            <p>We received a request to reset your password for your KamiLimu Forge account. Click the button below to set a new password.</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="background: #667eea; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">Reset Password</a>
            </div>
            <p style="color: #666; font-size: 14px;">This link will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hours.</p>
            <p style="color: #666; font-size: 14px;">If you didn't request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #999; font-size: 12px;">KamiLimu - Forging the next generation of tech professionals</p>
        </div>
    </body>
    </html>
    """

    text = f"""
    Password Reset Request

    Hi {first_name},

    We received a request to reset your password for your KamiLimu Forge account.

    Click the link below to set a new password:
    {reset_url}

    This link will expire in {settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS} hours.

    If you didn't request a password reset, you can safely ignore this email.
    Your password will remain unchanged.

    --
    KamiLimu - Forging the next generation of tech professionals
    """

    return await send_email(
        to=to,
        subject="Reset Your KamiLimu Forge Password",
        html=html,
        text=text,
    )
