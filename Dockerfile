# Utilise une version légère de Python
FROM python:3.11-slim

# Définit le dossier de travail dans le conteneur
WORKDIR /app

# Installe les dépendances système nécessaires pour XGBoost et Pandas
# (libgomp1 est crucial pour XGBoost sur les images slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copie et installe les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie tout le code du projet dans le conteneur
COPY . .

# Crée le dossier pour la base de données
RUN mkdir -p data

# Par défaut, on ne lance rien ici, c'est Docker Compose qui décidera (Backend ou Bot)