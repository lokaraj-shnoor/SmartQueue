from django import forms

from .models import Service


class TokenCreateForm(forms.Form):
    service = forms.ModelChoiceField(
        queryset=Service.objects.filter(is_active=True),
        empty_label="Choose a service",
    )


class QueueHistoryFilterForm(forms.Form):
    query = forms.CharField(required=False, label="Search")
    status = forms.ChoiceField(required=False, choices=[("", "All statuses")])
    service = forms.ModelChoiceField(
        required=False,
        queryset=Service.objects.all(),
        empty_label="All services",
    )
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        from .models import Token

        super().__init__(*args, **kwargs)
        self.fields["status"].choices += list(Token.Status.choices)
