from django import forms
from .models import AuthRequest, AuthImage

class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class AuthUploadForm(forms.ModelForm):
    images = forms.FileField(
        widget=MultiFileInput(),
        required=True,
        label="Imagini produs"
    )

    class Meta:
        model = AuthRequest
        fields = ['email', 'images']

    def save(self, commit=True):
        # Save the AuthRequest first
        auth_req = super().save(commit=commit)

        # Then process each uploaded file
        # Note: use self.files not cleaned_data for files
        files = self.files.getlist('images')
        for f in files:
            AuthImage.objects.create(auth_request=auth_req, image=f)
        return auth_req
