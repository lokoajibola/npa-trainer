from django.contrib import admin
from .models import *
from django.urls import path 

@admin.register(Directorate)
class DirectorateAdmin(admin.ModelAdmin):
    list_display = ['name', 'code']
    search_fields = ['name', 'code']

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ['name', 'directorate']
    list_filter = ['directorate']
    search_fields = ['name']

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'division', 'directorate']
    list_filter = ['division__directorate', 'division']
    search_fields = ['name']
    
    def directorate(self, obj):
        return obj.division.directorate

@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ['staff_id', 'first_name', 'last_name', 'grade_level', 'department', 'years_of_service', 'training_count']
    list_filter = ['grade_level', 'directorate', 'division', 'department']
    search_fields = ['staff_id', 'first_name', 'last_name']
    readonly_fields = ['training_count']
    
    actions = ['delete_all_staff']

    def delete_all_staff(self, request, queryset):
        # Redirect to confirmation page
        selected = queryset.values_list('pk', flat=True)
        return HttpResponseRedirect(
            f"/admin/training/staff/reset-confirm/?ids={','.join(str(pk) for pk in selected)}"
        )
    delete_all_staff.short_description = "Delete all staff records"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'reset-confirm/',
                self.admin_site.admin_view(self.reset_confirm_view),
                name='staff_reset_confirm',
            ),
            path(
                'reset-execute/',
                self.admin_site.admin_view(self.reset_execute_view),
                name='staff_reset_execute',
            ),
        ]
        return custom_urls + urls

    def reset_confirm_view(self, request):
        staff_count = Staff.objects.count()
        upload_count = NominalRollUpload.objects.count()
        
        context = {
            'title': 'Confirm Nominal Roll Reset',
            'staff_count': staff_count,
            'upload_count': upload_count,
        }
        return render(request, 'admin/staff_reset_confirm.html', context)

    def reset_execute_view(self, request):
        if request.method == 'POST':
            keep_structure = 'keep_structure' in request.POST
            
            # Delete data
            staff_count = Staff.objects.count()
            upload_count = NominalRollUpload.objects.count()
            
            Staff.objects.all().delete()
            NominalRollUpload.objects.all().delete()
            
            if not keep_structure:
                Department.objects.all().delete()
                Division.objects.all().delete()
                Directorate.objects.all().delete()
            
            self.message_user(
                request, 
                f"Successfully deleted {staff_count} staff records and {upload_count} upload records.",
                messages.SUCCESS
            )
            return HttpResponseRedirect("/admin/training/staff/")
        
        return HttpResponseRedirect("/admin/training/staff/")

@admin.register(TrainingProgram)
class TrainingProgramAdmin(admin.ModelAdmin):
    list_display = ['title', 'start_date', 'end_date', 'venue', 'capacity', 'created_by']
    list_filter = ['start_date', 'venue']
    search_fields = ['title', 'description']

@admin.register(TrainingSelectionCriteria)
class TrainingSelectionCriteriaAdmin(admin.ModelAdmin):
    list_display = ['training', 'max_previous_trainings', 'min_years_of_service']
    filter_horizontal = ['directorates', 'divisions', 'departments']

@admin.register(TrainingNomination)
class TrainingNominationAdmin(admin.ModelAdmin):
    list_display = ['training', 'status', 'created_by', 'created_at', 'approved_by']
    list_filter = ['status', 'created_at']
    readonly_fields = ['created_at', 'approved_at']

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'directorate']
    list_filter = ['role', 'directorate']