import json
import re
from datetime import datetime, timedelta
from functools import wraps

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render

from .models import AlertSetting, Currency, UserProfile
from .services import CurrencyParser, Notifier, RateAnalyzer

CURRENCIES = ["KZT", "EUR", "RUB"]


# ════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════

def get_or_create_profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def admin_required(view_func):
    """Декоратор: доступ только для администраторов"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/login/")
        profile = get_or_create_profile(request.user)
        if not profile.is_admin():
            return redirect("/")
        return view_func(request, *args, **kwargs)
    return wrapper


def validate_email(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)


# ════════════════════════════════════════════
#  MAIN — КУРСЫ ВАЛЮТ
# ════════════════════════════════════════════

def index(request):
    selected_currency = request.GET.get("currency", "KZT")
    period = request.GET.get("period", "all")
    now = datetime.now()
    day_ago = now - timedelta(days=1)
    week_ago = now - timedelta(days=7)

    # Если авторизован — показываем только его данные,
    # если гость — показываем последние данные из всей БД
    def base_qs(name):
        qs = Currency.objects.filter(name=name)
        if request.user.is_authenticated:
            qs = qs.filter(user=request.user)
        return qs

    rates_qs = base_qs(f"USD/{selected_currency}").order_by("date")

    if period == "day":
        rates_qs = rates_qs.filter(date__gte=now - timedelta(days=1))
    elif period == "week":
        rates_qs = rates_qs.filter(date__gte=now - timedelta(weeks=1))
    elif period == "month":
        rates_qs = rates_qs.filter(date__gte=now - timedelta(days=30))

    chart_labels = [r.date.strftime("%d.%m %H:%M") for r in rates_qs]
    chart_values = [r.value for r in rates_qs]

    # Статистика по всем валютам
    currency_stats = []
    for code in CURRENCIES:
        name = f"USD/{code}"

        latest = base_qs(name).order_by("-date").first()

        oldest = base_qs(name).filter(date__gte=day_ago).order_by("date").first()

        change = None
        if latest and oldest and oldest.value != 0:
            change = round(((latest.value - oldest.value) / oldest.value) * 100, 2)

        values = list(base_qs(name).filter(
            date__gte=week_ago
        ).values_list("value", flat=True))
        prediction = round(sum(values) / len(values), 2) if values else None

        currency_stats.append({
            "code": code,
            "name": name,
            "latest": latest,
            "change": change,
            "prediction": prediction,
        })

    latest = base_qs(f"USD/{selected_currency}").order_by("-date").first()

    last_two = list(base_qs(f"USD/{selected_currency}").order_by("-date")[:2])
    trend = None
    if len(last_two) == 2:
        trend = "up" if last_two[0].value > last_two[1].value else "down"

    context = {
        "rates": rates_qs.order_by("-date"),
        "currencies": CURRENCIES,
        "selected_currency": selected_currency,
        "period": period,
        "period_choices": [
            ("day", "День"), ("week", "Неделя"),
            ("month", "Месяц"), ("all", "Всё"),
        ],
        "chart_labels": json.dumps(chart_labels),
        "chart_values": json.dumps(chart_values),
        "latest": latest,
        "trend": trend,
        "currency_stats": currency_stats,
    }
    return render(request, "index.html", context)


@login_required
def update_rates(request):
    parser = CurrencyParser()
    notifier = Notifier()
    rates = parser.fetch()

    if rates:
        for code in CURRENCIES:
            value = rates.get(code)
            if value:
                Currency.objects.create(
                    name=f"USD/{code}",
                    value=value,
                    user=request.user
                )
                notifier.check_and_notify(f"USD/{code}", value)

    return redirect("/")


@login_required
def delete_rate(request, rate_id):
    if request.method == "POST":
        Currency.objects.filter(id=rate_id, user=request.user).delete()
    currency = request.POST.get("currency", "KZT")
    return redirect(f"/history/?currency={currency}")


@login_required
def delete_all_rates(request):
    if request.method == "POST":
        currency = request.POST.get("currency", "KZT")
        Currency.objects.filter(name=f"USD/{currency}", user=request.user).delete()
        return redirect(f"/history/?currency={currency}")
    return redirect("/history/")


# ════════════════════════════════════════════
#  КОНВЕРТЕР
# ════════════════════════════════════════════

def converter(request):
    result = None
    error = None

    if request.method == "POST":
        try:
            amount = float(request.POST.get("amount", 0))
            from_cur = request.POST.get("from_currency", "USD")
            to_cur = request.POST.get("to_currency", "KZT")
            commission = float(request.POST.get("commission", 0))

            if amount <= 0:
                error = "Сумма должна быть больше нуля"
            elif amount > 1_000_000_000:
                error = "Сумма слишком большая"
            elif commission < 0 or commission > 100:
                error = "Комиссия должна быть от 0 до 100"
            else:
                analyzer = RateAnalyzer()
                result = analyzer.convert(amount, from_cur, to_cur, commission)
                if not result:
                    error = "Нет данных о курсах. Нажмите «Обновить» на главной."
        except (ValueError, TypeError):
            error = "Некорректные данные. Введите числа."

    all_currencies = ["USD"] + CURRENCIES
    return render(request, "converter.html", {
        "result": result,
        "error": error,
        "currencies": all_currencies,
    })


# ════════════════════════════════════════════
#  НАСТРОЙКИ АЛЕРТОВ
# ════════════════════════════════════════════

@login_required
def user_settings(request):
    alerts = AlertSetting.objects.filter(user=request.user)
    error = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "add_alert":
            try:
                currency = request.POST.get("currency", "").strip()
                threshold_str = request.POST.get("threshold", "").strip()
                direction = request.POST.get("direction", "")
                chat_id = request.POST.get("telegram_chat_id", "").strip()

                if currency not in CURRENCIES:
                    raise ValueError("Недопустимая валюта")
                if not threshold_str:
                    raise ValueError("Укажите порог")
                threshold = float(threshold_str)
                if threshold <= 0 or threshold > 10_000_000:
                    raise ValueError("Некорректный порог")
                if direction not in ["above", "below"]:
                    raise ValueError("Некорректное условие")
                if not chat_id or not chat_id.lstrip("-").isdigit():
                    raise ValueError("Chat ID должен быть числом (узнай у @userinfobot)")

                AlertSetting.objects.create(
                    user=request.user,
                    currency=currency,
                    threshold=threshold,
                    direction=direction,
                    telegram_chat_id=chat_id,
                )
            except ValueError as e:
                error = str(e)

        elif action == "delete_alert":
            alert_id = request.POST.get("alert_id")
            AlertSetting.objects.filter(id=alert_id, user=request.user).delete()

        if not error:
            return redirect("settings")

    return render(request, "settings.html", {
        "alerts": alerts,
        "currencies": CURRENCIES,
        "error": error,
    })


# ════════════════════════════════════════════
#  АУТЕНТИФИКАЦИЯ
# ════════════════════════════════════════════

def login_view(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        if not username or not password:
            error = "Заполните все поля"
        elif len(username) > 150:
            error = "Логин слишком длинный"
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect(request.GET.get("next", "/"))
            else:
                error = "Неверный логин или пароль"

    return render(request, "login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("/")


def register_view(request):
    error = None
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")

        if not username or not email or not password1:
            error = "Заполните все поля"
        elif len(username) < 3 or len(username) > 150:
            error = "Логин от 3 до 150 символов"
        elif not validate_email(email):
            error = "Некорректный email"
        elif password1 != password2:
            error = "Пароли не совпадают"
        elif len(password1) < 6:
            error = "Пароль минимум 6 символов"
        elif User.objects.filter(username=username).exists():
            error = "Пользователь с таким логином уже существует"
        elif User.objects.filter(email=email).exists():
            error = "Этот email уже используется"
        else:
            user = User.objects.create_user(
                username=username, email=email, password=password1
            )
            get_or_create_profile(user)
            login(request, user)
            return redirect("/")

    return render(request, "register.html", {"error": error})


# ════════════════════════════════════════════
#  ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ
# ════════════════════════════════════════════

@login_required
def profile_view(request):
    profile = get_or_create_profile(request.user)
    alerts_count = AlertSetting.objects.filter(user=request.user).count()
    return render(request, "profile.html", {
        "profile": profile,
        "alerts_count": alerts_count,
    })


@login_required
def edit_profile_view(request):
    profile = get_or_create_profile(request.user)
    error = None
    success = None

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "update_info":
            new_username = request.POST.get("username", "").strip()
            new_email = request.POST.get("email", "").strip()

            if not new_username or not new_email:
                error = "Заполните все поля"
            elif len(new_username) < 3:
                error = "Логин минимум 3 символа"
            elif not validate_email(new_email):
                error = "Некорректный email"
            elif User.objects.filter(username=new_username).exclude(id=request.user.id).exists():
                error = "Этот логин уже занят"
            elif User.objects.filter(email=new_email).exclude(id=request.user.id).exists():
                error = "Этот email уже используется"
            else:
                request.user.username = new_username
                request.user.email = new_email
                request.user.save()
                success = "Данные обновлены"

        elif action == "change_password":
            old_pass = request.POST.get("old_password", "")
            new_pass1 = request.POST.get("new_password1", "")
            new_pass2 = request.POST.get("new_password2", "")

            if not request.user.check_password(old_pass):
                error = "Неверный текущий пароль"
            elif len(new_pass1) < 6:
                error = "Новый пароль минимум 6 символов"
            elif new_pass1 != new_pass2:
                error = "Новые пароли не совпадают"
            else:
                request.user.set_password(new_pass1)
                request.user.save()
                update_session_auth_hash(request, request.user)
                success = "Пароль успешно изменён"

    return render(request, "edit_profile.html", {
        "profile": profile,
        "error": error,
        "success": success,
    })


@login_required
def history_view(request):
    selected_currency = request.GET.get("currency", "KZT")

    rates = Currency.objects.filter(
        user=request.user,
        name=f"USD/{selected_currency}"
    ).order_by("-date")

    return render(request, "history.html", {
        "rates": rates,
        "currencies": CURRENCIES,
        "selected_currency": selected_currency,
    })


# ════════════════════════════════════════════
#  АДМИН-ПАНЕЛЬ
# ════════════════════════════════════════════

@admin_required
def admin_panel_view(request):
    users = User.objects.all().order_by("-date_joined").select_related("profile")
    for u in users:
        get_or_create_profile(u)
    users = User.objects.all().order_by("-date_joined").select_related("profile")
    return render(request, "admin_panel.html", {"users": users})


@admin_required
def admin_change_role_view(request, user_id):
    if request.method == "POST":
        target_user = get_object_or_404(User, id=user_id)
        if target_user != request.user:
            profile = get_or_create_profile(target_user)
            new_role = request.POST.get("role")
            if new_role in ["user", "admin"]:
                profile.role = new_role
                profile.save()
    return redirect("/admin-panel/")


@admin_required
def admin_delete_user_view(request, user_id):
    if request.method == "POST":
        target_user = get_object_or_404(User, id=user_id)
        if target_user != request.user:
            target_user.delete()
    return redirect("/admin-panel/")