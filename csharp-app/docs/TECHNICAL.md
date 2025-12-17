# Technical Description — Mockups

Документ описывает устройство проекта, запуск, конфигурацию и основные маршруты приложения.

---

## 1. Назначение проекта

Mockups — учебное приложение на ASP.NET Core MVC (Razor Views) с функционалом:
- меню
- корзина
- оформление заказа
- авторизация/регистрация (ASP.NET Core Identity)
- роли (например, администратор)

---

## 2. Архитектура

Проект использует классическую MVC-архитектуру и разделён на уровни:

### 2.1 UI (Controllers + Views)
- `Controllers/` — принимает запросы, вызывает сервисы, возвращает View/Redirect
- `Views/` — Razor Views (страницы)

### 2.2 Бизнес-логика (Services)
- `Services/` — операции уровня приложения (меню, корзина, заказы, пользователи и т.д.)
- Сервисы скрывают детали хранения и упрощают контроллеры

### 2.3 Данные (Repositories + EF Core)
- `Repositories/` — инкапсулируют работу с DbContext (запросы и сохранение)
- `Storage/` — EF Core сущности, DbContext, Identity-модели

---

## 3. Данные и база

### 3.1 База данных
Основная БД: SQL Server.

На macOS нельзя использовать SQL LocalDB, поэтому рекомендуется SQL Server в Docker или удалённый SQL Server.

### 3.2 Миграции
Схема базы описана миграциями в `Migrations/`.
Фактический способ применения миграций/создания схемы зависит от кода запуска приложения.

---

## 4. Аутентификация и авторизация

Используется ASP.NET Core Identity:
- регистрация
- логин/логаут
- роли

Часть действий (корзина, оформление заказа, админ-операции) требует авторизации.

---

## 5. Запуск

### 5.1 Запуск SQL Server в Docker

```bash
docker run -d --name hits-sql   -e "ACCEPT_EULA=Y"   -e "MSSQL_SA_PASSWORD=Str0ngPassw0rd!123"   -p 1433:1433   mcr.microsoft.com/mssql/server:2022-latest
```

Проверка статуса:

```bash
docker ps --filter "name=hits-sql"
```

### 5.2 Строка подключения

Файл: `Mockups/appsettings.Development.json` (или `appsettings.json`)

Ключ: `ConnectionStrings:Default`

Пример:

```json
{
  "ConnectionStrings": {
    "Default": "Server=localhost,1433;Database=Mockups;User Id=sa;Password=Str0ngPassw0rd!123;TrustServerCertificate=True;"
  }
}
```

### 5.3 Запуск приложения

```bash
cd Mockups
dotnet restore
dotnet run
```

Обычно приложение слушает:
- `http://localhost:5146`
- `https://localhost:7146`

---

## 6. Основные маршруты (Web UI)

Проект — MVC + Razor, поэтому документируются основные страницы/маршруты.

### 6.1 Публичные страницы (анонимно)
- `GET /Menu/Index` — меню
- `GET /Account/Register` — регистрация
- `GET /Account/Login` — вход

### 6.2 Для авторизованных пользователей
- `GET /Menu/AddToCart/{id}` — добавить позицию в корзину
- `GET /Orders/Create` — страница оформления заказа
- `POST /Orders/Create` — создание заказа

### 6.3 Выход
- `GET|POST /Account/Logout` — зависит от реализации контроллера

---

## 7. Тестирование

Проект тестов: `Mockups.Tests/`

Используется:
- xUnit
- Moq
- SQLite in-memory для EF Core тестов, где важны FK/constraints

Запуск:

```bash
dotnet test
```

---

## 8. Нагрузочное тестирование

Директория: `loadtest/`

Инструмент: k6. Сценарии создают нагрузку на страницы/потоки действий (анонимно/с авторизацией) и собирают метрики:
- RPS
- latency (avg, p95)
- error rate

Запуск:

```bash
cd loadtest
ENGINE=docker BASE_URL=http://host.docker.internal:5146 MODE=baseline ./run_all.sh
./make_report.sh
```

Артефакты сохраняются в `loadtest/out/`.
