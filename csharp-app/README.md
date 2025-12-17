# Mockups (ASP.NET Core MVC)

Учебное веб-приложение на **ASP.NET Core MVC (Razor Views)**: меню, корзина, оформление заказа, регистрация/логин (Identity), роли.

Проект используется как база для задания по улучшению кода с применением AI:
- Unit-тесты
- Нагрузочное тестирование
- Документация и рефакторинг
- (опционально) аналитические эндпоинты и CI/CD

---

## Возможности

- Просмотр меню (анонимно)
- Регистрация / вход / выход
- Добавление блюд в корзину (для авторизованных)
- Оформление заказа
- Скидки (по правилам проекта: например, ланч / день рождения)
- Админ-действия (если пользователь имеет роль администратора)

---

## Технологии

- .NET 6
- ASP.NET Core MVC + Razor Views
- Entity Framework Core
- ASP.NET Core Identity
- SQL Server (рекомендуется запуск в Docker)
- Тесты: xUnit, Moq, SQLite (in-memory) для EF-тестов
- Нагрузка: k6 (+ генерация HTML-отчётов из JSON)

---

## Структура репозитория

- `Mockups/` — приложение  
  - `Controllers/` — MVC контроллеры  
  - `Services/` — бизнес-логика  
  - `Repositories/` — доступ к данным  
  - `Storage/` — сущности, DbContext, Identity-модели  
  - `Views/` — Razor Views  
  - `Migrations/` — миграции EF Core  
  - `Configs/` — конфиги приложения  
- `Mockups.Tests/` — тесты  
  - `TestSupport/` — фикстуры/сидеры/хелперы для тестов  
- `loadtest/` — нагрузочные сценарии и генерация отчётов

---

## Быстрый старт

### Требования

- .NET SDK 6.x
- Docker Desktop (для БД)

### 1) Запуск SQL Server в Docker

```bash
docker run -d --name hits-sql   -e "ACCEPT_EULA=Y"   -e "MSSQL_SA_PASSWORD=Str0ngPassw0rd!123"   -p 1433:1433   mcr.microsoft.com/mssql/server:2022-latest
```

Проверка статуса:

```bash
docker ps --filter "name=hits-sql"
```

### 2) Настроить строку подключения

Проверь `Mockups/appsettings.Development.json` (или `appsettings.json`) и укажи корректный connection string.

Пример:

```json
{
  "ConnectionStrings": {
    "Default": "Server=localhost,1433;Database=Mockups;User Id=sa;Password=Str0ngPassw0rd!123;TrustServerCertificate=True;"
  }
}
```

> Важно: **LocalDB на macOS не поддерживается**. Используй SQL Server в Docker/удалённый SQL Server.

### 3) Запустить приложение

```bash
cd Mockups
dotnet restore
dotnet run
```

По умолчанию приложение слушает два адреса (пример):
- `http://localhost:5146`
- `https://localhost:7146`

---

## Тесты

Запуск всех тестов:

```bash
dotnet test
```

---

## Нагрузочное тестирование

Сценарии находятся в `loadtest/scripts/scenarios/`.

Пример запуска набора сценариев и генерации отчёта:

```bash
cd loadtest
ENGINE=docker BASE_URL=http://host.docker.internal:5146 MODE=baseline ./run_all.sh
./make_report.sh
```

Артефакты сохраняются в `loadtest/out/`.

---

## Маршруты (основные)

Swagger не подключён, т.к. проект — MVC + Razor. Основные страницы:

- `GET /Menu/Index` — меню (анонимно)
- `GET /Account/Register` — регистрация
- `GET /Account/Login` — вход
- `POST /Account/Login` — отправка формы входа
- `GET|POST /Account/Logout` — выход (зависит от реализации)
- `GET /Menu/AddToCart/{id}` — добавить в корзину (нужна авторизация)
- `GET /Orders/Create` — оформление заказа (нужна авторизация)
- `POST /Orders/Create` — создать заказ (нужна авторизация)

Подробности — в `[docs/TECHNICAL.md](https://github.com/msLoginoff/hits-docker-practice-AI/blob/master/csharp-app/docs/TECHNICAL.md#technical-description--mockups)`.

---

## Лицензия

Учебный проект. Использование — в рамках курса/практики.
