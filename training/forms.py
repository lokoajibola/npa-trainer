from django import forms
from .models import *
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Row, Column, Div, HTML
import pandas as pd
from django.core.exceptions import ValidationError

class TrainingProgramForm(forms.ModelForm):
    class Meta:
        model = TrainingProgram
        fields = ['title', 'description', 'start_date', 'end_date', 'venue', 'capacity']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('title', css_class='form-group col-md-12'),
                css_class='form-row'
            ),
            'description',
            Row(
                Column('start_date', css_class='form-group col-md-6'),
                Column('end_date', css_class='form-group col-md-6'),
                css_class='form-row'
            ),
            Row(
                Column('venue', css_class='form-group col-md-6'),
                Column('capacity', css_class='form-group col-md-6'),
                css_class='form-row'
            ),
            Submit('submit', 'Create Training Program', css_class='btn-primary')
        )

class SelectionCriteriaForm(forms.ModelForm):
    grade_level_from = forms.ChoiceField(
        choices=Staff.GRADE_LEVELS,
        label='Grade Level From',
        required=False
    )
    grade_level_to = forms.ChoiceField(
        choices=Staff.GRADE_LEVELS,
        label='Grade Level To',
        required=False
    )
    max_years_service_left = forms.IntegerField(
        label='Maximum Years of Service Left',
        initial=34,
        min_value=0,
        max_value=35
    )
    locations = forms.MultipleChoiceField(
        choices=Staff.LOCATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='Locations',
        required=False,
        # initial=['ALL']  # Default to 'All'
    )
    
    class Meta:
        model = TrainingSelectionCriteria
        fields = ['directorates', 'divisions', 'departments', 'max_previous_trainings']
        widgets = {
            'directorates': forms.CheckboxSelectMultiple(),
            'divisions': forms.CheckboxSelectMultiple(),
            'departments': forms.CheckboxSelectMultiple(),
            'max_previous_trainings': forms.NumberInput(attrs={'value': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default value for max_previous_trainings
        self.fields['max_previous_trainings'].initial = 3
        
        # Set initial locations to include 'ALL'
        self.fields['locations'].initial = ['ALL']
    
    def clean(self):
        cleaned_data = super().clean()
        grade_level_from = cleaned_data.get('grade_level_from')
        grade_level_to = cleaned_data.get('grade_level_to')
        
        if grade_level_from and grade_level_to:
            # Convert grade levels to numerical values for comparison
            grade_values = {grade[0]: i for i, grade in enumerate(Staff.GRADE_LEVELS)}
            if grade_values[grade_level_from] > grade_values[grade_level_to]:
                raise forms.ValidationError("'Grade Level From' cannot be higher than 'Grade Level To'")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set grade_levels based on range
        grade_level_from = self.cleaned_data.get('grade_level_from')
        grade_level_to = self.cleaned_data.get('grade_level_to')
        
        if grade_level_from and grade_level_to:
            grade_values = {grade[0]: i for i, grade in enumerate(Staff.GRADE_LEVELS)}
            start_idx = grade_values[grade_level_from]
            end_idx = grade_values[grade_level_to]
            
            grade_levels = [Staff.GRADE_LEVELS[i][0] for i in range(start_idx, end_idx + 1)]
            instance.grade_levels = grade_levels
        
        # Set locations
        locations = self.cleaned_data.get('locations', [])
        instance.locations = locations
        
        # Set years of service criteria based on max years left
        max_years_left = self.cleaned_data.get('max_years_service_left', 34)
        instance.min_years_of_service = 0  # Always 0 since we're calculating years left
        instance.max_years_of_service = 35 - max_years_left  # Assuming retirement at 35 years
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance

class NominationApprovalForm(forms.ModelForm):
    class Meta:
        model = TrainingNomination
        fields = ['status']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            ('approved', 'Approve'),
            ('rejected', 'Reject'),
        ]

class NominalRollUploadForm(forms.Form):
    excel_file = forms.FileField(
        label='Select Excel File',
        help_text='Upload Excel file with staff data. Required columns: Personal Number, Name, GL Range, Directorate, Division, Department, Location, Years of Service Left'
    )
    
    def clean_excel_file(self):
        excel_file = self.cleaned_data['excel_file']
        
        # Check file extension
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            raise ValidationError('Please upload a valid Excel file (.xlsx or .xls)')
        
        # Check file size (max 10MB)
        if excel_file.size > 10 * 1024 * 1024:
            raise ValidationError('File size should not exceed 10MB')
        
        return excel_file
    
    def process_excel_file(self):
        """Process the uploaded Excel file and return DataFrame"""
        excel_file = self.cleaned_data['excel_file']
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Check required columns
            required_columns = ['Personal Number', 'Name', 'GL Range', 'Directorate', 
                              'Division', 'Department', 'Location', 'Years of Service Left']
            
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValidationError(f'Missing required columns: {", ".join(missing_columns)}')
            
            return df
            
        except Exception as e:
            raise ValidationError(f'Error reading Excel file: {str(e)}')