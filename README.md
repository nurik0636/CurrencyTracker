# 💰 CurrencyTracker

Веб-приложение для отслеживания курсов валют в реальном времени, построенное на Django.

---

## 📌 Описание проекта

**CurrencyTracker** — это сервис мониторинга валютных курсов (USD/KZT, USD/EUR, USD/RUB) с возможностью конвертации, настройки Telegram-уведомлений и управления пользователями.

---

## ⚙️ Стек технологий

| Технология | Назначение |
|---|---|
| Python 3.14 | Основной язык |
| Django 5.x | Web-фреймворк |
| SQLite | База данных |
| Chart.js | Графики курсов |
| Bootstrap 5 | UI-компоненты |
| Telegram Bot API | Уведомления об алертах |
| ExchangeRate API | Источник курсов валют |

---

## 🗂️ Структура проекта

```
CurrencyTracker/
├── currency_tracker/        # Основной конфиг Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── rates/                   # Главное приложение
│   ├── models.py            # Модели: Currency, UserProfile, AlertSetting
│   ├── views.py             # Все представления
│   ├── urls.py              # Маршруты
│   ├── services.py          # Парсер курсов, Telegram, аналитика
│   └── templates/           # HTML-шаблоны
│       ├── index.html
│       ├── converter.html
│       ├── settings.html
│       ├── profile.html
│       ├── history.html
│       ├── admin_panel.html
│       ├── login.html
│       └── register.html
├── manage.py
└── requirements.txt
```

---

## 🚀 Установка и запуск

### 1. Клонировать репозиторий

```bash
git clone https://github.com/ВАШ_ЛОГИН/CurrencyTracker.git
cd CurrencyTracker/currency_tracker
```

### 2. Создать виртуальное окружение

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Настроить переменные окружения

Создай файл `.env` в корне проекта:

```env
SECRET_KEY=ваш_секретный_ключ
DEBUG=True
TELEGRAM_BOT_TOKEN=токен_вашего_бота
```

### 5. Применить миграции

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Создать суперпользователя

```bash
python manage.py createsuperuser
```

### 7. Запустить сервер

```bash
python manage.py runserver
```

Открыть в браузере: http://127.0.0.1:8000

---

## 📋 Функциональность

### 🏠 Главная страница
- Карточки актуальных курсов USD/KZT, USD/EUR, USD/RUB
- Изменение курса за последние 24 часа
- Прогноз на завтра (среднее за неделю)
- Тренд (Растёт / Падает / Стабильно)
- Интерактивный график с фильтрами по периоду (День / Неделя / Месяц / Всё)
- Гостевой доступ — курсы видны без регистрации

### 🔢 Конвертер валют
- Конвертация между USD, KZT, EUR, RUB
- Учёт комиссии (%)
- Отображение использованного курса

### 🔔 Настройки уведомлений
- Создание алертов по условию (выше / ниже порога)
- Отправка уведомлений в Telegram при срабатывании
- Управление активными алертами

### 👤 Профиль пользователя
- Просмотр данных аккаунта
- Редактирование логина и email
- Смена пароля
- История запросов курсов

### 🛡️ Админ-панель
- Список всех пользователей
- Изменение ролей (User / Admin)
- Удаление пользователей

---

## 🗄️ Модели базы данных

### Currency
Хранит историю курсов валют.

| Поле | Тип | Описание |
|---|---|---|
| name | CharField | Название пары (напр. USD/KZT) |
| value | FloatField | Значение курса |
| date | DateTimeField | Дата и время записи |
| user | ForeignKey | Владелец записи |

### UserProfile
Расширение стандартного User.

| Поле | Тип | Описание |
|---|---|---|
| user | OneToOneField | Связь с User |
| role | CharField | Роль: user / admin |

### AlertSetting
Настройки Telegram-уведомлений.

| Поле | Тип | Описание |
|---|---|---|
| currency | CharField | Код валюты (KZT, EUR, RUB) |
| threshold | FloatField | Пороговое значение |
| direction | CharField | above / below |
| telegram_chat_id | CharField | Chat ID в Telegram |
| is_active | BooleanField | Активен ли алерт |

---

## 🔗 Маршруты (URLs)

| URL | Описание |
|---|---|
| / | Главная — курсы валют |
| /update/ | Обновить курсы |
| /converter/ | Конвертер валют |
| /history/ | История запросов |
| /settings/ | Настройки алертов |
| /profile/ | Профиль пользователя |
| /profile/edit/ | Редактирование профиля |
| /admin-panel/ | Панель администратора |
| /login/ | Вход |
| /logout/ | Выход |
| /register/ | Регистрация |

---

## 📦 Зависимости

```
django>=5.0
requests>=2.31
python-dotenv>=1.0
```

---

## 👨‍💻 Автор

Проект разработан в рамках учебного курса по веб-разработке.
