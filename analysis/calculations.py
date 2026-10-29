"""Calculs numériques du laboratoire, indépendants des vues Django.

Les axes décrivent les séries analysées : ``columns`` crée une série par
colonne, ``rows`` une série par ligne, ``all`` une série avec toutes les cases.
Les opérations matricielles et les relations entre variables utilisent toujours
la matrice sélectionnée telle quelle.
"""

from __future__ import annotations

import math
from numbers import Integral

import numpy as np
import pandas as pd


def _operation(identifier, label, group, description, axis=True, second=False):
    return {
        "id": identifier,
        "label": label,
        "group": group,
        "description": description,
        "accepts_axis": axis,
        "needs_second": second,
    }


OPERATIONS = [
    _operation("describe", "Résumé statistique", "Statistiques descriptives", "Effectif, moyenne, médiane, dispersion et quartiles de vos données."),
    _operation("sum", "Somme", "Statistiques descriptives", "Additionner les valeurs de chaque série."),
    _operation("mean", "Moyenne", "Statistiques descriptives", "La somme des valeurs divisée par leur effectif."),
    _operation("median", "Médiane", "Statistiques descriptives", "La valeur centrale après classement des observations."),
    _operation("mode", "Mode", "Statistiques descriptives", "La ou les valeurs ayant l’effectif le plus élevé."),
    _operation("variance", "Variance", "Statistiques descriptives", "La moyenne des écarts à la moyenne élevés au carré."),
    _operation("std", "Écart-type", "Statistiques descriptives", "La racine carrée de la variance, dans l’unité des données."),
    _operation("min", "Minimum", "Statistiques descriptives", "La plus petite valeur de chaque série."),
    _operation("max", "Maximum", "Statistiques descriptives", "La plus grande valeur de chaque série."),
    _operation("range", "Étendue", "Statistiques descriptives", "La différence entre le maximum et le minimum."),
    _operation("quartiles", "Quartiles et écart interquartile", "Statistiques descriptives", "Q1, médiane, Q3 et l’écart Q3 − Q1 (interpolation linéaire)."),
    _operation("frequency", "Effectifs et fréquences", "Statistiques descriptives", "Compter les valeurs distinctes de chaque série : par colonne, par ligne ou sur toutes les cellules."),
    _operation("correlation", "Corrélation de Pearson", "Relations entre variables", "Mesurer les relations linéaires entre les colonnes sélectionnées.", axis=False),
    _operation("covariance", "Covariance", "Relations entre variables", "Comparer les variations conjointes de plusieurs colonnes.", axis=False),
    _operation("transpose", "Transposée", "Matrices et vecteurs", "Échanger les lignes et les colonnes de la matrice.", axis=False),
    _operation("determinant", "Déterminant", "Matrices et vecteurs", "Calculer le déterminant d’une matrice carrée.", axis=False),
    _operation("inverse", "Matrice inverse", "Matrices et vecteurs", "Inverser une matrice carrée non singulière.", axis=False),
    _operation("matmul", "Produit matriciel A × B", "Matrices et vecteurs", "Le nombre de colonnes de A doit égaler le nombre de lignes de B.", axis=False, second=True),
    _operation("multiply", "Produit terme à terme", "Matrices et vecteurs", "Multiplier les cases correspondantes de deux matrices de même taille.", axis=False, second=True),
    _operation("dot", "Produit scalaire", "Matrices et vecteurs", "Multiplier deux vecteurs de même longueur puis additionner les produits.", axis=False, second=True),
    _operation("cross", "Produit vectoriel", "Matrices et vecteurs", "Calculer le produit vectoriel de deux vecteurs à trois composantes.", axis=False, second=True),
]

_CATALOG = {operation["id"]: operation for operation in OPERATIONS}


def _array(frame, name="Les données"):
    try:
        values = np.asarray(frame, dtype=float)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} doivent contenir uniquement des nombres.") from error
    if values.ndim != 2 or not values.size or not all(values.shape):
        raise ValueError(f"{name} doivent former un tableau non vide.")
    if not np.isfinite(values).all():
        raise ValueError(f"{name} doivent contenir des nombres finis (sans case vide, NaN ou infini).")
    return values


def _safe(value):
    """Conserver les nombres calculés sans arrondi et interdire NaN/Infinity."""
    if isinstance(value, str) or value is None:
        return value
    if isinstance(value, Integral):
        return int(value)
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("Le résultat dépasse la précision numérique disponible. Utilisez des nombres moins grands.")
    return value


def _result(title, columns, rows, note=""):
    return {"title": title, "columns": [str(c) for c in columns], "rows": [[_safe(v) for v in row] for row in rows], "note": note}


def _row_name(index):
    return f"Ligne {int(index) + 1}" if isinstance(index, Integral) else f"Ligne {index}"


def _series(frame, values, axis):
    if axis == "all":
        return [("Toutes les valeurs", values.ravel())]
    if axis == "rows":
        return [(_row_name(index), values[i, :]) for i, index in enumerate(frame.index)]
    return [(str(name), values[:, i]) for i, name in enumerate(frame.columns)]


def _mode(values):
    unique, counts = np.unique(values, return_counts=True)
    modes = unique[counts == counts.max()]
    return "; ".join(format(float(value), ".12g") for value in modes)


def _matrix_result(title, matrix, columns=None, index=None, note=""):
    matrix = np.asarray(matrix)
    columns = columns if columns is not None else [f"C{i + 1}" for i in range(matrix.shape[1])]
    index = index if index is not None else [f"Ligne {i + 1}" for i in range(matrix.shape[0])]
    return _result(title, ["Ligne", *columns], [[str(index[i]), *row] for i, row in enumerate(matrix)], note)


def calculate(data: pd.DataFrame, operation="describe", axis="columns", ddof=0, second: pd.DataFrame | None = None):
    """Retourner un tableau sérialisable en JSON ou une erreur explicite en français.

    ``ddof=0`` divise la variance et la covariance par n (population), ``ddof=1``
    par n−1 (échantillon). Les quartiles suivent NumPy, méthode ``linear``.
    Les noms et les index du DataFrame sont conservés dans les résultats.
    """
    if not isinstance(operation, str) or operation not in _CATALOG:
        raise ValueError("Choisissez un calcul proposé dans la liste.")
    if not isinstance(axis, str) or axis not in {"columns", "rows", "all"}:
        raise ValueError("L’axe doit être « par colonne », « par ligne » ou « toutes les valeurs ».")
    if type(ddof) is not int or ddof not in {0, 1}:
        raise ValueError("La correction de variance doit être 0 (population) ou 1 (échantillon).")
    if not isinstance(data, pd.DataFrame):
        data = pd.DataFrame(data)
    a = _array(data)
    metadata = _CATALOG[operation]
    title = metadata["label"]
    population_note = "Variance et écart-type : division par n (population)." if ddof == 0 else "Variance et écart-type : division par n − 1 (échantillon)."
    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            if metadata["accepts_axis"]:
                series = _series(data, a, axis)
                if operation in {"describe", "variance", "std"} and any(len(v) <= ddof for _, v in series):
                    raise ValueError("Le calcul avec la correction n − 1 exige au moins deux valeurs dans chaque série.")
                if operation == "describe":
                    rows = []
                    for name, v in series:
                        q1, q3 = np.quantile(v, [0.25, 0.75], method="linear")
                        rows.append([name, len(v), np.mean(v), np.median(v), np.var(v, ddof=ddof), np.std(v, ddof=ddof), np.min(v), q1, q3, np.max(v)])
                    return _result(title, ["Série", "Effectif", "Moyenne", "Médiane", "Variance", "Écart-type", "Minimum", "Q1", "Q3", "Maximum"], rows, population_note + " Quartiles : interpolation linéaire.")
                if operation == "quartiles":
                    rows = []
                    for name, v in series:
                        q1, q2, q3 = np.quantile(v, [0.25, 0.5, 0.75], method="linear")
                        rows.append([name, q1, q2, q3, q3 - q1])
                    return _result(title, ["Série", "Q1 (25 %)", "Médiane (50 %)", "Q3 (75 %)", "Écart interquartile"], rows, "Quartiles calculés par interpolation linéaire (méthode NumPy « linear »).")
                if operation == "frequency":
                    rows = []
                    for name, v in series:
                        unique, counts = np.unique(v, return_counts=True)
                        cumulative = np.cumsum(counts)
                        rows.extend([[name, u, n, n / len(v) * 100, c / len(v) * 100] for u, n, c in zip(unique, counts, cumulative)])
                    return _result(title, ["Série", "Valeur", "Effectif", "Fréquence (%)", "Fréquence cumulée (%)"], rows, "Pour chaque série, les valeurs distinctes sont classées par ordre croissant. Fréquence = effectif / effectif de la série.")
                functions = {
                    "sum": np.sum, "mean": np.mean, "median": np.median,
                    "mode": _mode, "variance": lambda v: np.var(v, ddof=ddof),
                    "std": lambda v: np.std(v, ddof=ddof), "min": np.min,
                    "max": np.max, "range": np.ptp,
                }
                note = population_note if operation in {"variance", "std"} else ""
                if operation == "mode":
                    note = "Toutes les valeurs ex æquo sont affichées ; si toutes les valeurs sont distinctes, elles ont chacune un effectif de 1."
                return _result(title, ["Série", title], [[name, functions[operation](v)] for name, v in series], note)

            if operation in {"correlation", "covariance"}:
                if a.shape[1] < 2:
                    raise ValueError("Sélectionnez au moins deux colonnes pour comparer les variables.")
                if a.shape[0] < 2:
                    raise ValueError("La corrélation et la covariance exigent au moins deux lignes d’observations.")
                if operation == "correlation":
                    if np.any(np.ptp(a, axis=0) == 0):
                        raise ValueError("La corrélation n’est pas définie pour une colonne constante. Retirez cette colonne.")
                    matrix = np.corrcoef(a, rowvar=False)
                    note = "Coefficient de Pearson : −1 (relation décroissante), 0 (absence de relation linéaire), +1 (relation croissante)."
                else:
                    matrix = np.cov(a, rowvar=False, ddof=ddof)
                    note = "Covariance : division par " + ("n (population)." if ddof == 0 else "n − 1 (échantillon).")
                return _matrix_result(title, matrix, list(data.columns), list(data.columns), note)

            if operation == "transpose":
                return _matrix_result(title, a.T, [_row_name(i) for i in data.index], list(data.columns))
            if operation in {"determinant", "inverse"}:
                if a.shape[0] != a.shape[1]:
                    raise ValueError("Ce calcul exige une matrice carrée : autant de lignes que de colonnes.")
                if operation == "determinant":
                    return _result(title, ["Calcul", "Valeur"], [["Déterminant", np.linalg.det(a)]])
                try:
                    inverse = np.linalg.inv(a)
                except np.linalg.LinAlgError as error:
                    raise ValueError("Cette matrice est singulière : elle ne possède pas d’inverse.") from error
                return _matrix_result(title, inverse, note="L’inverse est calculé en virgule flottante ; une matrice proche d’être singulière peut donner des résultats peu précis.")

            if second is None:
                raise ValueError("Saisissez la seconde matrice B pour ce calcul.")
            if not isinstance(second, pd.DataFrame):
                second = pd.DataFrame(second)
            b = _array(second, "La matrice B")
            if operation == "matmul":
                if a.shape[1] != b.shape[0]:
                    raise ValueError(f"Produit impossible : A a {a.shape[1]} colonnes, mais B a {b.shape[0]} lignes. Ces nombres doivent être égaux.")
                return _matrix_result(title, a @ b, list(second.columns), [_row_name(i) for i in data.index])
            if operation == "multiply":
                if a.shape != b.shape:
                    raise ValueError("Le produit terme à terme exige deux matrices de mêmes dimensions.")
                return _matrix_result(title, a * b, list(data.columns), [_row_name(i) for i in data.index])
            if min(a.shape) != 1 or min(b.shape) != 1:
                raise ValueError("Chaque vecteur doit occuper une seule ligne ou une seule colonne.")
            av, bv = a.ravel(), b.ravel()
            if len(av) != len(bv):
                raise ValueError("Les deux vecteurs doivent avoir la même longueur.")
            if operation == "dot":
                return _result(title, ["Calcul", "Valeur"], [[title, np.dot(av, bv)]])
            if len(av) != 3:
                raise ValueError("Le produit vectoriel exige exactement trois composantes pour chaque vecteur.")
            return _result(title, ["Composante", "Valeur"], [[name, value] for name, value in zip(["x", "y", "z"], np.cross(av, bv))])
    except (FloatingPointError, OverflowError) as error:
        raise ValueError("Le calcul dépasse la précision numérique disponible. Utilisez des nombres moins grands.") from error
    except np.linalg.LinAlgError as error:
        raise ValueError("Le calcul matriciel n’a pas convergé. Vérifiez les données sélectionnées.") from error
