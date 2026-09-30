# DNTSNE Hit & Blow Online 2.1 — чистая версия

Игра на Python/Flet с офлайн-тренировкой и онлайном 1×1. Интерфейс полностью
на японском. В онлайне у каждого игрока собственное задание, а выигрывает тот,
чей правильный ответ первым получил сервер.

Это чистая версия исходников без учебных комментариев. Визуальный стиль —
чёрный/белый/бежевый, логотип и watermark
`DNTSNE — DeadNeuronsThatShouldNeverExist`. Кастомная загрузочная картинка
лежит в `assets/icons/loading-animation.png`.

## Что реализовано

- быстрый поиск соперника с подбором по количеству цифр;
- приватные комнаты с шестизначным кодом;
- split-screen: слева полный лог соперника, справа свой лог и ввод;
- серверная проверка всех попыток и защита секретов от клиента;
- анимации переходов, появления попыток, ошибки ввода и результата;
- рейтинг побед и лучших результатов в SQLite;
- сохранён одиночный режим без подключения к серверу;
- единый ASGI-процесс: Flet-сайт, FastAPI и WebSocket API.

Правила: от 3 до 8 цифр, цифры в секрете и попытке не повторяются.

## Локальный запуск сайта и сервера

Требуется Python 3.12+.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python server.py
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```

Открыть `http://127.0.0.1:8000`. Для проверки онлайна достаточно открыть
сайт в двух разных браузерах или в обычном и приватном окне.

## Запуск как desktop-клиент

Сначала должен работать `server.py` — локально или на удалённом сервере.

```powershell
$env:GAME_WS_URL="wss://game.example.com/api/ws"
python launch.py
```

Без `GAME_WS_URL` клиент подключается к `ws://127.0.0.1:8000/api/ws`.
Если сервер недоступен, одиночная тренировка всё равно работает.

## Docker

```bash
docker build -t hit-and-blow .
docker run --name hit-and-blow -p 8000:8000 -v hit-and-blow-data:/app/data hit-and-blow
```

Проверка: `http://127.0.0.1:8000/health`.

## Cloudflare

Это динамическое Python-приложение, поэтому ему нужен origin с постоянно
работающим контейнером или процессом. Cloudflare ставится перед ним как DNS,
HTTPS/WSS-прокси или Tunnel.

Пример маршрута Cloudflare Tunnel:

```yaml
ingress:
  - hostname: game.example.com
    service: http://localhost:8000
  - service: http_status:404
```

После привязки домена сайт доступен через `https://game.example.com`, а игровой
канал — через `wss://game.example.com/api/ws`. На серверном веб-запуске
`GAME_WS_URL` менять не требуется: Flet-сессии обращаются к API через localhost.

Запускайте Uvicorn с одним worker. Комнаты и быстрый поиск находятся в памяти
процесса; SQLite хранит только рейтинг. Для горизонтального масштабирования
нужно вынести состояние матчей в Redis.

## Структура

- `launch.py` — Flet GUI, экраны, анимации и обработка событий;
- `generators.py` — общие правила Hit & Blow;
- `network.py` — асинхронный WebSocket-клиент;
- `game_core.py` — модель матча и SQLite-рейтинг;
- `game_server.py` — комнаты, быстрый поиск и синхронизация;
- `server.py` — единая точка запуска сайта и сервера;
- `tests/` — тесты правил и онлайн-сценариев.

## Тесты

```bash
python -m unittest discover -s tests -v
```
