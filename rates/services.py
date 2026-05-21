import csv
import requests
from io import StringIO
from datetime import datetime, timedelta
from django.conf import settings


class CurrencyParser:
    """Получение данных с внешнего API и сохранение в БД"""

    BASE_URL = "https://api.exchangerate-api.com/v4/latest/USD"
    CURRENCIES = ["KZT", "EUR", "RUB"]

    def fetch(self):
        """Запрашивает курсы с API. Возвращает dict или None при ошибке."""
        try:
            response = requests.get(self.BASE_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "rates" not in data:
                raise ValueError("Поле 'rates' отсутствует в ответе API")
            return data["rates"]
        except requests.exceptions.ConnectionError:
            print("[CurrencyParser] Ошибка: нет соединения с API")
            return None
        except requests.exceptions.Timeout:
            print("[CurrencyParser] Ошибка: таймаут запроса")
            return None
        except requests.exceptions.HTTPError as e:
            print(f"[CurrencyParser] HTTP ошибка: {e}")
            return None
        except (ValueError, KeyError) as e:
            print(f"[CurrencyParser] Ошибка данных: {e}")
            return None
        except Exception as e:
            print(f"[CurrencyParser] Неизвестная ошибка: {e}")
            return None

    def save(self, rates):
        """Сохраняет полученные курсы в БД. Возвращает True при успехе."""
        if not rates:
            return False

        from .models import Currency

        saved = 0
        for code in self.CURRENCIES:
            value = rates.get(code)
            if value:
                Currency.objects.create(name=f"USD/{code}", value=value)
                saved += 1

        print(f"[CurrencyParser] Сохранено {saved} курсов")
        return saved > 0


class RateAnalyzer:
    """Аналитика, расчёты и прогнозы по курсам валют"""

    def get_latest(self, currency_name):
        """Возвращает последнюю запись курса."""
        from .models import Currency
        return Currency.objects.filter(name=currency_name).order_by("-date").first()

    def get_trend(self, currency_name):
        """Возвращает 'up', 'down' или None если недостаточно данных."""
        from .models import Currency
        last_two = list(
            Currency.objects.filter(name=currency_name).order_by("-date")[:2]
        )
        if len(last_two) < 2:
            return None
        return "up" if last_two[0].value > last_two[1].value else "down"

    def get_change_24h(self, currency_name):
        """Изменение курса за последние 24 часа в процентах."""
        from .models import Currency
        now = datetime.now()
        day_ago = now - timedelta(days=1)

        latest = Currency.objects.filter(name=currency_name).order_by("-date").first()
        oldest = Currency.objects.filter(
            name=currency_name, date__gte=day_ago
        ).order_by("date").first()

        if not latest or not oldest or oldest.value == 0:
            return None

        change = ((latest.value - oldest.value) / oldest.value) * 100
        return round(change, 2)

    def predict_tomorrow(self, currency_name):
        """
        Простой прогноз на завтра на основе среднего значения за 7 дней.
        Возвращает число или None если данных недостаточно.
        """
        from .models import Currency
        week_ago = datetime.now() - timedelta(days=7)
        values = list(
            Currency.objects.filter(
                name=currency_name, date__gte=week_ago
            ).values_list("value", flat=True)
        )

        if not values:
            return None

        return round(sum(values) / len(values), 2)

    def convert(self, amount, from_currency, to_currency, commission_pct=0):
        """
        Конвертирует сумму из одной валюты в другую через USD как базу.
        Учитывает комиссию в процентах.
        Возвращает dict с result, commission, rate — или None при ошибке.
        """
        from_rate = 1.0  # USD/USD = 1
        to_rate = 1.0

        if from_currency != "USD":
            obj = self.get_latest(f"USD/{from_currency}")
            if not obj:
                return None
            from_rate = obj.value

        if to_currency != "USD":
            obj = self.get_latest(f"USD/{to_currency}")
            if not obj:
                return None
            to_rate = obj.value

        # Переводим в USD, затем в целевую валюту
        usd_amount = amount / from_rate
        result = usd_amount * to_rate

        # Вычитаем комиссию
        commission = result * (commission_pct / 100)
        result_after = result - commission

        return {
            "result": round(result_after, 2),
            "commission": round(commission, 2),
            "rate": round(to_rate / from_rate, 4),
        }


class Notifier:
    """Отправка уведомлений через Telegram Bot API"""

    def send(self, chat_id, message):
        """
        Отправляет сообщение в Telegram.
        Возвращает True при успехе, False при ошибке.
        """
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)

        if not token or token in ("сюда_вставь_токен", ""):
            print("[Notifier] Telegram токен не настроен в settings.py")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            response = requests.post(
                url,
                data={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=5,
            )
            if response.status_code == 200:
                print(f"[Notifier] Сообщение отправлено в {chat_id}")
                return True
            else:
                print(f"[Notifier] Ошибка Telegram API: {response.text}")
                return False
        except requests.exceptions.Timeout:
            print("[Notifier] Таймаут при отправке в Telegram")
            return False
        except Exception as e:
            print(f"[Notifier] Неизвестная ошибка: {e}")
            return False

    def check_and_notify(self, currency_name, new_value):
        """
        Проверяет все активные алерты для валюты.
        Отправляет уведомление если условие сработало.
        """
        from .models import AlertSetting

        code = currency_name.replace("USD/", "")
        alerts = AlertSetting.objects.filter(currency=code, is_active=True)

        for alert in alerts:
            triggered = (
                alert.direction == "above" and new_value > alert.threshold
            ) or (
                alert.direction == "below" and new_value < alert.threshold
            )

            if triggered:
                direction_text = "выше" if alert.direction == "above" else "ниже"
                msg = (
                    f"🔔 <b>Алерт сработал!</b>\n\n"
                    f"💱 {currency_name} = <b>{new_value:.2f}</b>\n"
                    f"📊 Условие: курс {direction_text} {alert.threshold}\n"
                    f"👤 Пользователь: {alert.user.username}\n"
                    f"⏰ {datetime.now().strftime('%d.%m.%Y %H:%M')}"
                )
                self.send(alert.telegram_chat_id, msg)


class CSVExporter:
    """Экспорт истории курсов в CSV файл"""

    def export(self, currency_name):
        """
        Возвращает строку CSV со всеми записями для указанной валюты.
        """
        from .models import Currency

        rates = Currency.objects.filter(name=currency_name).order_by("-date")

        output = StringIO()
        writer = csv.writer(output)

        # Заголовок
        writer.writerow(["Дата", "Время", "Валюта", "Курс (USD)"])

        # Данные
        for r in rates:
            writer.writerow([
                r.date.strftime("%Y-%m-%d"),
                r.date.strftime("%H:%M:%S"),
                r.name,
                r.value,
            ])

        return output.getvalue()