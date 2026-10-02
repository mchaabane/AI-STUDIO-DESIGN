Personal Design AI

Personal Design AI est un atelier de conception web assisté par IA.

Le projet transforme une demande en langage naturel en interface web
HTML/CSS, tout en utilisant une mémoire de design personnelle pour
conserver une cohérence visuelle.

Stack

Frontend : React + Vite

Backend : Python + FastAPI

IA locale : Ollama + Qwen qwen3:8b

Mémoire de design : design-library/

Projets générés : data/projects/

1. Prérequis

Sur macOS, installer :

Python 3.12+

Node.js + npm

Ollama

Git (optionnel)

Vérifier :

python3 --version
node --version
npm --version
ollama --version

2. Copier les fichiers du projet

Copier le projet dans un dossier local, par exemple :

/Users/chaabane/design-ai-mvp

Structure attendue :

design-ai-mvp/
├── backend/
│   └── app/
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
├── design-library/
│   ├── design-profile.json
│   └── projets/
├── data/
└── .venv/

Le dossier .venv peut être recréé s'il n'est pas fourni.

3. Installer le backend Python

Dossier : /Users/chaabane/design-ai-mvp

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install fastapi uvicorn httpx pydantic

Si un requirements.txt est fourni par le projet, utiliser plutôt :

pip install -r requirements.txt

Tester :

python -c "import fastapi, httpx, pydantic; print('Backend OK')"

4. Installer le frontend

Dossier : /Users/chaabane/design-ai-mvp/frontend

npm install

5. Installer et préparer Ollama

Dossier : peu importe

ollama --version
ollama pull qwen3:8b
ollama list

Le modèle attendu est :

qwen3:8b

Ollama utilise normalement :

http://127.0.0.1:11434

La configuration du modèle se trouve dans :

backend/app/ollama.py

6. Préparer la mémoire de design

Ajouter les captures de référence dans :

design-library/projets/

Exemple :

design-library/
└── projets/
    ├── projet001/
    │   ├── reference-01.png
    │   └── reference-02.png
    ├── projet002/
    └── projet003/

Ces références servent à analyser notamment les couleurs, la luminosité,
la densité, la composition et les caractéristiques visuelles du style.

7. Analyser les références

Dossier : /Users/chaabane/design-ai-mvp

source .venv/bin/activate
python3 -c "from backend.app.design_analyzer import analyze_design_library; print(analyze_design_library())"

Vérifier ensuite le profil :

python3 -c "from backend.app.generator import load_design_profile; p=load_design_profile(); print('Profil chargé :', bool(p)); print('Projets analysés :', p.get('analysis', {}).get('total_projects'))"

Pour afficher le contexte envoyé au moteur de génération :

python3 -c "from backend.app.generator import load_design_profile, build_design_memory_context; p=load_design_profile(); print(build_design_memory_context(p))"

8. Vérifier la syntaxe Python

Dossier : /Users/chaabane/design-ai-mvp

python3 -m py_compile backend/app/main.py
python3 -m py_compile backend/app/ollama.py
python3 -m py_compile backend/app/intelligence.py
python3 -m py_compile backend/app/reasoner.py
python3 -m py_compile backend/app/change_planner.py
python3 -m py_compile backend/app/design_analyzer.py
python3 -m py_compile backend/app/design_memory.py
python3 -m py_compile backend/app/api/projects.py
python3 -m py_compile backend/app/api/generation.py

Aucune sortie signifie normalement qu'il n'y a pas d'erreur de syntaxe.

9. Démarrer le projet

Terminal 1 --- Ollama

Dossier : peu importe

ollama serve

Terminal 2 --- Backend

Dossier : /Users/chaabane/design-ai-mvp

source .venv/bin/activate
uvicorn backend.app.main:app --reload

Backend :

http://127.0.0.1:8000

Documentation API :

http://127.0.0.1:8000/docs

Terminal 3 --- Frontend

Dossier : /Users/chaabane/design-ai-mvp/frontend

npm run dev

Frontend :

http://localhost:5173

10. Premier test

Dans l'interface, essayer :

Crée une landing page moderne pour un refuge animalier.

Ajoute un grand titre "Adoptez votre compagnon",
un texte de présentation et un bouton "Voir les animaux".

Ajoute une grille de cartes avec des photos réalistes
d'animaux correspondant exactement à leur nom.

Respecte le style visuel de mes références de design.

Flux de génération :

Prompt utilisateur
        ↓
Frontend React
        ↓
Backend FastAPI
        ↓
Analyse de la demande
        ↓
Mémoire de design
        ↓
Prompt enrichi
        ↓
Ollama + Qwen
        ↓
HTML / CSS
        ↓
Validation / réparation
        ↓
Images sémantiques
        ↓
Projet généré

11. Modifier un projet

Le système accepte également des modifications en langage naturel :

Ajoute un bouton "Nous contacter".

Ajoute un Scottish Fold dans la liste.

Supprime le menu vertical en double.

Change le titre principal.

Le backend analyse la demande et applique les changements au projet et à
sa version.

12. Gestion des images

Lorsqu'une demande nécessite des photos, le système :

identifie le sujet demandé ;

recherche une image correspondant au sujet ;

vérifie que l'URL répond réellement ;

conserve uniquement une image valide ;

utilise un fallback si aucune image distante valide n'est
disponible.

Cela évite de laisser des URLs d'images cassées dans les projets
générés.

13. Projets et versions

Les projets sont enregistrés dans :

data/projects/

Chaque projet peut conserver plusieurs versions :

data/projects/
└── project_xxxxx/
    ├── version-1/
    │   └── index.html
    ├── version-2/
    │   └── index.html
    └── ...

14. Mettre à jour la mémoire de design

Après avoir ajouté de nouvelles références :

Dossier : /Users/chaabane/design-ai-mvp

source .venv/bin/activate
python3 -c "from backend.app.design_analyzer import analyze_design_library; print(analyze_design_library())"

Puis vérifier :

python3 -c "from backend.app.generator import load_design_profile; p=load_design_profile(); print('Profil chargé :', bool(p)); print('Projets analysés :', p.get('analysis', {}).get('total_projects'))"

Les générations suivantes utiliseront le profil mis à jour.

15. Dépannage

« Impossible de contacter le backend »

Vérifier que le backend est lancé :

Dossier : /Users/chaabane/design-ai-mvp

source .venv/bin/activate
uvicorn backend.app.main:app --reload

Ollama ne répond pas

Dossier : peu importe

ollama list

Si qwen3:8b manque :

ollama pull qwen3:8b

Puis :

ollama serve

Erreur ModuleNotFoundError

Réactiver l'environnement :

Dossier : /Users/chaabane/design-ai-mvp

source .venv/bin/activate

Erreur pendant une génération

Regarder les logs du terminal FastAPI. Les messages commençant par
[GENERATION] permettent notamment de suivre la génération et la
validation des images.

Images cassées

Vérifier que le backend a été redémarré après une modification de
generation.py.

16. Arrêter les services

Dans chaque terminal :

Ctrl + C

17. Démarrage quotidien

Après l'installation initiale :

Terminal 1 --- Dossier : peu importe

ollama serve

Terminal 2 --- Dossier : /Users/chaabane/design-ai-mvp

source .venv/bin/activate
uvicorn backend.app.main:app --reload

Terminal 3 --- Dossier : /Users/chaabane/design-ai-mvp/frontend

npm run dev

Puis ouvrir :

http://localhost:5173

18. Architecture

                 UTILISATEUR
                      ↓
              ┌───────────────┐
              │    FRONTEND   │
              │  React / Vite │
              └───────┬───────┘
                      ↓
              ┌───────────────┐
              │    BACKEND    │
              │    FastAPI    │
              └───────┬───────┘
                     /                     /                      ↓     ↓
          ┌──────────┐  ┌─────────────┐
          │ Mémoire  │  │ Ollama/Qwen │
          │  design  │  │     IA      │
          └────┬─────┘  └──────┬──────┘
               └────────┬───────┘
                        ↓
                 ┌─────────────┐
                 │ HTML / CSS  │
                 │ validation  │
                 └──────┬──────┘
                        ↓
                 ┌─────────────┐
                 │ Projet Web  │
                 │ + versions  │
                 └─────────────┘

19. Vision

Le projet évolue progressivement selon cette logique :

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

L'objectif est de passer d'un simple générateur de sites à un véritable
atelier de conception capable de comprendre les références visuelles et
les habitudes de design de son utilisateur.