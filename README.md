# LabCloud зертханалық жұмыс 7

Зертханалық жабдықтарға өтінім тіркейтін Flask REST API. Негізгі код, қосымша тестілер, Docker, PostgreSQL, CI/CD, A–E талдауы және тәжірибе дәлелдері осы папкада.

## Жергілікті іске қосу

PowerShell терминалында:

```powershell
cd "$env:USERPROFILE\Desktop\labcloud"
.\.venv\Scripts\python.exe app.py
```

Немесе `scripts/run.ps1` пайдаланыңыз. Ол Windows үшін тек `127.0.0.1:8000` адресіне байлайды. Контейнерде және PaaS-та Gunicorn `0.0.0.0:$PORT` қолданады. Gunicorn Linux ортасына арналған, Windows-та `python app.py` жергілікті сынақ үшін қолданылады. Debug өшірілген.

Браузер: http://127.0.0.1:8000/health

Жаңа компьютерде: `python -m venv .venv`, содан кейін `.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`. `.env.example` тек үлгі; `.env` автоматты оқылмайды. Айнымалыларды `$env:NAME='value'` арқылы беріңіз.

## API

| Әдіс | Жол | Нәтиже |
|---|---|---|
| GET | `/` | Қосымша, орта, күй, нұсқа; 200 |
| GET | `/health` | healthy; 200, DB қолжетімсіз болса 503 |
| GET | `/api/requests` | Өтінімдер тізімі; 200 |
| POST | `/api/requests` | Жаңа өтінім; 201 немесе 400 |
| GET | `/api/requests/<id>` | Өтінім; 200 немесе 404 |

```powershell
$body = @{title='Желіні тексеру'; category='network'; priority='high'; description='Байланысты тексеру'} | ConvertTo-Json
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/requests' -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod 'http://127.0.0.1:8000/api/requests'
```

`category`: computer, network, software. `priority`: low, medium, high. `title`: бос емес, ең көбі 120 таңба. `description`: мәтін, ең көбі 1000 таңба, міндетті емес. Қате типтер, соның ішінде category/priority массивтері де 400 қайтарады. Сұрау денесі 16 KiB-тан үлкен болса 413.

## Тестілеу және дәлелдер

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe scripts/run_local_experiments.py
```

`evidence/` ішіндегі JSON және журналдар нақты орындалған тексерулерді сақтайды. Бұл папка репозиторийге кірмейді. Негізгі тестілерден бөлек, әдейі қате тест жеке evidence файлында орындалады. Оның exit code 1 болуы күтіледі.

## Docker

```powershell
docker build -t labcloud:1.0 .
docker run --rm -p 127.0.0.1:8000:8000 -e APP_ENV=container labcloud:1.0
docker ps
docker logs <container_id>
```

Автоматты тексеру: `scripts/test-container.ps1`. Жергілікті Docker жоқ болса, GitHub Actions Ubuntu runner бейнені құрастырып, контейнерді іске қосады, UID және нақты HTTP сұрауларын тексереді. Контейнер тоқтағанша SQLite сақталады; контейнер жойылып қайта жасалса, volume-сыз жоғалады.

PostgreSQL бар толық орта:

```powershell
# Құпия мәнді өзіңіз орнатыңыз; бұл мәнді файлға не Git-ке жазбаңыз.
$env:POSTGRES_PASSWORD = Read-Host 'PostgreSQL password'
docker compose up --build -d
docker compose restart web
docker compose logs web
docker compose stop
```

DB порты хостқа ашылмайды; тек web порты localhost-қа жарияланады. Compose-та read-only web, tmpfs, cap_drop ALL және no-new-privileges бар. DB volume `labcloud-pg` контейнер қайта жасалғанда да сақталады. `docker compose down -v` деректерді жояды, оны сақтағыңыз келсе қолданбаңыз.

## GitHub және PaaS

Орналастыруға Render таңдалған. `render.yaml` — Docker web service және сыртқы PostgreSQL үлгісі; автоматты deploy өшірілген. CI/CD тесттен кейін дәл тексерілген commit SHA-ны Render API арқылы жариялайды, `live` күйін күтеді және public API-ді тексереді.

Баптау нұсқаулығы: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). A–E талдауы мен сызбалар: [docs/TASKS_A_E.md](docs/TASKS_A_E.md). Нақты орындалу күйі: жергілікті `Есеп.md` және `evidence/status.json`.

Бұл оқу API-і аутентификациясыз жұмыс істейді. Тек жасанды зертханалық өтінімдерді пайдаланыңыз.
