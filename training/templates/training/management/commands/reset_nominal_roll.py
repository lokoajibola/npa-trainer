from django.core.management.base import BaseCommand
from training.models import Staff, Directorate, Division, Department, NominalRollUpload, TrainingNomination, NominationItem
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Delete all nominal roll data and reset to empty state'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-structure',
            action='store_true',
            help='Keep directorates, divisions, and departments (only delete staff)',
        )
        parser.add_argument(
            '--force-all',
            action='store_true',
            help='Force delete ALL staff including those in approved trainings (not recommended)',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        keep_structure = options['keep_structure']
        force_all = options['force_all']
        confirm = options['confirm']
        
        # Count records
        all_staff_count = Staff.objects.count()
        
        # Find staff in approved trainings that should be protected
        protected_staff_ids = set()
        if not force_all:
            protected_staff_ids = set(
                NominationItem.objects.filter(
                    nomination__status='approved'
                ).values_list('staff_id', flat=True).distinct()
            )
        
        staff_to_delete_count = all_staff_count - len(protected_staff_ids)
        directorate_count = Directorate.objects.count()
        division_count = Division.objects.count()
        department_count = Department.objects.count()
        upload_count = NominalRollUpload.objects.count()
        
        if not confirm:
            self.stdout.write(self.style.WARNING(
                f"This will delete:\n"
                f"  - {staff_to_delete_count} staff records (excluding {len(protected_staff_ids)} staff in approved trainings)\n"
                f"  - {upload_count} upload history records\n"
            ))
            
            if not keep_structure:
                self.stdout.write(self.style.WARNING(
                    f"  - {directorate_count} directorates\n"
                    f"  - {division_count} divisions\n"
                    f"  - {department_count} departments\n"
                ))
            
            if protected_staff_ids and not force_all:
                self.stdout.write(self.style.NOTICE(
                    f"NOTE: {len(protected_staff_ids)} staff members in approved trainings will be preserved.\n"
                    f"Use --force-all to delete ALL staff including those in approved trainings."
                ))
            
            confirmation = input("Are you sure you want to continue? (yes/no): ")
            if confirmation.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Operation cancelled.'))
                return
        
        # Delete data
        self.stdout.write("Deleting data...")
        
        # Delete upload history
        NominalRollUpload.objects.all().delete()
        
        # Delete staff (preserve those in approved trainings unless forced)
        if force_all:
            # Delete all staff
            deleted_staff_count = Staff.objects.all().delete()[0]
        else:
            # Only delete staff not in approved trainings
            staff_to_delete = Staff.objects.exclude(id__in=protected_staff_ids)
            deleted_staff_count = staff_to_delete.delete()[0]
        
        if not keep_structure:
            # Only delete organizational structure if no staff remain
            remaining_staff = Staff.objects.count()
            if remaining_staff == 0:
                Department.objects.all().delete()
                Division.objects.all().delete()
                Directorate.objects.all().delete()
            else:
                self.stdout.write(self.style.NOTICE(
                    f"Preserved organizational structure because {remaining_staff} staff members remain in approved trainings."
                ))
        
        self.stdout.write(self.style.SUCCESS(
            f"Successfully reset nominal roll data!\n"
            f"Deleted: {deleted_staff_count} staff, {upload_count} uploads"
            + (f", {directorate_count} directorates, {division_count} divisions, {department_count} departments" if not keep_structure and remaining_staff == 0 else "")
        ))
        
        if protected_staff_ids and not force_all:
            self.stdout.write(self.style.SUCCESS(
                f"Preserved {len(protected_staff_ids)} staff members in approved trainings."
            ))