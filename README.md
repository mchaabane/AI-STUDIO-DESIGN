# 🎨 Personal Design AI

> **Un atelier de conception web assisté par IA locale, conçu pour
> générer des interfaces qui respectent le langage visuel du designer.**

Personal Design AI transforme une idée exprimée en langage naturel en
interface web **HTML/CSS**, tout en s'appuyant sur une **mémoire de
design personnelle** pour conserver les choix visuels de l'utilisateur.

L'objectif n'est pas seulement de générer une page web, mais de
permettre à l'IA de mieux comprendre progressivement les **couleurs,
formes, compositions, composants et préférences visuelles** d'un
designer.

------------------------------------------------------------------------

## ✨ À quoi sert le projet ?

Le principe est simple :

``` text
💬 Une idée
   ↓
🧠 Analyse de la demande
   ↓
🎨 Mémoire de design personnelle
   ↓
🤖 IA locale
   ↓
🛠️ HTML / CSS généré
   ↓
👀 Interface prête à visualiser
```

Le designer peut ensuite demander des modifications en langage naturel
et conserver différentes versions de ses projets.

### Exemples

``` text
Crée une landing page pour un refuge animalier.
```

``` text
Ajoute un bouton "Nous contacter".
```

``` text
Supprime le menu vertical en double.
```

``` text
Ajoute un Scottish Fold dans la liste.
```

------------------------------------------------------------------------

## 🧠 Une IA qui apprend le contexte du designer

Le projet utilise une **librairie personnelle de références visuelles**.

``` text
design-library/
└── projets/
    ├── projet001/
    ├── projet002/
    └── projet003/
```

Ces références sont analysées afin de construire un profil de design
pouvant notamment contenir :

-   🎨 couleurs dominantes
-   ◼️ formes et compositions
-   🧩 structures et composants récurrents
-   📐 proportions
-   🌗 luminosité et densité visuelle
-   ✨ caractéristiques générales du style

Ces informations servent ensuite à enrichir le contexte transmis au
modèle.

> **L'objectif est de passer d'une IA qui génère un design générique à
> une IA qui comprend progressivement les préférences de son
> utilisateur.**

------------------------------------------------------------------------

# 🏗️ Architecture

``` text
                    👤 UTILISATEUR
                          │
                          ▼
                 ┌─────────────────┐
                 │    FRONTEND     │
                 │   React / Vite  │
                 └────────┬────────┘
                          │
                          ▼
                 ┌─────────────────┐
                 │     BACKEND     │
                 │     FastAPI     │
                 └───────┬─────────┘
                        /                        /                         ▼     ▼
             ┌──────────┐ ┌──────────────┐
             │ Mémoire  │ │ Ollama + Qwen│
             │  Design  │ │   IA locale  │
             └────┬─────┘ └──────┬───────┘
                  └────────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  HTML / CSS │
                    │  Validation │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │ Projet Web  │
                    │ + versions  │
                    └─────────────┘
```

------------------------------------------------------------------------

# 🛠️ Technologies

  Technologie                   Utilisation
  ----------------------------- -------------------------------------------------
  **Python**                    Backend et logique applicative
  **FastAPI**                   API et orchestration
  **React**                     Interface utilisateur
  **Vite**                      Environnement frontend
  **Ollama**                    Exécution locale du modèle
  **Qwen 3 8B**                 Modèle de langage
  **RAG / mémoire de design**   Contextualisation des générations
  **HTML / CSS**                Interfaces générées
  **HTTPX**                     Communication HTTP et validation des ressources

------------------------------------------------------------------------

# 📁 Structure du projet

``` text
design-ai-mvp/
│
├── backend/
│   └── app/
│       ├── main.py
│       ├── models.py
│       ├── storage.py
│       ├── ollama.py
│       ├── intelligence.py
│       ├── reasoner.py
│       ├── change_planner.py
│       ├── css_patcher.py
│       ├── design_analyzer.py
│       ├── design_memory.py
│       └── api/
│           ├── projects.py
│           └── generation.py
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       └── styles.css
│
├── design-library/
│   ├── design-profile.json
│   └── projets/
│
├── data/
│   └── projects/
│
└── README.md
```

------------------------------------------------------------------------

# 🚀 Installation

## 1. Prérequis

Le projet est actuellement prévu pour une utilisation locale sur macOS.

Installer :

-   Python **3.12+**
-   Node.js + npm
-   Ollama
-   Git *(optionnel)*

Vérifier :

### Dossier : peu importe

``` bash
python3 --version
node --version
npm --version
ollama --version
```

------------------------------------------------------------------------

## 2. Installer le backend

### Dossier : `/Users/chaabane/design-ai-mvp`

Créer l'environnement virtuel :

``` bash
python3 -m venv .venv
```

Activer l'environnement :

``` bash
source .venv/bin/activate
```

Mettre pip à jour :

``` bash
python -m pip install --upgrade pip
```

Installer les dépendances :

``` bash
pip install fastapi uvicorn httpx pydantic
```

Si un `requirements.txt` est fourni :

``` bash
pip install -r requirements.txt
```

Vérifier :

``` bash
python -c "import fastapi, httpx, pydantic; print('Backend OK')"
```

------------------------------------------------------------------------

# 💻 Installation du frontend

### Dossier : `/Users/chaabane/design-ai-mvp/frontend`

``` bash
npm install
```

------------------------------------------------------------------------

# 🤖 Installer Ollama

Personal Design AI utilise Ollama pour exécuter le modèle localement.

### Dossier : peu importe

``` bash
ollama --version
```

Télécharger le modèle :

``` bash
ollama pull qwen3:8b
```

Vérifier :

``` bash
ollama list
```

Le modèle attendu :

``` text
qwen3:8b
```

Ollama utilise normalement :

``` text
http://127.0.0.1:11434
```

------------------------------------------------------------------------

# 🎨 Préparer la mémoire de design

Ajouter les références visuelles dans :

``` text
design-library/projets/
```

Par exemple :

``` text
design-library/
└── projets/
    ├── projet001/
    │   ├── reference-01.png
    │   ├── reference-02.png
    │   └── reference-03.png
    │
    ├── projet002/
    │   └── ...
    │
    └── projet003/
        └── ...
```

Les références servent à construire le profil visuel utilisé par les
générations.

------------------------------------------------------------------------

# 🔍 Analyser les références

### Dossier : `/Users/chaabane/design-ai-mvp`

Activer l'environnement :

``` bash
source .venv/bin/activate
```

Puis lancer l'analyse :

``` bash
python3 -c "from backend.app.design_analyzer import analyze_design_library; print(analyze_design_library())"
```

Vérifier le profil :

``` bash
python3 -c "from backend.app.generator import load_design_profile; p=load_design_profile(); print('Profil chargé :', bool(p)); print('Projets analysés :', p.get('analysis', {}).get('total_projects'))"
```

Afficher le contexte de design :

``` bash
python3 -c "from backend.app.generator import load_design_profile, build_design_memory_context; p=load_design_profile(); print(build_design_memory_context(p))"
```

------------------------------------------------------------------------

# ✅ Vérifier le backend

### Dossier : `/Users/chaabane/design-ai-mvp`

``` bash
python3 -m py_compile backend/app/main.py
python3 -m py_compile backend/app/ollama.py
python3 -m py_compile backend/app/intelligence.py
python3 -m py_compile backend/app/reasoner.py
python3 -m py_compile backend/app/change_planner.py
python3 -m py_compile backend/app/design_analyzer.py
python3 -m py_compile backend/app/design_memory.py
python3 -m py_compile backend/app/api/projects.py
python3 -m py_compile backend/app/api/generation.py
```

Aucune sortie signifie normalement que la syntaxe est correcte.

------------------------------------------------------------------------

# ▶️ Lancer l'application

Pour une utilisation quotidienne, ouvrir **3 terminaux**.

## Terminal 1 --- Ollama

### Dossier : peu importe

``` bash
ollama serve
```

------------------------------------------------------------------------

## Terminal 2 --- Backend

### Dossier : `/Users/chaabane/design-ai-mvp`

``` bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

Backend :

**http://127.0.0.1:8000**

Documentation API :

**http://127.0.0.1:8000/docs**

------------------------------------------------------------------------

## Terminal 3 --- Frontend

### Dossier : `/Users/chaabane/design-ai-mvp/frontend`

``` bash
npm run dev
```

Frontend :

**http://localhost:5173**

------------------------------------------------------------------------

# 🧪 Premier test

Dans l'interface, essayer :

``` text
Crée une landing page moderne pour un refuge animalier.

Ajoute un grand titre "Adoptez votre compagnon",
un texte de présentation et un bouton "Voir les animaux".

Ajoute une grille de cartes avec des photos réalistes
d'animaux correspondant exactement à leur nom.

Respecte le style visuel de mes références de design.
```

------------------------------------------------------------------------

# 🖼️ Gestion des images

Lorsqu'une génération nécessite des images, le système :

``` text
Sujet demandé
     ↓
Recherche sémantique
     ↓
Vérification de l'URL
     ↓
Image valide
     ↓
Intégration dans le HTML
```

Si aucune image distante valide n'est disponible, un **fallback local**
est utilisé afin d'éviter les images cassées.

------------------------------------------------------------------------

# 🔄 Modifier un projet

Les modifications peuvent également être demandées en langage naturel.

Par exemple :

``` text
Ajoute un bouton "Nous contacter".
```

``` text
Ajoute un Scottish Fold dans la liste.
```

``` text
Supprime le menu vertical en double.
```

``` text
Change le titre principal.
```

Le système analyse la demande puis applique les changements au projet.

------------------------------------------------------------------------

# 📦 Projets et versions

Les projets sont conservés dans :

``` text
data/projects/
```

Exemple :

``` text
data/projects/
└── project_xxxxx/
    ├── version-1/
    │   └── index.html
    ├── version-2/
    │   └── index.html
    └── ...
```

Cela permet de conserver l'historique des générations et modifications.

------------------------------------------------------------------------

# ♻️ Mettre à jour la mémoire de design

Après avoir ajouté de nouvelles références :

### Dossier : `/Users/chaabane/design-ai-mvp`

``` bash
source .venv/bin/activate
python3 -c "from backend.app.design_analyzer import analyze_design_library; print(analyze_design_library())"
```

Puis :

``` bash
python3 -c "from backend.app.generator import load_design_profile; p=load_design_profile(); print('Profil chargé :', bool(p)); print('Projets analysés :', p.get('analysis', {}).get('total_projects'))"
```

Les prochaines générations utiliseront le profil actualisé.

------------------------------------------------------------------------

# 🧯 Dépannage

### ❌ « Impossible de contacter le backend »

Vérifier que FastAPI fonctionne.

**Dossier : `/Users/chaabane/design-ai-mvp`**

``` bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

------------------------------------------------------------------------

### ❌ Ollama ne répond pas

**Dossier : peu importe**

``` bash
ollama list
```

Si `qwen3:8b` n'est pas présent :

``` bash
ollama pull qwen3:8b
```

Puis :

``` bash
ollama serve
```

------------------------------------------------------------------------

### ❌ `ModuleNotFoundError`

Vérifier que l'environnement virtuel est actif :

**Dossier : `/Users/chaabane/design-ai-mvp`**

``` bash
source .venv/bin/activate
```

------------------------------------------------------------------------

### ❌ Erreur pendant une génération

Regarder les logs du terminal FastAPI.

Les messages commençant par :

``` text
[GENERATION]
```

permettent de suivre les différentes étapes de génération et de
validation.

------------------------------------------------------------------------

### ❌ Images cassées

Après une modification de `generation.py`, redémarrer le backend.

Vérifier également les logs liés à la recherche et à la validation des
images.

------------------------------------------------------------------------

# 🛑 Arrêter l'application

Dans chaque terminal :

``` text
Ctrl + C
```

------------------------------------------------------------------------

# ⚡ Démarrage rapide

Une fois l'installation terminée :

### Terminal 1

**Dossier : peu importe**

``` bash
ollama serve
```

### Terminal 2

**Dossier : `/Users/chaabane/design-ai-mvp`**

``` bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

### Terminal 3

**Dossier : `/Users/chaabane/design-ai-mvp/frontend`**

``` bash
npm run dev
```

Puis ouvrir :

**http://localhost:5173**

------------------------------------------------------------------------

# 🗺️ Roadmap

Le projet suit progressivement cette évolution :

``` text
Génération de sites
        ↓
Mémoire de design
        ↓
Compréhension du style
        ↓
Mémoire contextuelle
        ↓
RAG de design
        ↓
Assistant personnel de conception
```

L'objectif final est de construire un **véritable atelier de conception
assisté par IA**, capable de comprendre le contexte, les références et
les préférences visuelles de son utilisateur.

------------------------------------------------------------------------

# 💡 Philosophie du projet

> **L'IA ne doit pas seulement générer une interface. Elle doit
> apprendre à comprendre la manière dont le designer conçoit.**

Personal Design AI cherche ainsi à rapprocher **IA générative + design
system + mémoire utilisateur + prototypage rapide**, avec une approche
locale et contrôlable.

------------------------------------------------------------------------

## 👋 Contribution & échanges

Le projet est avant tout un terrain d'expérimentation autour de :

-   IA locale
-   LLM
-   RAG
-   mémoire utilisateur
-   design génératif
-   automatisation du prototypage
-   personnalisation des modèles

Les retours, idées et discussions techniques sont les bienvenus.
