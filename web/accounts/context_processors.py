from .forms import LoginForm, RegisterForm

def login_form_context(request):
    return {
        'login_form': LoginForm(request=request),
        'register_form': RegisterForm()
    }
