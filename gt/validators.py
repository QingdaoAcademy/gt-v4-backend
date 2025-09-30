from django.core.exceptions import ValidationError


def validate_no_invisible_characters(value):
    if any(ord(char) in range(0, 32) for char in value):
        raise ValidationError("不得包含空格、回车等不可见字符")
