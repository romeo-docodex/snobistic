from django import forms
from .models import Message, Conversation

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['text', 'attachment']
        widgets = {
            'text': forms.Textarea(attrs={'rows':2, 'placeholder':'Scrie un mesaj…'}),
        }

class ConversationStartForm(forms.Form):
    recipient_email = forms.EmailField(label="Adresa de email a destinatarului")

    def clean_recipient_email(self):
        email = self.cleaned_data['recipient_email']
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("Nu există un utilizator cu acest email.")
        return email

    def save(self, starter):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        recipient = User.objects.get(email=self.cleaned_data['recipient_email'])
        conv = Conversation.objects.create()
        conv.participants.add(starter, recipient)
        conv.save()
        return conv
