from django.contrib.auth.models import User
from .models import NominationAuditLog, UserProfile

def is_training_staff(user):
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.role in ['training_staff', 'admin_officer', 'admin']
    except UserProfile.DoesNotExist:
        return False

def is_admin(user):
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.role in ['admin', 'admin_officer']
    except UserProfile.DoesNotExist:
        return False

def is_admin_officer(user):
    try:
        profile = UserProfile.objects.get(user=user)
        return profile.role == 'admin_officer'
    except UserProfile.DoesNotExist:
        return False

def log_nomination_action(nomination, user, action, description, request=None):
    """Log an action performed on a nomination"""
    ip_address = None
    if request:
        ip_address = get_client_ip(request)
    
    NominationAuditLog.objects.create(
        nomination=nomination,
        user=user,
        action=action,
        description=description,
        ip_address=ip_address
    )

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip