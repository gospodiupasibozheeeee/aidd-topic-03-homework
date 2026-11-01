from rest_framework import serializers

from dashboard.models import Share


class ShareSerializer(serializers.ModelSerializer):
    class Meta:
        model = Share
        fields = (
            "id",
            "figi",
            "isin",
            "name",
            "ticker",
            "currency",
            "uid",
            "last_price",
            "is_trend_high",
            "updated_at",
        )
        # Old update clients can retain their existing UID by omitting it.
        extra_kwargs = {"uid": {"required": False}}

    def validate(self, attrs):
        if self.instance is None and not attrs.get("uid"):
            raise serializers.ValidationError({"uid": "Обязательное поле."})
        return attrs
