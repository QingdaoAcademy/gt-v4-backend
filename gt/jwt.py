import base64
import hashlib
import json
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework import exceptions


INCLUDED_KEYS = ["user_id", "user_version", "exp", "source", "from_school"]
REQUIRED_KEYS = ["exp"]
SECRET_KEY = settings.SECRET_KEY


def _encode_base64(data: str) -> str:
    return base64.urlsafe_b64encode(data.encode()).decode()


def _encode_sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def _decode_base64(data: str) -> str:
    return base64.urlsafe_b64decode(data).decode()


class GtSignature:
    @classmethod
    def calculate_signature(cls, payload: dict) -> str:
        payload = {key: payload[key] for key in sorted(payload)}
        if type(payload["exp"]) == datetime:
            payload["exp"] = int(payload["exp"].timestamp())
        for key in REQUIRED_KEYS:
            if key not in payload:
                raise ValueError(f"Missing required key: {key}")
        _payload = {key: payload[key] for key in INCLUDED_KEYS if key in payload}
        _verify_str = _encode_base64(json.dumps(_payload))
        signature = _encode_sha256(f"{_verify_str}+{SECRET_KEY}")
        # return f"{_encode_base64(json.dumps(payload))}.{signature}"
        return signature

    @classmethod
    def decode(cls, token):
        data, signature = token.split(".")
        payload = json.loads(_decode_base64(data))
        payload = {key: payload[key] for key in sorted(payload)}
        for key in REQUIRED_KEYS:
            if key not in payload:
                raise exceptions.AuthenticationFailed(f"Missing required key: {key}")
        if payload["exp"] < timezone.now().timestamp():
            raise exceptions.AuthenticationFailed("Token has expired")
        _payload = {key: payload[key] for key in INCLUDED_KEYS if key in payload}
        _verify_str = _encode_base64(json.dumps(_payload))
        if _encode_sha256(f"{_verify_str}+{SECRET_KEY}") != signature:
            raise exceptions.AuthenticationFailed("Invalid token")
        return payload
