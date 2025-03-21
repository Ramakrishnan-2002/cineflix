from fastapi import APIRouter, HTTPException, status,  BackgroundTasks
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from ..schemas import ForgotEmail, ResetPassword
from ..mailer import mail, create_message
from ..models import User
from ..utils import hash as hash_password
import secrets

router = APIRouter(tags=['forgot_password'])


SECRET_KEY = secrets.token_hex(32)
serializer = URLSafeTimedSerializer(SECRET_KEY)

@router.post("/forgot_val")
async def send_reset_email(
    emails: ForgotEmail, 
    background_tasks: BackgroundTasks
):
    user = await User.find_one(User.email == emails.email)
 
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    try:
        # Generate a reset token valid for 1 hour
        token = serializer.dumps(user.email, salt="password-reset-salt")
        reset_url = f"https://cineflix-production.up.railway.app/reset-password?token={token}"
        html = f"""
        <p>Hello {user.name},</p>
        <p>Click the link below to reset your password:</p>
        <a href="{reset_url}">RESET URL</a>
        <p>This link will expire in 1 hour.</p>
        <h3>Happy Day !!!</h3>
        """
        subject = "Password Reset Request"

        # Use BackgroundTasks to send the email
        background_tasks.add_task(
            send_email_task,
            recipients=[emails.email],
            subject=subject,
            body=html
        )

        return {"message": "Password reset link has been sent to your email!"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to send email: {e}")

async def send_email_task(recipients: list, subject: str, body: str):
    """Background task to send an email."""
    message = create_message(recipients=recipients, subject=subject, body=body)
   
    await mail.send_message(message)


@router.post("/reset-password")
async def reset_password(data: ResetPassword):
    try:
        email = serializer.loads(data.token, salt="password-reset-salt", max_age=3600)  # 1 hour
        user = await User.find_one(User.email == email)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        # Hash the new password and save it
        user.password = hash_password(data.new_password)
        
        await user.save()
        return {"message": "Password has been reset successfully!"}
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to reset password: {e}")
    
@router.get("/logout")
async def redirect_to_login():
    redirect_response=RedirectResponse(url="/",status_code=status.HTTP_302_FOUND)
    redirect_response.delete_cookie(key="access_token")
    return redirect_response
