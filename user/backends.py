from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class CaseInsensitiveEmailBackend(ModelBackend):
    """
    Аутентификация пользователя по email без учета регистра.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = username or kwargs.get("email")
        if not email or not password:
            return None

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        except User.MultipleObjectsReturned:
            user = User.objects.filter(email__iexact=email).order_by("id").first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
