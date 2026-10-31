# GitHub және Render орналастыру тәртібі

Бұл файл конфигурация қадамдарын түсіндіреді. Нақты орындалған әрекеттер мен сілтемелер `evidence/status.json` және есепте көрсетіледі.

## GitHub

1. `main` және `development` тармақтарын remote-қа жүктеу.
2. Development-та өзгерту, Pull Request ашу, `Test and build` нәтижесін күту.
3. `main` branch protection: require pull request, require status check `Test and build`, strict up-to-date, enforce administrators, force push пен deletion-ды өшіру.
4. Қате тест бар commit CI-ді қызыл етуі тиіс; содан кейін түзетілген commit жасыл болғанда PR біріктіріледі. `needs: test` deploy-ды тесттен кейін ғана орындайды. Render-де бөлек On Commit auto-deploy қосылмауы керек, өйткені ол CI қақпасын айналып өтуі мүмкін.

## Render

1. GitHub аккаунтын Render-ге байланыстырып, осы репозиторийден New Blueprint жасаңыз. `render.yaml` таңдалады. Free web және Free PostgreSQL жоспарын тексеріңіз; төлемді жоспарды келісімсіз таңдамаңыз.
2. Web service: Dockerfile, branch main, health check `/health`, `APP_ENV=production`, `STORAGE_BACKEND=database`, `APP_VERSION=1.1.0`. `DATABASE_URL` Blueprint арқылы DB-ден құпия байланыс ретінде беріледі.
3. Render `PORT` бергенде Docker CMD оны қолданады. Егер startup override қажет болса: `gunicorn --bind 0.0.0.0:$PORT --workers 2 --access-logfile - --error-logfile - app:app`.
4. Render service ID мен нақты HTTPS URL-ді алыңыз. GitHub Settings → Environments → production ішіне secret `RENDER_API_KEY`, variables `RENDER_SERVICE_ID`, `PUBLIC_URL` орнатыңыз. Токенді чатқа, Git-ке немесе `.env` файлын жүктеу арқылы жібермеңіз.
5. Repository variable `RENDER_DEPLOY_ENABLED=true` орнатыңыз. Ол жоқ кезде remote deploy job әдейі іске қосылмайды; бұл жариялау аяқталды дегенді білдірмейді.
6. Main-ға тексерілген commit жүктелгенде workflow `scripts/deploy_render.py` арқылы сол SHA-ны жариялайды. Скрипт API-дің 201 жауабымен шектелмей, `live` күйін күтеді. Кейін `scripts/verify_http.py --public` сыртқы URL-ге нақты сұраулар жібереді.
7. Логтар: Render → service → Logs; оқиғалар: Events/Deploys. GitHub Actions артефактісінен `public-evidence` жүктеңіз.

Жария API-ді қолмен тексеру:

```powershell
$env:PUBLIC_URL = Read-Host 'Render HTTPS URL'
.\.venv\Scripts\python.exe scripts/verify_http.py --public --count 75 --output evidence/public.json
```

Бұл скрипт сынақ өтінімін жасайды, сәтті POST/GET, 400/404 жағдайларын және 75 health сұрауын дәлел ретінде сақтайды. URL берілмесе не нәтиже қате болса, тексеру сәтсіз аяқталады.

## A және қайта орналастыру дәлелі

Жария API-де жаңа өтінім жасаңыз, ID мен толық JSON-ды evidence-ке сақтаңыз. Render-де Restart service орындап, `/health` 200 болған соң сол ID-ді қайта оқыңыз. Одан кейін жаңа нұсқаны main PR арқылы жариялап, нұсқаны және бұрынғы ID-ді қайта тексеріңіз. Бұл PostgreSQL арқылы restart/redeploy кезіндегі сақталуды дәлелдейді. Жергілікті SQLite тәжірибесі бұлттық PostgreSQL дәлелін алмастырмайды.

## D диагностикасы

Өндірістік емес жеке тест сервисінде, оқытушы келісімінен кейін ғана startup target-ті `labcloud_typo:app` етіп ауыстырыңыз. Логтағы ModuleNotFoundError-ды тіркеңіз, `app:app` етіп түзетіп, `/health` 200 екенін сақтаңыз. Жергілікті қауіпсіз баламасы `scripts/run_local_experiments.py` ішінде орындалған.

## Ресурстарды тоқтату

Тексеруден кейін тест сервисін Render Dashboard-та Suspend етіңіз. Қажет болмаса, DB-ні экспорттап алып жойыңыз. Free PostgreSQL мерзімі 30 күн; free web ұйқы режиміне өте алады. Жергілікті Docker ресурстарына `docker compose stop` қолданыңыз.

## Ресми дереккөздер

- [Flask on Render](https://render.com/docs/deploy-flask)
- [Blueprint specification](https://render.com/docs/blueprint-spec)
- [Health checks](https://render.com/docs/health-checks)
- [Trigger deploy API](https://api-docs.render.com/reference/create-deploy)
- [Retrieve deploy API](https://api-docs.render.com/reference/retrieve-deploy)
- [Free plan limits](https://render.com/docs/free)
- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
