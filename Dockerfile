# Image du worker RénoBoost (exécution des runs) — déployée sur Railway.
# Déterministe et indépendant du builder Railway : on copie tout le source
# puis on installe le moteur en NON-éditable, ce qui évite l'erreur
# « egg_base : 'src' does not exist » provoquée par le `-e .` du requirements racine.
FROM python:3.11-slim

WORKDIR /app
COPY . /app

# requests (worker, mode demo) + le moteur renoboost_leads (mode real).
RUN pip install --no-cache-dir -r worker/requirements.txt \
 && pip install --no-cache-dir .

CMD ["python", "-m", "worker"]
