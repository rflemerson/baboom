from django import forms
from django.utils.translation import gettext_lazy as _

from .models import AlertSubscriber


class AlertSubscriptionForm(forms.ModelForm):
    email = forms.EmailField(
        error_messages={"invalid": _("Please enter a valid email address.")},
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": _("your@email.com"),
            }
        ),
    )

    class Meta:
        model = AlertSubscriber
        fields = ["email"]
        error_messages = {"email": {"unique": _("This email is already subscribed.")}}
