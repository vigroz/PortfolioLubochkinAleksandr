import os
import re
import pytest
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

# Загружаем переменные из .env
load_dotenv()

# Переменные из .env
BASE_URL = os.getenv("BASE_URL")
QIWI_TOKEN = os.getenv("QIWI_TOKEN")
APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
AGENT_ID = os.getenv("AGENT_ID")
POINT_ID = os.getenv("POINT_ID")
PAYMENT_ID = os.getenv("PAYMENT_ID")

# Общие заголовки
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "Authorization": f"Bearer {QIWI_TOKEN}"
}


@pytest.fixture(scope="session")
def api_request():
    """Фикстура: создаёт контекст для API-запросов"""
    with sync_playwright() as p:
        request_context = p.request.new_context(
            base_url=BASE_URL,
            extra_http_headers=DEFAULT_HEADERS
        )
        yield request_context
        request_context.dispose()


def test_1_check_form_availability(api_request):
    """Проверка доступности формы"""
    headers = {
        "X-Application-Id": APP_ID,
        "X-Application-Secret": APP_SECRET
    }
    response = api_request.get("/partner/sinap/providers/mosoblgaz-podolsk/form", headers=headers)
    assert response.status == 200, f"Ожидался 200, получен {response.status}"

    data = response.json()
    assert "id" in data
    assert "content" in data
    assert "elements" in data["content"]

    account_field = next((f for f in data["content"]["elements"] if f.get("name") == "account"), None)
    assert account_field is not None, "Поле 'account' не найдено"


def test_2_get_balance(api_request):
    """Запрос баланса"""
    url = f"/partner/payout/v1/agents/{AGENT_ID}/points/{POINT_ID}/balance"
    response = api_request.get(url)
    assert response.status == 200

    data = response.json()
    assert "balance" in data
    assert data["balance"]["currency"] == "RUB"
    assert float(data["balance"]["value"]) > 0


def test_3_create_payment(api_request):
    """Создание платежа"""
    url = f"/partner/payout/v1/agents/{AGENT_ID}/points/{POINT_ID}/payments/{PAYMENT_ID}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipientDetails": {
            "providerCode": "Bilain",
            "fields": {"account": "79123456789"}
        },
        "amount": {"value": "1.00", "currency": "RUB"},
        "customer": {
            "account": "test_user_001",
            "email": "test@mail.com",
            "phone": "79123456789"
        },
        "source": {
            "paymentType": "WITH_EXTRA_CHARGE",
            "paymentToolType": "CASH",
            "paymentTerminalType": "ATM_CASH_IN",
            "paymentDate": "2025-08-26T14:02:35.589+03:00",
            "extraCharge": {"value": "1.00", "currency": "RUB"},
            "callbackUrl": "https://domain/path",
            "IdentificationType": "NONE"
        }
    }

    response = api_request.put(url, headers=headers, data=payload)
    assert response.status == 200

    data = response.json()
    assert data["paymentId"] == PAYMENT_ID
    assert data["status"]["value"] == "READY"
    assert data["amount"]["currency"] == "RUB"
    assert float(data["amount"]["value"]) > 0
    assert "commission" in data and data["commission"]["currency"] == "RUB"
    assert data["recipientDetails"]["fields"]["account"] == "79123456789"
    assert re.match(r"^\d{10,11}$", data["customer"]["phone"])
    assert "customFields" in data and "cashier" in data["customFields"]
    assert "billingDetails" in data and "transactionId" in data["billingDetails"]


def test_4_execute_payment(api_request):
    """Исполнение платежа"""
    url = f"/partner/payout/v1/agents/{AGENT_ID}/points/{POINT_ID}/payments/{PAYMENT_ID}/execute"
    response = api_request.post(url)
    assert response.status == 200

    data = response.json()
    assert data["paymentId"] == PAYMENT_ID
    assert data["status"]["value"] in ["IN_PROGRESS", "PROCESSED", "PENDING"]
    assert data["amount"]["currency"] == "RUB"
    assert float(data["amount"]["value"]) > 0
    assert "commission" in data and data["commission"]["currency"] == "RUB"
    assert re.match(r"^\d{10,11}$", data["customer"]["phone"])
    assert "paymentToolType" in data["source"]
    assert "customFields" in data and "cashier" in data["customFields"]
    assert "billingDetails" in data and "transactionId" in data["billingDetails"] and "rrn" in data["billingDetails"]