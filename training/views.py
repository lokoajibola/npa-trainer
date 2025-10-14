from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError
import pandas as pd
from datetime import date
from .models import *
from .forms import TrainingProgramForm, SelectionCriteriaForm, NominationApprovalForm, NominalRollUploadForm
from .utils import is_training_staff, is_admin, log_nomination_action, get_client_ip
from django.contrib.auth import logout
from django.shortcuts import redirect
import json

@csrf_exempt
def search_staff(request):
    """API endpoint to search staff by personal number or name"""
    query = request.GET.get('q', '').strip()
    nomination_id = request.GET.get('nomination_id')
    
    if not query or len(query) < 2:
        return JsonResponse({'staff': []})
    
    # Get the nomination to check already nominated staff
    nomination = get_object_or_404(TrainingNomination, id=nomination_id)
    nominated_staff_ids = list(nomination.selected_staff.values_list('id', flat=True))
    
    # Search in staff database
    staff_query = Staff.objects.filter(
        Q(staff_id__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query)
    ).exclude(id__in=nominated_staff_ids)  # Exclude already nominated staff
    
    staff_list = []
    for staff in staff_query[:10]:  # Limit to 10 results
        staff_list.append({
            'id': staff.id,
            'staff_id': staff.staff_id,
            'first_name': staff.first_name,
            'last_name': staff.last_name,
            'grade_level': staff.get_grade_level_display(),
            'directorate': str(staff.directorate),
            'division': str(staff.division),
            'department': str(staff.department) if staff.department else '',
            'location': staff.get_location_display(),
            'training_count': staff.training_count,
            'years_of_service': staff.years_of_service(),
        })
    
    return JsonResponse({'staff': staff_list})

@csrf_exempt
def add_staff_to_nomination(request):
    """API endpoint to add staff to nomination"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            staff_id = data.get('staff_id')
            nomination_id = data.get('nomination_id')
            
            staff = get_object_or_404(Staff, id=staff_id)
            nomination = get_object_or_404(TrainingNomination, id=nomination_id)
            
            # Check permissions - allow both creator (for draft/submitted) and admin users
            user_profile = UserProfile.objects.get(user=request.user)
            if nomination.created_by != request.user and user_profile.role not in ['admin', 'admin_officer']:
                return JsonResponse({'success': False, 'error': 'You do not have permission to modify this nomination'})
            
            # Allow modifications for draft and submitted status (before approval)
            if nomination.status not in ['draft', 'submitted'] and nomination.created_by == request.user:
                return JsonResponse({'success': False, 'error': 'Cannot modify approved or rejected nominations'})
            
            # Check if staff is already nominated
            if nomination.selected_staff.filter(id=staff_id).exists():
                return JsonResponse({'success': False, 'error': 'Staff is already nominated'})
            
            # Check training capacity
            if nomination.selected_staff.count() >= nomination.training.capacity:
                return JsonResponse({'success': False, 'error': f'Training capacity ({nomination.training.capacity}) reached'})
            
            # Add staff to nomination
            NominationItem.objects.create(nomination=nomination, staff=staff)
            
            # LOG THE ACTION
            log_nomination_action(
                nomination, 
                request.user, 
                'staff_added', 
                f'Added staff {staff.staff_id} - {staff.first_name} {staff.last_name}',
                request
            )
            
            return JsonResponse({
                'success': True,
                'staff': {
                    'id': staff.id,
                    'staff_id': staff.staff_id,
                    'first_name': staff.first_name,
                    'last_name': staff.last_name,
                    'grade_level_display': staff.get_grade_level_display(),
                    'directorate': str(staff.directorate),
                    'division': str(staff.division),
                    'department': str(staff.department) if staff.department else '',
                    'location_display': staff.get_location_display(),
                    'training_count': staff.training_count,
                    'years_of_service': staff.years_of_service(),
                }
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@csrf_exempt
def remove_staff_from_nomination(request):
    """API endpoint to remove staff from nomination"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            staff_id = data.get('staff_id')
            nomination_id = data.get('nomination_id')
            
            nomination = get_object_or_404(TrainingNomination, id=nomination_id)
            staff = get_object_or_404(Staff, id=staff_id)
            
            # Check permissions - allow both creator (for draft/submitted) and admin users
            user_profile = UserProfile.objects.get(user=request.user)
            if nomination.created_by != request.user and user_profile.role not in ['admin', 'admin_officer']:
                return JsonResponse({'success': False, 'error': 'You do not have permission to modify this nomination'})
            
            # Allow modifications for draft and submitted status (before approval)
            if nomination.status not in ['draft', 'submitted'] and nomination.created_by == request.user:
                return JsonResponse({'success': False, 'error': 'Cannot modify approved or rejected nominations'})
            
            # Remove staff from nomination
            NominationItem.objects.filter(nomination=nomination, staff_id=staff_id).delete()
            
            # LOG THE ACTION
            log_nomination_action(
                nomination, 
                request.user, 
                'staff_removed', 
                f'Removed staff {staff.staff_id} - {staff.first_name} {staff.last_name}',
                request
            )
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def dashboard(request):
    # Get or create user profile
    user_profile, created = UserProfile.objects.get_or_create(
        user=request.user,
        defaults={
            'role': 'training_staff',  # Default role
            'directorate': Directorate.objects.first()  # Assign first directorate as default
        }
    )
    
    if user_profile.role == 'training_staff':
        nominations = TrainingNomination.objects.filter(created_by=request.user)
    else:
        nominations = TrainingNomination.objects.all()
    
    context = {
        'user_profile': user_profile,
        'nominations': nominations,
        'pending_approvals': TrainingNomination.objects.filter(status='submitted').count() if user_profile.role == 'admin' else 0
    }
    return render(request, 'training/dashboard.html', context)

@login_required
@user_passes_test(lambda u: is_training_staff(u) or is_admin_officer(u))
def create_training_program(request):
    if request.method == 'POST':
        form = TrainingProgramForm(request.POST)
        if form.is_valid():
            training = form.save(commit=False)
            training.created_by = request.user
            training.save()
            messages.success(request, 'Training program created successfully!')
            return redirect('set_selection_criteria', training_id=training.id)
    else:
        form = TrainingProgramForm()
    
    return render(request, 'training/create_training.html', {'form': form})

@login_required
@user_passes_test(is_training_staff)
def set_selection_criteria(request, training_id):
    training = get_object_or_404(TrainingProgram, id=training_id, created_by=request.user)
    
    if request.method == 'POST':
        form = SelectionCriteriaForm(request.POST)
        if form.is_valid():
            criteria = form.save(commit=False)
            criteria.training = training
            criteria.save()
            form.save_m2m()
            
            # Generate nomination list based on criteria
            nomination = generate_nomination_list(training, criteria, request.user)
            messages.success(request, 'Selection criteria set and nomination list generated!')
            return redirect('review_nomination', nomination_id=nomination.id)
    else:
        form = SelectionCriteriaForm()
    
    return render(request, 'training/set_criteria.html', {
        'form': form,
        'training': training
    })

def generate_nomination_list(training, criteria, user):
    # Start with all staff
    staff_query = Staff.objects.all()
    
    # Filter by grade levels
    if criteria.grade_levels:
        staff_query = staff_query.filter(grade_level__in=criteria.grade_levels)
    
    # Filter by locations
    if criteria.locations and 'ALL' not in criteria.locations:
        staff_query = staff_query.filter(location__in=criteria.locations)
    
    # Filter by directorates
    if criteria.directorates.exists():
        staff_query = staff_query.filter(directorate__in=criteria.directorates.all())
    
    # Filter by divisions
    if criteria.divisions.exists():
        staff_query = staff_query.filter(division__in=criteria.divisions.all())
    
    # Filter by departments
    if criteria.departments.exists():
        staff_query = staff_query.filter(department__in=criteria.departments.all())
    
    # Filter by training count
    staff_query = staff_query.filter(training_count__lte=criteria.max_previous_trainings)
    
    # Filter by years of service left (retirement at 35 years)
    from datetime import date
    current_year = date.today().year
    max_service_years = criteria.max_years_of_service
    
    staff_query = staff_query.filter(
        date_joined__year__lte=current_year - max_service_years
    )
    
    # Create nomination
    nomination = TrainingNomination.objects.create(
        training=training,
        criteria=criteria,
        created_by=user,
        status='draft'
    )
    
    # Add selected staff (limit to capacity)
    selected_staff = staff_query[:training.capacity]
    for staff in selected_staff:
        NominationItem.objects.create(nomination=nomination, staff=staff)
    
    return nomination

@login_required
@user_passes_test(is_training_staff)
def review_nomination(request, nomination_id):
    nomination = get_object_or_404(TrainingNomination, id=nomination_id, created_by=request.user)
    
    # Allow editing for both draft and submitted status (before approval)
    if nomination.status not in ['draft', 'submitted']:
        messages.error(request, 'You can only edit nominations that are in draft or submitted status.')
        return redirect('dashboard')
    
    if request.method == 'POST' and 'submit_approval' in request.POST:
        nomination.status = 'submitted'
        nomination.save()
        
        # Log the submission
        log_nomination_action(
            nomination, 
            request.user, 
            'updated', 
            'Nomination submitted for approval',
            request
        )
        
        messages.success(request, 'Nomination submitted for approval!')
        return redirect('dashboard')
    
    return render(request, 'training/review_nomination.html', {
        'nomination': nomination
    })
    
# New view for admin officers to review and edit nominations
@login_required
@user_passes_test(is_admin)
def admin_review_nomination(request, nomination_id):
    nomination = get_object_or_404(TrainingNomination, id=nomination_id)
    
    if request.method == 'POST':
        if 'approve' in request.POST:
            nomination.status = 'approved'
            nomination.approved_by = request.user
            nomination.approved_at = timezone.now()
            nomination.save()
            
            # LOG THE ACTION
            log_nomination_action(
                nomination, 
                request.user, 
                'approved', 
                'Nomination approved by admin',
                request
            )
            
            messages.success(request, 'Nomination approved successfully!')
            return redirect('approval_list')
            
        elif 'reject' in request.POST:
            nomination.status = 'rejected'
            nomination.approved_by = request.user
            nomination.approved_at = timezone.now()
            nomination.save()
            
            # LOG THE ACTION
            log_nomination_action(
                nomination, 
                request.user, 
                'rejected', 
                'Nomination rejected by admin',
                request
            )
            
            messages.success(request, 'Nomination rejected!')
            return redirect('approval_list')
    
    return render(request, 'training/admin_review_nomination.html', {
        'nomination': nomination
    })

@login_required
@user_passes_test(is_admin)
def approval_list(request):
    nominations = TrainingNomination.objects.filter(status='submitted')
    return render(request, 'training/approval_list.html', {
        'nominations': nominations
    })

@login_required
@user_passes_test(is_admin)
def approve_nomination(request, nomination_id):
    nomination = get_object_or_404(TrainingNomination, id=nomination_id)
    
    if request.method == 'POST':
        form = NominationApprovalForm(request.POST, instance=nomination)
        if form.is_valid():
            nomination = form.save(commit=False)
            if nomination.status == 'approved':
                nomination.approved_by = request.user
                nomination.approved_at = timezone.now()
                
                # LOG THE ACTION - ADD THIS LINE
                log_nomination_action(
                    nomination, 
                    request.user, 
                    'approved', 
                    'Nomination approved',
                    request
                )
            elif nomination.status == 'rejected':
                # LOG THE ACTION - ADD THIS LINE
                log_nomination_action(
                    nomination, 
                    request.user, 
                    'rejected', 
                    'Nomination rejected',
                    request
                )
                
            nomination.save()
            messages.success(request, f'Nomination {nomination.status}!')
            return redirect('approval_list')
    else:
        form = NominationApprovalForm(instance=nomination)
    
    return render(request, 'training/approve_nomination.html', {
        'nomination': nomination,
        'form': form
    })
@login_required
def print_nomination(request, nomination_id):
    nomination = get_object_or_404(TrainingNomination, id=nomination_id)
    
    # Check permissions
    user_profile = UserProfile.objects.get(user=request.user)
    if user_profile.role == 'training_staff' and nomination.created_by != request.user:
        messages.error(request, 'You can only print your own nominations.')
        return redirect('dashboard')
    
    if nomination.status != 'approved':
        messages.error(request, 'Only approved nominations can be printed.')
        return redirect('dashboard')
    
    # Generate and store print hash if not exists
    if not nomination.print_hash:
        nomination.print_hash = nomination.generate_print_hash()
        nomination.printed_at = timezone.now()
        nomination.printed_by = request.user
        nomination.save()
        
        # LOG THE ACTION
        log_nomination_action(
            nomination, 
            request.user, 
            'printed', 
            'Nomination printed for the first time',
            request
        )
    else:
        # LOG THE ACTION (for re-prints)
        log_nomination_action(
            nomination, 
            request.user, 
            'printed', 
            'Nomination re-printed',
            request
        )
    
    # Get staff sorted by grade level (highest to lowest)
    def get_grade_value(staff):
        try:
            return int(staff.grade_level.replace('GL_', ''))
        except (ValueError, AttributeError):
            return 0
    
    # Get nomination items with staff sorted by grade level
    nomination_items = nomination.nominationitem_set.select_related('staff').all()
    sorted_items = sorted(
        nomination_items,
        key=lambda item: get_grade_value(item.staff),
        reverse=True
    )
    
    # Verify integrity before printing
    if not nomination.verify_print_hash():
        messages.error(request, 'WARNING: This nomination may have been modified after approval. Please contact administrator.')
    
    return render(request, 'training/print_nomination.html', {
        'nomination': nomination,
        'sorted_items': sorted_items,
        'is_tampered': not nomination.verify_print_hash()
    })

@csrf_exempt
def divisions_departments_api(request):
    """API endpoint to get divisions and departments data"""
    divisions_data = {}
    departments_data = {}
    
    # Get all divisions grouped by directorate
    for directorate in Directorate.objects.all():
        divisions = directorate.division_set.all()
        divisions_data[str(directorate.id)] = [
            {'id': div.id, 'name': div.name}
            for div in divisions
        ]
    
    # Get all departments grouped by division
    for division in Division.objects.all():
        departments = division.department_set.all()
        departments_data[str(division.id)] = [
            {'id': dept.id, 'name': dept.name}
            for dept in departments
        ]
    
    return JsonResponse({
        'divisions': divisions_data,
        'departments': departments_data
    })

@login_required
@user_passes_test(is_admin)
def upload_nominal_roll(request):
    if request.method == 'POST':
        form = NominalRollUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                df = form.process_excel_file()
                stats = process_nominal_roll_data(df, request.FILES['excel_file'].name, request.user)
                
                if stats['errors'] == len(df):
                    messages.error(request, 
                        f"All {stats['errors']} records failed to process. Please check:\n"
                        f"1. Column names match exactly: Personal Number, Name, GL Range, Directorate, Division, Department, Location, Years of Service Left\n"
                        f"2. Personal Number and Name are filled\n"
                        f"3. GL Range format is correct (GL04, GL06, GL07, etc.)\n"
                        f"4. Years of Service Left is a number between 0-35\n"
                        f"5. Check server console for specific error details"
                    )
                elif stats['errors'] > 0:
                    messages.warning(request, 
                        f"Nominal roll processed with some errors! "
                        f"Processed: {stats['created']} created, {stats['updated']} updated, "
                        f"{stats['errors']} errors. Check server console for details."
                    )
                else:
                    messages.success(request, 
                        f"Nominal roll uploaded successfully! "
                        f"Processed: {stats['created']} created, {stats['updated']} updated."
                    )
                return redirect('upload_nominal_roll')
                
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error processing file: {str(e)}')
    else:
        form = NominalRollUploadForm()
    
    # Get upload history
    upload_history = NominalRollUpload.objects.all().order_by('-uploaded_at')[:10]
    
    return render(request, 'training/upload_nominal_roll.html', {
        'form': form,
        'upload_history': upload_history
    })

def custom_logout(request):
    logout(request)
    return redirect('login')

def process_nominal_roll_data(df, file_name, user):
    """Process the DataFrame and update staff records"""
    stats = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0}
    
    for index, row in df.iterrows():
        try:
            # Basic data validation
            personal_number = str(row['Personal Number']).strip()
            if not personal_number or personal_number == 'nan':
                stats['errors'] += 1
                continue
                
            name = str(row['Name']).strip()
            if not name or name == 'nan':
                stats['errors'] += 1
                continue
                
            name_parts = name.split(' ', 1)
            if len(name_parts) < 2:
                stats['errors'] += 1
                continue
                
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Grade level processing
            grade_level_raw = str(row['GL Range']).strip()
            if not grade_level_raw or grade_level_raw == 'nan':
                stats['errors'] += 1
                continue
                
            # Convert various GL formats to standard format
            grade_level = grade_level_raw.upper().replace(' ', '_')
            if not grade_level.startswith('GL_'):
                if grade_level.startswith('GL'):
                    grade_level = 'GL_' + grade_level[2:]
                else:
                    grade_level = 'GL_' + grade_level
            
            # Validate grade level
            valid_grade_levels = dict(Staff.GRADE_LEVELS)
            if grade_level not in valid_grade_levels:
                stats['errors'] += 1
                continue
            
            # Directorate processing
            directorate_name = str(row['Directorate']).strip()
            if not directorate_name or directorate_name == 'nan':
                stats['errors'] += 1
                continue
            
            # Division processing
            division_name = str(row['Division']).strip()
            if not division_name or division_name == 'nan':
                stats['errors'] += 1
                continue
            
            # Department processing
            department_name = str(row['Department']).strip()
            if not department_name or department_name == 'nan':
                department_name = ''  # Allow empty departments
            
            # Location processing
            location = str(row['Location']).strip()
            if not location or location == 'nan':
                location = 'HQ'  # Default to HQ
            
            # Validate location
            valid_locations = dict(Staff.LOCATION_CHOICES)
            if location not in valid_locations:
                location = 'HQ'  # Default to HQ if invalid
            
            # Years of service processing
            try:
                years_service_left = int(float(row['Years of Service Left']))
                if years_service_left < 0 or years_service_left > 35:
                    stats['errors'] += 1
                    continue
            except (ValueError, TypeError):
                stats['errors'] += 1
                continue
            
            # Calculate date joined based on years of service left (assuming retirement at 35 years)
            current_year = date.today().year
            years_of_service = 35 - years_service_left
            date_joined = date(current_year - years_of_service, 1, 1)
            
            # Get or create directorate
            directorate, created = Directorate.objects.get_or_create(
                name=directorate_name,
                defaults={'code': directorate_name[:3].upper()}
            )
            
            # Get or create division
            division, created = Division.objects.get_or_create(
                name=division_name,
                directorate=directorate,
                defaults={}
            )
            
            # Get or create department (only if department name is provided)
            department = None
            if department_name:
                department, created = Department.objects.get_or_create(
                    name=department_name,
                    division=division,
                    defaults={}
                )
            
            # Create or update staff
            staff, created = Staff.objects.update_or_create(
                staff_id=personal_number,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'grade_level': grade_level,
                    'directorate': directorate,
                    'division': division,
                    'department': department,
                    'location': location,
                    'date_joined': date_joined,
                    'training_count': 0,  # Reset training count on upload
                }
            )
            
            if created:
                stats['created'] += 1
            else:
                stats['updated'] += 1
                
        except Exception as e:
            stats['errors'] += 1
            print(f"Error processing row {index + 2}: {e}")  # +2 because Excel rows start at 1 and header is row 1
    
    # Create upload record
    NominalRollUpload.objects.create(
        uploaded_by=user,
        records_processed=len(df),
        created_count=stats['created'],
        updated_count=stats['updated'],
        error_count=stats['errors'],
        file_name=file_name
    )
    
    return stats

@login_required
def search_staff_trainings(request):
    """Search for staff and display their training history"""
    query = request.GET.get('q', '').strip()
    staff = None
    training_history_data = []
    staff_list = None
    status_stats = {}
    
    if query and len(query) >= 2:
        # Search for staff by ID or name
        staff_queryset = Staff.objects.filter(
            Q(staff_id__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        ).order_by('staff_id')
        
        # Get count and limited results
        staff_count = staff_queryset.count()
        staff_list = staff_queryset[:10]
        
        # If exactly one result, get the staff object
        if staff_count == 1:
            staff = staff_queryset.first()
            # Get ALL training nominations for this staff (not just approved)
            training_history = NominationItem.objects.filter(
                staff=staff
            ).select_related(
                'nomination__training',
                'nomination__training__created_by',
                'nomination'
            ).order_by('-nomination__training__start_date')
            
            # Initialize status statistics
            status_stats = {
                'approved': 0,
                'submitted': 0,
                'draft': 0,
                'rejected': 0,
                'total': training_history.count()
            }
            
            # Prepare training history data with calculated duration and status
            for item in training_history:
                duration_days = (item.nomination.training.end_date - item.nomination.training.start_date).days + 1
                status = item.nomination.status
                
                # Update status statistics
                if status in status_stats:
                    status_stats[status] += 1
                
                training_history_data.append({
                    'item': item,
                    'duration_days': duration_days,
                    'status': status,
                    'status_display': item.nomination.get_status_display()
                })
    
    return render(request, 'training/staff_training_search.html', {
        'query': query,
        'staff': staff,
        'staff_list': staff_list,
        'training_history_data': training_history_data,
        'status_stats': status_stats
    })

@login_required
@user_passes_test(is_admin)
def verify_nomination(request, nomination_id):
    """Verify the integrity of a nomination"""
    nomination = get_object_or_404(TrainingNomination, id=nomination_id)
    is_valid = nomination.verify_print_hash()
    audit_logs = NominationAuditLog.objects.filter(nomination=nomination).order_by('-timestamp')
    
    return render(request, 'training/verify_nomination.html', {
        'nomination': nomination,
        'is_valid': is_valid,
        'audit_logs': audit_logs
    })
    
@login_required
@user_passes_test(is_admin)
def reset_nominal_roll(request):
    """Reset all nominal roll data"""
    if request.method == 'POST':
        keep_structure = 'keep_structure' in request.POST
        force_all = 'force_all' in request.POST
        
        # Find staff in approved trainings that should be protected
        protected_staff_ids = set()
        if not force_all:
            protected_staff_ids = set(
                NominationItem.objects.filter(
                    nomination__status='approved'
                ).values_list('staff_id', flat=True).distinct()
            )
        
        # Count before deletion
        all_staff_count = Staff.objects.count()
        staff_to_delete_count = all_staff_count - len(protected_staff_ids)
        upload_count = NominalRollUpload.objects.count()
        
        # Delete data
        NominalRollUpload.objects.all().delete()
        
        # Delete staff (preserve those in approved trainings unless forced)
        if force_all:
            deleted_staff_count = Staff.objects.all().delete()[0]
        else:
            staff_to_delete = Staff.objects.exclude(id__in=protected_staff_ids)
            deleted_staff_count = staff_to_delete.delete()[0]
        
        # Handle organizational structure
        dir_count = div_count = dept_count = 0
        if not keep_structure:
            remaining_staff = Staff.objects.count()
            if remaining_staff == 0:
                dept_count = Department.objects.all().delete()[0]
                div_count = Division.objects.all().delete()[0]
                dir_count = Directorate.objects.all().delete()[0]
        
        messages.success(
            request, 
            f"Nominal roll reset successfully! Deleted {deleted_staff_count} staff records and {upload_count} upload records."
            + (f" Also deleted {dir_count} directorates, {div_count} divisions, and {dept_count} departments." if not keep_structure and remaining_staff == 0 else "")
        )
        
        if protected_staff_ids and not force_all:
            messages.info(
                request, 
                f"Preserved {len(protected_staff_ids)} staff members who are part of approved training programs."
            )
            
        return redirect('upload_nominal_roll')
    
    # Get counts for confirmation
    all_staff_count = Staff.objects.count()
    protected_staff_ids = set(
        NominationItem.objects.filter(
            nomination__status='approved'
        ).values_list('staff_id', flat=True).distinct()
    )
    staff_to_delete_count = all_staff_count - len(protected_staff_ids)
    upload_count = NominalRollUpload.objects.count()
    dir_count = Directorate.objects.count()
    div_count = Division.objects.count()
    dept_count = Department.objects.count()
    
    return render(request, 'training/reset_nominal_roll.html', {
        'all_staff_count': all_staff_count,
        'staff_to_delete_count': staff_to_delete_count,
        'protected_staff_count': len(protected_staff_ids),
        'upload_count': upload_count,
        'dir_count': dir_count,
        'div_count': div_count,
        'dept_count': dept_count,
    })