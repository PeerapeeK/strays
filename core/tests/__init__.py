from django.urls import reverse


def login_via_view(client, username, password):
    """Log in through the real LoginView so django-axes sees the request."""
    response = client.post(
        reverse('login'),
        {'username': username, 'password': password},
    )
    return response.status_code == 302
