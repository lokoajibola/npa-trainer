from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db.models import Q  # Add this import
import hashlib
from django.conf import settings


class Directorate(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10)
    
    def __str__(self):
        return self.name

class Division(models.Model):
    name = models.CharField(max_length=200)
    directorate = models.ForeignKey(Directorate, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name

class Department(models.Model):
    name = models.CharField(max_length=200)
    division = models.ForeignKey(Division, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name

class Staff(models.Model):
    GRADE_LEVELS = [
        ('GL_04', 'GL 04'),
        ('GL_06', 'GL 06'),
        ('GL_07', 'GL 07'),
        ('GL_08', 'GL 08'),
        ('GL_09', 'GL 09'),
        ('GL_10', 'GL 10'),
        ('GL_12', 'GL 12'),
        ('GL_13', 'GL 13'),
        ('GL_14', 'GL 14'),
        ('GL_15', 'GL 15'),
        ('GL_16', 'GL 16'),
    ]
    
    LOCATION_CHOICES = [
        ('ALL', 'All'),
        ('LPC', 'LPC'),
        ('TCIPC', 'TCIPC'),
        ('RP', 'RP'),
        ('CAL', 'CAL'),
        ('HQ', 'HQ'),
        ('DP', 'DP'),
        ('ONNE', 'ONNE'),
        ('ABJ', 'ABJ'),
    ]
    
    staff_id = models.CharField(max_length=20, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    grade_level = models.CharField(max_length=10, choices=GRADE_LEVELS)
    directorate = models.ForeignKey(Directorate, on_delete=models.CASCADE)
    division = models.ForeignKey(Division, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    location = models.CharField(max_length=10, choices=LOCATION_CHOICES, default='HQ')
    date_joined = models.DateField()
    training_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def years_of_service(self):
        from datetime import date
        today = date.today()
        return today.year - self.date_joined.year
    
    def __str__(self):
        return f"{self.staff_id} - {self.first_name} {self.last_name}"

class TrainingProgram(models.Model):
    title = models.CharField(max_length=300)
    training_coordinator = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        limit_choices_to={'userprofile__role': 'training_staff'},
        related_name='coordinated_trainings',
        null=True,  # Allow null initially
        blank=True  # Allow blank initially
    )
    training_consultant = models.CharField(
        max_length=200, 
        blank=True,  # Allow blank initially
        null=True,   # Allow null initially
        help_text="Name of training consultant/facilitator"
    )
    consultant_info = models.TextField(
        blank=True,  # Allow blank initially
        null=True,   # Allow null initially
        help_text="Consultant qualifications and experience"
    )
    remarks = models.TextField(
        blank=True, 
        default='',
        help_text="Additional notes or special instructions"
    )
    start_date = models.DateField()
    end_date = models.DateField()
    venue = models.CharField(max_length=200)
    capacity = models.IntegerField(default=25)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class TrainingSelectionCriteria(models.Model):
    training = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE)  # Changed from OneToOne to ForeignKey
    grade_levels = models.JSONField()  # List of selected grade levels
    directorates = models.ManyToManyField(Directorate)
    divisions = models.ManyToManyField(Division)
    departments = models.ManyToManyField(Department)
    locations = models.JSONField(default=list)  # List of selected locations
    max_previous_trainings = models.IntegerField(default=3)
    min_years_of_service = models.IntegerField(default=0)
    max_years_of_service = models.IntegerField(default=35)
    created_at = models.DateTimeField(auto_now_add=True)  # Add timestamp
    is_active = models.BooleanField(default=True)  # Track active criteria
    
    class Meta:
        ordering = ['-created_at']  # Show latest first
    
    def __str__(self):
        return f"Criteria for {self.training.title} ({self.created_at})"

class TrainingNomination(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted for Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    training = models.ForeignKey(TrainingProgram, on_delete=models.CASCADE)
    criteria = models.ForeignKey(TrainingSelectionCriteria, on_delete=models.CASCADE)  # This stays as ForeignKey
    selected_staff = models.ManyToManyField(Staff, through='NominationItem')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_nominations')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    print_hash = models.CharField(max_length=64, blank=True, null=True)
    printed_at = models.DateTimeField(null=True, blank=True)
    printed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='printed_nominations')
    
    def generate_print_hash(self):
        """Generate a unique hash for this nomination to prevent tampering"""
        data_string = f"""
        {self.id}
        {self.training.title}
        {self.training.start_date}
        {self.training.end_date}
        {self.status}
        {self.approved_at}
        {''.join(str(staff.id) for staff in self.selected_staff.all().order_by('staff_id'))}
        {settings.SECRET_KEY}
        """
        return hashlib.sha256(data_string.encode()).hexdigest()
    
    def verify_print_hash(self):
        """Verify if the current data matches the stored hash"""
        if not self.print_hash:
            return False
        return self.generate_print_hash() == self.print_hash
    
    def __str__(self):
        return f"Nomination for {self.training.title}"

class NominationItem(models.Model):
    nomination = models.ForeignKey(TrainingNomination, on_delete=models.CASCADE)
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE)
    selected_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['nomination', 'staff']

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('training_staff', 'Training Staff'),
        ('admin', 'Administrator'),
        ('admin_officer', 'Admin Officer'),  # New role
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    directorate = models.ForeignKey(Directorate, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
class NominalRollUpload(models.Model):
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    records_processed = models.IntegerField()
    created_count = models.IntegerField()
    updated_count = models.IntegerField()
    error_count = models.IntegerField()
    file_name = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"Upload {self.uploaded_at.strftime('%Y-%m-%d %H:%M')} by {self.uploaded_by.username}"
    
class NominationAuditLog(models.Model):
    ACTION_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('staff_added', 'Staff Added'),
        ('staff_removed', 'Staff Removed'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('printed', 'Printed'),
    ]
    
    nomination = models.ForeignKey(TrainingNomination, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.get_action_display()} by {self.user.username} on {self.timestamp}"