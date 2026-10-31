# LabCloud Render орналастыруы

Жария URL: https://labcloud-q2il.onrender.com

## Автоматты жариялау

GitHub development тармағында код өзгертіледі. Pull Request үшін main branch protection міндетті `Test and build` тексеруін талап етеді. Ол Ruff, pytest, PostgreSQL интеграциясын, Docker build және контейнердегі HTTP сұрауларын орындайды. PR тек тексеру өткен соң main-ға біріктіріледі.

`render.yaml` ішіндегі `autoDeployTrigger: checksPass` арқылы Render main тармағындағы CI аяқталғанын күтеді. Қате CI өзгерісті автоматты жариялауға өткізбейді. Blueprint Auto Sync қосулы болуы керек. Blueprint конфигурациясының өзгерісі ресурс sync жасай алатындықтан, render.yaml да міндетті тексерілген PR арқылы өзгереді.

Render үшін қосымша GitHub API secret қажет емес. `scripts/deploy_render.py` балама қолмен/API басқаруға арналған; ол қазіргі автоматты жолда қолданылмайды. CI-де жария URL-ді күтетін job жоқ: ол Render күтіп тұрған checks тізімін тұйық циклге түсірмеуі үшін тексеру жариялаудан кейін бөлек орындалады.

## Орта және сервер

APP_ENV=production, STORAGE_BACKEND=database. DATABASE_URL PostgreSQL байланысынан Blueprint арқылы алынады, кодта сақталмайды. APP_VERSION Blueprint арқылы нұсқа белгісін береді; source commit revision өрісінен тәуелсіз тексеріледі. Нақты source commit `/` жауабының revision өрісінен тексеріледі. instance — Render instance идентификаторы; ауысуы қайта іске қосылған жаңа ортаны дәлелдеуге көмектеседі.

Gunicorn 0.0.0.0:${PORT:-8000} адресіне байланады. Docker CMD автоматты қолданылады. Health check — /health. Logs — Render service Logs. Web контейнері UID 10001 қолданады. Web жоспары және PostgreSQL жоспары — Free; қосымша ақылы ресурс жасалмайды.

## Нақты сыртқы тексеру

```powershell
.\.venv\Scripts\python.exe scripts/verify_http.py --url https://labcloud-q2il.onrender.com --public --count 75 --output evidence/public.json
```

Тексеру бір сынақ өтінімін жасайды, оның ID-сін қайта оқиды, қате деректерді және 75 тізбекті health сұрауын тексереді. evidence/cloud-persistence-before.json және cloud release дәлелдері бастапқы өтінімнің жаңа deploy-дан кейін де сақталуын көрсетеді.

## Шектеулер және ресурстар

Free web ұйқы режиміне өте алады. Free PostgreSQL 30 күннен кейін мерзімі бітуі мүмкін. Оқу API-і аутентификациясыз; тек жасанды өтінімдерге арналған. Тексеруден кейін ресурс қажет болмаса Render Dashboard-та Suspend жасаңыз; дерек керек болса DB-ні жоймас бұрын экспорттаңыз.

## Ресми дереккөздер

- [Render CI және deploy](https://render.com/docs/deploys)
- [Blueprint autoDeployTrigger](https://render.com/docs/blueprint-spec)
- [Blueprint sync](https://render.com/docs/infrastructure-as-code)
- [Revision және instance айнымалылары](https://render.com/docs/environment-variables)
- [Free жоспар шектеулері](https://render.com/docs/free)
