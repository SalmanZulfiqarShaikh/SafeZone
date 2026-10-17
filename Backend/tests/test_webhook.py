import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import config
from routes import webhook


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", "verify-me")
    monkeypatch.setattr(webhook.whatsapp, "verify_signature", lambda _body, _sig: True)

    app = FastAPI()
    app.include_router(webhook.router)
    return TestClient(app)


def text_payload(sender="923001234567", text="There is flooding here"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": sender,
                                    "id": "wamid.1",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def test_verification_echoes_the_challenge(client):
    response = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-me",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 200
    assert response.text == "12345"


def test_verification_rejects_a_wrong_token(client):
    response = client.get(
        "/webhook/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "12345",
        },
    )

    assert response.status_code == 403


def test_verification_rejects_when_no_token_is_configured(client, monkeypatch):
    monkeypatch.setattr(config, "WHATSAPP_VERIFY_TOKEN", "")

    response = client.get(
        "/webhook/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"},
    )

    assert response.status_code == 403


def test_inbound_text_is_forwarded_to_intake(client, monkeypatch):
    received = []
    monkeypatch.setattr(
        webhook.intake, "handle_inbound", lambda sender, text, **kwargs: received.append((sender, text))
    )

    response = client.post("/webhook/whatsapp", json=text_payload())

    assert response.status_code == 200
    assert received == [("923001234567", "There is flooding here")]


def test_status_callbacks_are_ignored(client, monkeypatch):
    received = []
    monkeypatch.setattr(
        webhook.intake, "handle_inbound", lambda sender, text, **kwargs: received.append((sender, text))
    )
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"id": "wamid.1", "status": "delivered", "recipient_id": "92300"}
                            ]
                        }
                    }
                ]
            }
        ]
    }

    response = client.post("/webhook/whatsapp", json=payload)

    assert response.status_code == 200
    assert received == []


def test_non_text_messages_are_ignored(client, monkeypatch):
    received = []
    monkeypatch.setattr(
        webhook.intake, "handle_inbound", lambda sender, text, **kwargs: received.append((sender, text))
    )
    payload = text_payload()
    message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
    message["type"] = "image"
    message.pop("text")

    response = client.post("/webhook/whatsapp", json=payload)

    assert response.status_code == 200
    assert received == []


def test_malformed_json_still_returns_200(client, monkeypatch):
    received = []
    monkeypatch.setattr(
        webhook.intake, "handle_inbound", lambda sender, text, **kwargs: received.append((sender, text))
    )

    response = client.post(
        "/webhook/whatsapp",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert received == []


def test_intake_failure_still_returns_200(client, monkeypatch):
    def explode(_sender, _text, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(webhook.intake, "handle_inbound", explode)

    response = client.post("/webhook/whatsapp", json=text_payload())

    assert response.status_code == 200
    assert response.json() == {"status": "received"}


def test_invalid_signature_is_acknowledged_but_not_processed(client, monkeypatch):
    monkeypatch.setattr(webhook.whatsapp, "verify_signature", lambda _body, _sig: False)
    received = []
    monkeypatch.setattr(
        webhook.intake, "handle_inbound", lambda sender, text, **kwargs: received.append((sender, text))
    )

    response = client.post("/webhook/whatsapp", json=text_payload())

    assert response.status_code == 200
    assert response.json() == {"status": "ignored"}
    assert received == []


def test_parse_messages_skips_malformed_entries():
    payload = text_payload()
    payload["entry"][0]["changes"][0]["value"]["messages"].append({"type": "text"})

    assert list(webhook.parse_messages(payload)) == [
        webhook.InboundMessage(sender="923001234567", text="There is flooding here")
    ]


def test_parse_messages_accepts_a_serialized_payload():
    payload = json.loads(json.dumps(text_payload()))

    assert list(webhook.parse_messages(payload)) == [
        webhook.InboundMessage(sender="923001234567", text="There is flooding here")
    ]
