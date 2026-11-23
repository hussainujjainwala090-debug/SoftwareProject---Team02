"""Push alerts through Firebase Cloud Messaging (FR-11)."""
from typing import Protocol


class Messenger(Protocol):
    def send(self, fcm_token: str, title: str, body: str, data: dict[str, str]) -> None: ...


class FakeMessenger:
    """Records messages instead of sending them (memory mode and tests)."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, fcm_token: str, title: str, body: str, data: dict[str, str]) -> None:
        self.sent.append({"token": fcm_token, "title": title, "body": body, "data": data})


class FcmMessenger:
    def __init__(self, firebase_app) -> None:
        self._app = firebase_app

    def send(self, fcm_token: str, title: str, body: str, data: dict[str, str]) -> None:
        from firebase_admin import messaging

        message = messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(title=title, body=body),
            data=data,
        )
        messaging.send(message, app=self._app)
