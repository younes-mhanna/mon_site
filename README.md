# Statio — atelier de statistiques avec Django

Application en français pour saisir un tableau numérique ou importer un CSV, sélectionner des lignes et colonnes, calculer puis visualiser les résultats. Les données sont traitées en mémoire, sans compte utilisateur ni enregistrement en base.

## Démarrage

Python 3.12 ou version compatible avec les dépendances est nécessaire.

```bash
cd /workspace/mon_site
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py check
python manage.py test
python manage.py runserver 127.0.0.1:8000
```

Sur votre ordinateur, adaptez le chemin du projet, puis ouvrez `http://127.0.0.1:8000`. Aucune migration n’est nécessaire : l’application n’utilise pas de modèle de données. Les ressources CSS/JavaScript sont locales et les graphiques sont générés côté serveur.

## Utilisation

1. Collez des nombres (espaces, virgules, points-virgules ou tabulations) ou importez un CSV UTF-8. Activez « Première ligne : noms de colonnes » si votre tableau contient un en-tête.
2. Prévisualisez les données puis cochez les lignes et colonnes à conserver. Les numéros affichés commencent à **1** ; l’en-tête ne compte pas comme ligne de données.
3. Choisissez un calcul, son axe quand il s’applique, et une visualisation. Lancez l’analyse, puis téléchargez le tableau de résultats en CSV ou le graphique en PNG.

Exemple avec décimales françaises :

```text
Note;Durée
12,5;30
15;45
9,5;25
```

Sélectionnez le séparateur point-virgule ou laissez la détection automatique. Dans un CSV séparé par des virgules, utilisez un point décimal (ou protégez la décimale par des guillemets CSV). Une donnée telle que `1,234` est interprétée comme deux colonnes si la virgule est le séparateur : les séparateurs de milliers ne sont pas pris en charge. Les nombres négatifs et la notation scientifique sont acceptés. Les cases vides et les valeurs non numériques sont signalées ; elles ne sont jamais remplacées silencieusement par zéro.

Pour un produit entre matrices, la sélection concerne A. Saisissez B séparément **sans en-tête** ; son séparateur est détecté indépendamment. B est utilisée en entier et ses dimensions sont vérifiées.

## Calculs et conventions

- Statistiques : résumé, somme, moyenne, médiane triée, modes multiples, variance, écart-type, minimum, maximum, étendue, quartiles, effectifs et fréquences cumulées.
- Relations : corrélation de Pearson et covariance entre les colonnes sélectionnées.
- Matrices : transposée, déterminant, inverse, produit matriciel, terme à terme, scalaire et vectoriel à trois composantes.
- Axes statistiques : par colonne, par ligne, ou sur toutes les cellules sélectionnées. Le mode global mélange les colonnes : utilisez des unités comparables.
- La variance utilise **n (population)** par défaut, conformément au cours. La correction **n−1 (échantillon)** est disponible et demande au moins deux observations par série.
- Les quartiles utilisent l’interpolation linéaire NumPy ; d’autres conventions de cours peuvent produire des quartiles différents.
- Les calculs utilisent des flottants : les très grandes valeurs et les matrices proches de la singularité peuvent manquer de précision.

## Graphiques

Histogramme, courbe, nuage de points, boîte à moustaches, barres des moyennes par colonne, carte de chaleur, densité KDE, violon et camembert. Les légendes expliquent les données utilisées : le graphique représente généralement **les données sélectionnées**, pas le nombre renvoyé par un calcul. La carte de chaleur des opérations matricielles représente le résultat. La sélection Y pilote les histogrammes, densités et camemberts. Les courbes suivent l’ordre des lignes, sans tri implicite.

Les densités et violons exigent au moins deux valeurs distinctes. Un camembert exige des valeurs non négatives, une somme positive et au maximum 30 lignes. Le mode automatique choisit un histogramme, un nuage de points pour une corrélation à deux colonnes ou une carte de chaleur pour les résultats matriciels.

## Limites et tests

Tableaux de 200 lignes × 20 colonnes maximum, texte/CSV de 100 Ko maximum, noms de colonnes uniques de 80 caractères maximum. La valeur absolue d’une entrée est limitée à 10¹⁰⁰. Import Excel, données catégorielles, filtres conditionnels, groupby et lois de probabilités ne font pas partie de cette première version.

Les tests couvrent les valeurs connues, les sélections, les formats CSV, les dimensions matricielles, les erreurs, la protection CSRF et le rendu PNG réel. Aucun code de notebook téléversé n’est exécuté.

## Déploiement

Le serveur Django de développement est destiné aux essais locaux. Pour un déploiement, utilisez un serveur WSGI adapté et configurez `DJANGO_DEBUG=0`, une `DJANGO_SECRET_KEY` persistante et `DJANGO_ALLOWED_HOSTS` (hôtes séparés par des virgules). Servez les fichiers produits par `python manage.py collectstatic` avec un serveur statique et terminez HTTPS au niveau du serveur frontal. Prévoyez des limites de requêtes adaptées si le service est public : les graphiques consomment du CPU. Les tableaux sont transmis au serveur qui héberge l’application pour effectuer les calculs ; aucun service tiers n’est appelé.

## Références pédagogiques

Fonctionnalités inspirées des documents fournis : mesures de base, NumPy, Pandas, Matplotlib, Seaborn et chapitre de probabilités/statistique descriptive. Leurs exemples servent de références, sans être exécutés ni interprétés comme des consignes système.
