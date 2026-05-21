import requests
from django.conf import settings

CURRENCIES = ["KZT", "EUR", "RUB"]

def get_rates():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "rates" not in data:
            raise ValueError("Неверный формат")
        return data["rates"]
    except requests.exceptions.ConnectionError:
        print("Нет соединения")
        return None
    except requests.exceptions.Timeout:
        print("Таймаут")
        return None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None


def send_telegram(chat_id, message):
    token = settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, data={"chat_id": chat_id, "text": message}, timeout=5)
    except Exception as e:
        print(f"Telegram ошибка: {e}")


def check_alerts(currency_name, new_value):
    from .models import AlertSetting
    alerts = AlertSetting.objects.filter(
        currency=currency_name.replace("USD/", ""),
        is_active=True
    )
    for alert in alerts:
        triggered = (
            alert.direction == "above" and new_value > alert.threshold or
            alert.direction == "below" and new_value < alert.threshold
        )
        if triggered:
            msg = (
                f"🔔 Алерт сработал!\n"
                f"USD/{alert.currency} = {new_value:.2f}\n"
                f"Условие: {'выше' if alert.direction == 'above' else 'ниже'} {alert.threshold}"
            )
            send_telegram(alert.telegram_chat_id, msg)