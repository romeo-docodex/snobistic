from django import forms
from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Scrie un mesaj...',
                'class': 'form-control'
            }),
            'attachment': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'content': '',
            'attachment': 'Atașament (opțional)',
        }
