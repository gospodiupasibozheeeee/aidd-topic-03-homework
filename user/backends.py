from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    """Support legacy mixed-case usernames and normalized new accounts."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        model = get_user_model()
        try:
            user = model.objects.get(username__iexact=username)
        except (model.DoesNotExist, model.MultipleObjectsReturned):
            model().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
