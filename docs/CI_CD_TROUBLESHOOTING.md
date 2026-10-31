# Автоматты жариялау диагностикасы

## CI сәтті бірақ Render жаңа нұсқаны ашпайды

Бұл зертханада main CI өткенмен, Render-де жаңа deploy оқиғасы пайда болмаған жағдай байқалды. Жария API жұмысын жалғастырды; оның revision өрісі бұрынғы commit-ті көрсетті. Бұл API кодының сәтсіздігі емес, жеткізу байланысын тексеру қажет екенін көрсетті. Git provider байланысы сол сәтте басқару беті арқылы тексерілген жоқ, сондықтан бастапқы себеп нақты расталды деп көрсетілмейді.

Render ресми құжаттамасына сай Public Git Repository URL және байланысқан Git Provider екі бөлек тәсіл. Автоматты жариялау үшін байланысқан Git Provider қажет.

1. Render Account Settings → Account Security → Git Deployment Credentials ішінде GitHub байланысын тексеріңіз.
2. Render GitHub App осы `Arujan7122/labcloud-lab7` репозиторийіне қол жеткізуі керек. Тек қажетті репозиторийді таңдаңыз.
3. labcloud Settings ішінде тиісті Git Credentials, main тармағы және Auto-Deploy = After CI Checks Pass таңдалсын.
4. Blueprint Settings → Auto Sync = Yes болсын. Blueprint конфигурациясын тек тексерілген PR арқылы өзгертіңіз.
5. Байланыс жөнделгеннен кейін жаңа тексерілген commit жіберіп, CI аяқталуын және Render Deploys/Events оқиғасын бақылаңыз. Бұрын аяқталған check үшін жаңа автоматты оқиға бірден тумаса, жаңа push арқылы толық ағынды тексеріңіз.

## Нәтижені дәлелдеу

Жария `/` жауабындағы revision GitHub main SHA-мен сәйкес болуы керек. Тек version мәтінін өзгерту жаңа код жарияланғанын өздігінен дәлелдемейді. instance идентификаторы өзгерсе, жаңа Render instance ашылғанын көрсетеді.

Қайта іске қосу алдында `scripts/check_persistence.py --url https://labcloud-q2il.onrender.com` арқылы snapshot жасаңыз. Кейін сол snapshot-пен `--check` орындаңыз. JSON нәтижесінде бұрынғы өтінімнің ID-і мен барлық өрісі сақталуы тиіс.

## Ресми дереккөздер

- https://render.com/docs/git-provider
- https://render.com/docs/deploys
- https://render.com/docs/infrastructure-as-code
- https://render.com/docs/environment-variables
