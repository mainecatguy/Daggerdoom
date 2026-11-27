# Triage agent reports so questions and oversights are not missed

Waiting on: the owner picking this up.

Owner (2026-11-27): "we need a backlog item to check reports for qs are these getting a quality review and flags as
well are there any of those that were missed".

Found 2026-11-27: `work/agent-reports/` holds 93 untriaged run files from 2026-11-25 to 2026-11-27, with 200 questions
and 118 suspected oversights. `work/orchestrator.md` says the orchestrator triages them (merge duplicates, drop answered
or minor ones, send design questions through the game designer's answer and challenge passes, then move real owner
decisions to `work/questions.md` and major problems to `work/suspectedoversights.md`). This hasn't been happening,
so questions such as Speed and climbing reached the owner late or not at all.

Open: a one-time triage of the backlog of reports, and a routine so new reports are triaged as lanes finish (for
example, each merge or lane result triggers triage of that run's report file).