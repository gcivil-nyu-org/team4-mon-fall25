# recom_sys_app/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

from .models import UserProfile, Sex, Genre

User = get_user_model()


class UserProfileForm(forms.ModelForm):
    sex = forms.ChoiceField(choices=Sex.choices, required=True, label="Sex")
    favourite_genre1 = forms.ChoiceField(
        choices=Genre.choices, required=False, label="Favourite Genre 1"
    )
    favourite_genre2 = forms.ChoiceField(
        choices=Genre.choices, required=False, label="Favourite Genre 2"
    )

    class Meta:
        model = UserProfile
        fields = [
            "name",
            "sex",
            "age",
            "date_of_birth",
            "country",
            "favourite_genre1",
            "favourite_genre2",
            "liked_g1_tmdb_id",
            "liked_g1_title",
            "liked_g2_tmdb_id",
            "liked_g2_title",
            "language",
            "timezone",
            "onboarding_complete",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }


class SignUpForm(UserCreationForm):
    # Extra fields you wanted on signup
    name = forms.CharField(max_length=120, label="Name")
    email = forms.EmailField(label="Email")

    country = forms.CharField(
        max_length=64, label="Country"
    )  # ← NEW (required by model)

    age = forms.IntegerField(min_value=1, max_value=120, required=False)
    sex = forms.ChoiceField(choices=Sex.choices, required=True, label="Sex")
    favourite_genre1 = forms.ChoiceField(
        choices=Genre.choices, required=False, label="Favourite Genre 1"
    )
    favourite_genre2 = forms.ChoiceField(
        choices=Genre.choices, required=False, label="Favourite Genre 2"
    )
    liked_g1_title = forms.CharField(
        max_length=300, required=False, label="Movie you like in Genre 1"
    )
    liked_g2_title = forms.CharField(
        max_length=300, required=False, label="Movie you like in Genre 2"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        # We’ll use email as the username; passwords come from UserCreationForm
        fields = ("email",)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        # Enforce unique email
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        g1 = data.get("favourite_genre1")
        g2 = data.get("favourite_genre2")
        if g1 and not data.get("liked_g1_title"):
            self.add_error("liked_g1_title", "Add one movie you like in Genre 1.")
        if g2 and not data.get("liked_g2_title"):
            self.add_error("liked_g2_title", "Add one movie you like in Genre 2.")
        return data

    def save(self, commit=True):
        """Create the User (username=email), then the UserProfile with the extra fields."""
        user = super().save(commit=False)
        email = self.cleaned_data["email"].strip().lower()
        name = self.cleaned_data["name"].strip()

        user.username = email
        user.email = email
        user.first_name = name[:150]

        if commit:
            user.save()
            UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "name": name,
                    "country": self.cleaned_data.get(
                        "country", ""
                    ).strip(),  # ← PASS COUNTRY
                    "age": self.cleaned_data.get("age"),
                    "sex": self.cleaned_data.get("sex"),
                    "favourite_genre1": self.cleaned_data.get("favourite_genre1") or "",
                    "favourite_genre2": self.cleaned_data.get("favourite_genre2") or "",
                    "liked_g1_title": (
                        self.cleaned_data.get("liked_g1_title") or ""
                    ).strip(),
                    "liked_g2_title": (
                        self.cleaned_data.get("liked_g2_title") or ""
                    ).strip(),
                },
            )
        return user
