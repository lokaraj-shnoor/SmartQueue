from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.contrib.auth.password_validation import validate_password

from accounts.models import Role, User


class SignUpForm(UserCreationForm):
    """Public sign-up. Always creates a visitor; roles are granted, not chosen."""

    first_name = forms.CharField(max_length=150, label="Full name")
    email = forms.EmailField(label="Email")
    phone = forms.CharField(max_length=32, required=False, label="Phone (optional)")

    class Meta:
        model = User
        fields = ["first_name", "username", "email", "phone"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"
        # Django's defaults here are a four-bullet list that swamps the card.
        # Same rules, said once.
        self.fields["username"].help_text = "Letters, digits and @ . + - _ only."
        self.fields["password1"].help_text = (
            "At least 8 characters. Not all numbers, and not too close to your name."
        )
        self.fields["password2"].help_text = ""
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "field-input")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account already uses this email.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.phone = self.cleaned_data.get("phone", "")
        user.role = Role.VISITOR
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {"class": "field-input", "autofocus": True, "autocomplete": "username"}
        )
        self.fields["password"].widget.attrs.update(
            {"class": "field-input", "autocomplete": "current-password"}
        )


class StaffAccountForm(forms.ModelForm):
    """Admins create staff and administrator accounts from the dashboard."""

    password1 = forms.CharField(
        label="Temporary password",
        widget=forms.PasswordInput(attrs={"class": "field-input"}),
        help_text="Share it with them once. They can change it after signing in.",
    )
    role = forms.ChoiceField(
        choices=[(Role.STAFF, "Counter staff"), (Role.ADMIN, "Administrator")],
        widget=forms.Select(attrs={"class": "field-input"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "username", "email", "phone", "department", "role"]
        labels = {"first_name": "Full name"}
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "field-input"}),
            "username": forms.TextInput(attrs={"class": "field-input"}),
            "email": forms.EmailInput(attrs={"class": "field-input"}),
            "phone": forms.TextInput(attrs={"class": "field-input"}),
            "department": forms.TextInput(attrs={"class": "field-input"}),
        }

    def clean_email(self):
        """One address, one account.

        Password resets go to whoever holds the address, and Google sign-in
        matches on it, so a second account with the same email leaves both
        pointing at whichever row happens to come first.
        """
        email = self.cleaned_data["email"].strip().lower()
        clash = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError(
                "Another account already uses this email: " + clash.first().username + "."
            )
        return email

    def clean_password1(self):
        password = self.cleaned_data["password1"]
        validate_password(password)
        return password

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class PasswordResetRequestForm(PasswordResetForm):
    """Django's reset form, wearing this project's field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["email"].widget.attrs.update(
            {
                "class": "field-input",
                "autocomplete": "email",
                "autofocus": True,
                "placeholder": "you@example.edu",
            }
        )


class NewPasswordForm(SetPasswordForm):
    """The two boxes at the end of a reset link."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "Confirm password"
        self.fields["new_password1"].help_text = (
            "At least 8 characters. Not all numbers, and not too close to your name."
        )
        self.fields["new_password2"].help_text = ""
        for field in self.fields.values():
            field.widget.attrs.update({"class": "field-input", "autocomplete": "new-password"})
