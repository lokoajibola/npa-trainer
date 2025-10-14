from django.core.management.base import BaseCommand
from training.models import *
from django.contrib.auth.models import User
from datetime import date, timedelta
import random

class Command(BaseCommand):
    help = 'Load sample data for NPA Training Scheduler'

    def handle(self, *args, **options):
        # Create directorates
        directorates = [
            {'name': 'Managing Director', 'code': 'MDI'},
            {'name': 'Engineering & Technical Services', 'code': 'ETS'},
            {'name': 'Marine & Operations', 'code': 'MOP'},
            {'name': 'Finance & Administration', 'code': 'FAD'},
        ]
        
        for data in directorates:
            Directorate.objects.get_or_create(**data)
        
        # Create divisions for each directorate
        divisions_data = {
            'Managing Director': ['Human Resources', 'Procurement', 'Legal Services'],
            'Engineering & Technical Services': ['Engineering', 'Lands & Estate'],
            'Marine & Operations': ['Marine', 'HSE', 'Operations'],
            'Finance & Administration': ['Accounts', 'Budget', 'Audit'],
        }
        
        divisions = {}
        for directorate_name, division_names in divisions_data.items():
            directorate = Directorate.objects.filter(name=directorate_name).first()
            if directorate:
                for div_name in division_names:
                    div, created = Division.objects.get_or_create(
                        name=div_name, 
                        directorate=directorate
                    )
                    divisions[div_name] = div
        
        # Create departments
        departments_data = {
            'Human Resources': ['Recruitment', 'Training & Development', 'Employee Relations'],
            'Procurement': ['Tendering', 'Contract Management', 'Stores'],
            'Engineering': ['Construction', 'Maintenance', 'Planning'],
            'Marine': ['Pilotage', 'Vessel Traffic', 'Berthing'],
            'Accounts': ['Payables', 'Receivables', 'Payroll'],
        }
        
        departments = {}
        for division_name, dept_names in departments_data.items():
            division = Division.objects.filter(name=division_name).first()
            if division:
                for dept_name in dept_names:
                    dept, created = Department.objects.get_or_create(
                        name=dept_name,
                        division=division
                    )
                    departments[dept_name] = dept
        
        # Create users with profiles
        users_data = [
            {'username': 'training_officer', 'role': 'training_staff', 'directorate': 'Managing Director'},
            {'username': 'admin_user', 'role': 'admin', 'directorate': 'Managing Director'},
        ]
        
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={'email': f"{user_data['username']}@npa.gov.ng", 'is_staff': True}
            )
            if created:
                user.set_password('password123')
                user.save()
            
            # FIXED: Use filter().first() instead of get() for directorate
            directorate = Directorate.objects.filter(name=user_data['directorate']).first()
            if directorate:
                UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'role': user_data['role'],
                        'directorate': directorate
                    }
                )
        
        # Create sample staff
        grade_levels = [choice[0] for choice in Staff.GRADE_LEVELS[5:12]]
        first_names = ['John', 'Mary', 'James', 'Elizabeth', 'Michael', 'Sarah', 'David', 'Grace']
        last_names = ['Adeyemi', 'Bello', 'Chukwu', 'Danjuma', 'Eze', 'Falana', 'Garba', 'Hassan']

        # Get all departments
        all_departments = list(Department.objects.all())

        if not all_departments:
            self.stdout.write(self.style.ERROR('No departments found. Please create departments first.'))
            return

        # In the staff creation section of load_sample_data.py
        LOCATIONS = ['LPC', 'TCIPC', 'RP', 'CAL', 'HQ', 'DP', 'ONNE', 'ABJ']

        for i in range(50):
            staff_id = f"NPA{str(i+1).zfill(5)}"
            directorate = random.choice(Directorate.objects.all())
            divisions = directorate.division_set.all()
            
            if not divisions.exists():
                continue
                
            division = random.choice(list(divisions))
            departments = division.department_set.all()
            department = random.choice(list(departments)) if departments.exists() else random.choice(all_departments)
            location = random.choice(LOCATIONS)
            
            Staff.objects.get_or_create(
                staff_id=staff_id,
                defaults={
                    'first_name': random.choice(first_names),
                    'last_name': random.choice(last_names),
                    'grade_level': random.choice(grade_levels),
                    'directorate': directorate,
                    'division': division,
                    'department': department,
                    'location': location,
                    'date_joined': date.today() - timedelta(days=random.randint(365, 3650)),
                    'training_count': random.randint(0, 10)
                }
            )