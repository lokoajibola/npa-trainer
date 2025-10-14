from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserProfile, Directorate

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Get first directorate or create a default one
        directorate = Directorate.objects.first()
        if not directorate:
            directorate = Directorate.objects.create(
                name='Corporate Services',
                code='CSD'
            )
        
        UserProfile.objects.create(
            user=instance,
            role='training_staff',  # Default role
            directorate=directorate
        )

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    try:
        instance.userprofile.save()
    except UserProfile.DoesNotExist:
        create_user_profile(sender, instance, True, **kwargs)