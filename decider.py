"""Decide s'il faut remonter les annonces maintenant (2 fois par jour, apres 9h30 et 15h30, heure de Paris)."""
import json, os, sys, urllib.request
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
HORAIRES = [time(9, 30), time(15, 30)]   # heures de remontee voulues
ECART_MIN = timedelta(hours=3)           # ecart minimum entre deux remontees
JOB = "remonter"


def api(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "decider-remontee",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def remontees_du_jour(debut_jour_utc):
    repo = os.environ["GITHUB_REPOSITORY"]
    since = debut_jour_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    runs = api(f"https://api.github.com/repos/{repo}/actions/workflows/remonte.yml/runs"
               f"?created=%3E%3D{since}&per_page=100").get("workflow_runs", [])
    faites = []
    for run in runs:
        if run.get("conclusion") != "success":
            continue
        for job in api(run["jobs_url"]).get("jobs", []):
            if job.get("name") == JOB and job.get("conclusion") == "success" and job.get("completed_at"):
                faites.append(datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00")))
    return sorted(faites)


def decide(now, faites, manuel=False):
    if manuel:
        return True, "lancement manuel"
    dues = sum(1 for h in HORAIRES if now.time() >= h)
    if len(faites) >= dues:
        return False, f"rien a faire ({len(faites)} remontee(s) faite(s), {dues} prevue(s) a cette heure)"
    if faites and now - faites[-1].astimezone(PARIS) < ECART_MIN:
        return False, "derniere remontee trop recente, on attend"
    return True, f"remontee n°{len(faites) + 1} du jour"


def main():
    now = datetime.now(PARIS)
    manuel = os.environ.get("EVENT") == "workflow_dispatch"
    faites = [] if manuel else remontees_du_jour(
        datetime.combine(now.date(), time(0, 0), PARIS).astimezone(timezone.utc))
    go, pourquoi = decide(now, faites, manuel)
    print(f"{now:%d/%m %H:%M} (Paris) -> {'ON REMONTE' if go else 'on attend'} : {pourquoi}")
    with open(os.environ.get("GITHUB_OUTPUT", os.devnull), "a") as f:
        f.write(f"go={'1' if go else '0'}\n")


if __name__ == "__main__":
    main()
