from django import forms

from queues.models import Counter, Service, SystemSettings


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            "name",
            "code",
            "description",
            "avg_service_minutes",
            "daily_token_limit",
            "is_active",
        ]
        labels = {
            "code": "Token prefix",
            "avg_service_minutes": "Expected minutes per person",
            "daily_token_limit": "Tokens per day",
            "is_active": "Accepting tokens",
        }
        help_texts = {
            "daily_token_limit": "0 means no limit.",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "field-input", "placeholder": "Fee payment"}),
            "code": forms.TextInput(
                attrs={"class": "field-input field-mono", "placeholder": "FEE", "maxlength": 3}
            ),
            "description": forms.TextInput(
                attrs={"class": "field-input", "placeholder": "Pay semester fees and collect the receipt"}
            ),
            "avg_service_minutes": forms.NumberInput(attrs={"class": "field-input", "min": 1}),
            "daily_token_limit": forms.NumberInput(attrs={"class": "field-input", "min": 0}),
        }

    def clean_code(self):
        code = self.cleaned_data["code"].strip().upper()
        if not code.isalnum():
            raise forms.ValidationError("Use letters and digits only.")
        return code


class CounterForm(forms.ModelForm):
    class Meta:
        model = Counter
        fields = ["name", "code", "location", "services", "assigned_staff", "status", "is_active"]
        labels = {
            "code": "Board code",
            "assigned_staff": "Staff on duty",
            "is_active": "Show on the board",
        }
        widgets = {
            "name": forms.TextInput(attrs={"class": "field-input", "placeholder": "Front desk"}),
            "code": forms.TextInput(
                attrs={"class": "field-input field-mono", "placeholder": "C1", "maxlength": 12}
            ),
            "location": forms.TextInput(
                attrs={"class": "field-input", "placeholder": "Ground floor, room 4"}
            ),
            "services": forms.CheckboxSelectMultiple(),
            "assigned_staff": forms.Select(attrs={"class": "field-input"}),
            "status": forms.Select(attrs={"class": "field-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import Role, User

        self.fields["assigned_staff"].queryset = User.objects.filter(
            role__in=[Role.STAFF, Role.ADMIN], is_active=True
        )
        self.fields["assigned_staff"].empty_label = "Nobody yet"
        self.fields["services"].queryset = Service.objects.order_by("code")

    def clean_code(self):
        return self.cleaned_data["code"].strip().upper()


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ["accepting_tokens", "announcement"]
        labels = {
            "accepting_tokens": "Issue new tokens",
            "announcement": "Notice on the board",
        }
        widgets = {
            "announcement": forms.TextInput(
                attrs={
                    "class": "field-input",
                    "placeholder": "Counters close at 4:30 pm today",
                }
            )
        }
