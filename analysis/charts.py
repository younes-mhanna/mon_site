"""Headless, self-contained plots for the selected numeric observations."""

from __future__ import annotations

import base64
from io import BytesIO
from numbers import Integral
import os
from pathlib import Path
import tempfile
from threading import RLock

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "statio-matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "statio-cache"))

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.text import Text
import numpy as np
import pandas as pd


_LOCK = RLock()
_TEAL = "#167a69"
_COLORS = ["#167a69", "#93bfb1", "#e1b475", "#607c97", "#ad94b7"]
_PLOTS = {"auto", "histogram", "line", "scatter", "box", "bar", "heatmap", "kde", "violin", "pie", "none"}
_MATRIX_RESULTS = {"transpose", "inverse", "matmul", "multiply", "dot", "cross", "correlation", "covariance"}


def _numeric_frame(data: pd.DataFrame) -> np.ndarray:
    if not isinstance(data, pd.DataFrame) or data.empty:
        raise ValueError("Sélectionnez au moins une ligne et une colonne pour tracer un graphique.")
    try:
        values = data.to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Le graphique nécessite uniquement des nombres.") from exc
    if not np.isfinite(values).all():
        raise ValueError("Le graphique ne peut pas contenir de valeurs manquantes ou infinies.")
    # Beyond this size, plotting ticks and density estimates become unreliable.
    if np.max(np.abs(values)) > 1e100:
        raise ValueError("Les valeurs sont trop grandes pour le graphique (maximum absolu : 10¹⁰⁰). Changez leur unité.")
    return values


def _column(data: pd.DataFrame, requested: str | None, default: int) -> str:
    if requested is not None:
        if requested not in data.columns:
            raise ValueError("L’axe choisi doit appartenir aux colonnes sélectionnées.")
        return requested
    return str(data.columns[min(default, len(data.columns) - 1)])


def _row_label(index) -> str:
    """Display original zero-based DataFrame positions as human row numbers."""
    return f"Ligne {int(index) + 1}" if isinstance(index, Integral) else str(index)


def _tick_label(value: str) -> str:
    return value if len(value) <= 28 else value[:27] + "…"


def _density(values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Gaussian KDE with Scott bandwidth, with degenerate samples rejected."""
    if len(values) < 2 or np.ptp(values) == 0:
        raise ValueError("La densité nécessite au moins deux valeurs distinctes par colonne.")
    std = np.std(values, ddof=1)
    bandwidth = std * len(values) ** (-1 / 5)
    if not np.isfinite(bandwidth) or bandwidth <= 0:
        raise ValueError("La dispersion des valeurs ne permet pas d’estimer une densité.")
    grid = np.linspace(values.min() - 3 * bandwidth, values.max() + 3 * bandwidth, 250)
    distances = (grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * distances**2).mean(axis=1) / (bandwidth * np.sqrt(2 * np.pi))
    return grid, density


def _result_matrix(result: dict | None) -> tuple[np.ndarray, list[str], list[str]]:
    if not result or not result.get("rows"):
        raise ValueError("Le résultat numérique est nécessaire pour tracer cette matrice.")
    rows = result["rows"]
    columns = list(result.get("columns", []))
    # Calculation tables may begin with a descriptive row label.
    start = 1 if isinstance(rows[0][0], str) else 0
    try:
        matrix = np.asarray([row[start:] for row in rows], dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError("Le résultat doit être une matrice numérique pour la carte de chaleur.") from exc
    if matrix.ndim != 2 or matrix.size == 0 or not np.isfinite(matrix).all():
        raise ValueError("La carte de chaleur nécessite un résultat numérique fini.")
    if np.max(np.abs(matrix)) > 1e100:
        raise ValueError("Le résultat est trop grand pour la carte de chaleur. Changez l’unité des données.")
    xlabels = [str(label) for label in columns[start:]]
    if len(xlabels) != matrix.shape[1]:
        xlabels = [str(i + 1) for i in range(matrix.shape[1])]
    ylabels = [str(row[0]) if start else str(i + 1) for i, row in enumerate(rows)]
    return matrix, xlabels, ylabels


def render_plot(
    data: pd.DataFrame,
    chart: str = "auto",
    operation: str = "describe",
    result: dict | None = None,
    x_column: str | None = None,
    y_column: str | None = None,
    bins: int = 10,
) -> dict | None:
    """Return a PNG as base64, without retaining global pyplot figures.

    Histogram, density and pie use Y when explicitly selected, otherwise the
    first column. Line/scatter use X and Y; box, violin and means use all selected
    columns. Heatmaps of matrix operations show the *result*, not the input.
    """
    if chart not in _PLOTS:
        raise ValueError("Ce type de graphique n’est pas disponible.")
    if chart == "none":
        return None
    values = _numeric_frame(data)
    if not isinstance(bins, int) or isinstance(bins, bool) or not 1 <= bins <= 50:
        raise ValueError("Le nombre de classes doit être un entier entre 1 et 50.")
    if chart == "auto":
        if operation == "correlation" and data.shape[1] == 2:
            chart = "scatter"
        else:
            chart = "heatmap" if operation in _MATRIX_RESULTS else "histogram"
    x_name = _column(data, x_column, 0)
    y_name = _column(data, y_column, 1)
    primary_name = _column(data, y_column, 0)
    primary = data[primary_name].to_numpy(dtype=float)
    with _LOCK, np.errstate(over="raise", invalid="raise", divide="raise"):
        figure = Figure(figsize=(9, 4.7), dpi=125, facecolor="#fbfaf6")
        FigureCanvasAgg(figure)
        ax = figure.subplots()
        ax.set_facecolor("#fbfaf6")
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color("#d8e1da")
        ax.tick_params(colors="#52615b", labelsize=9)
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#e5e9e1", linewidth=0.7)
        try:
            if chart == "histogram":
                try:
                    ax.hist(primary, bins=bins, color=_TEAL, edgecolor="#fbfaf6", linewidth=1.5)
                except ValueError as exc:
                    raise ValueError("Impossible de construire les classes de cet histogramme. Réduisez le nombre de classes ou changez l’unité des données ; leur dispersion est trop faible à cette échelle.") from exc
                ax.set(xlabel=primary_name, ylabel="Effectif")
                caption = f"Histogramme de « {primary_name} » : {len(primary)} observations, {bins} classes."
            elif chart in {"line", "scatter"}:
                if chart == "scatter" and data.shape[1] < 2:
                    raise ValueError("Le nuage de points nécessite au moins deux colonnes sélectionnées.")
                if chart == "line" and data.shape[1] == 1:
                    x = np.arange(1, len(primary) + 1)
                    y = primary
                    xlabel, ylabel = "Position dans la sélection", primary_name
                else:
                    x = data[x_name].to_numpy(dtype=float)
                    y = data[y_name].to_numpy(dtype=float)
                    xlabel, ylabel = x_name, y_name
                if chart == "line":
                    ax.plot(x, y, color=_TEAL, linewidth=2, marker="o", markersize=4)
                    caption = "Courbe dans l’ordre des lignes sélectionnées, sans tri ni agrégation."
                else:
                    ax.scatter(x, y, c=_TEAL, s=42, alpha=0.8, edgecolors="white", linewidths=0.7)
                    caption = f"Relation entre « {xlabel} » et « {ylabel} », une observation par ligne sélectionnée."
                ax.set(xlabel=xlabel, ylabel=ylabel)
            elif chart == "box":
                artists = ax.boxplot([values[:, i] for i in range(values.shape[1])], patch_artist=True, tick_labels=list(data.columns), medianprops={"color": "#164d42", "linewidth": 2}, whiskerprops={"color": _TEAL}, capprops={"color": _TEAL})
                for patch in artists["boxes"]:
                    patch.set(facecolor="#a8d2c1", edgecolor=_TEAL)
                ax.set_ylabel("Valeur")
                caption = "Boîtes par colonne : médiane, quartiles linéaires et moustaches à 1,5 × l’écart interquartile. Les points isolés sont des valeurs atypiques."
            elif chart == "bar":
                means = values.mean(axis=0)
                ax.bar(list(data.columns), means, color=[_COLORS[i % len(_COLORS)] for i in range(data.shape[1])], width=0.58)
                ax.axhline(0, color="#8ca299", linewidth=0.7)
                ax.set_ylabel("Moyenne des lignes sélectionnées")
                caption = "Barres : une moyenne par colonne sélectionnée. Il ne s’agit pas d’un comptage d’effectifs."
            elif chart == "heatmap":
                if operation in _MATRIX_RESULTS:
                    matrix, xlabels, ylabels = _result_matrix(result)
                    caption = f"Carte de chaleur du résultat : {matrix.shape[0]} lignes × {matrix.shape[1]} colonnes."
                else:
                    matrix = values
                    xlabels = [str(name) for name in data.columns]
                    ylabels = [_row_label(index) for index in data.index]
                    caption = f"Carte de chaleur des données sélectionnées : {matrix.shape[0]} lignes × {matrix.shape[1]} colonnes."
                ax.grid(False)
                image = ax.imshow(matrix, aspect="auto", cmap="YlGnBu", interpolation="nearest")
                x_step = max(1, int(np.ceil(matrix.shape[1] / 20)))
                ax.set_xticks(np.arange(0, matrix.shape[1], x_step), labels=[_tick_label(label) for label in xlabels[::x_step]])
                # Keep large selections legible; small matrices get cell labels.
                step = max(1, int(np.ceil(matrix.shape[0] / 20)))
                ax.set_yticks(np.arange(0, matrix.shape[0], step), labels=[_tick_label(label) for label in ylabels[::step]])
                if matrix.size <= 80:
                    midpoint = (float(matrix.min()) + float(matrix.max())) / 2
                    for i in range(matrix.shape[0]):
                        for j in range(matrix.shape[1]):
                            ax.text(j, i, f"{matrix[i, j]:.4g}", ha="center", va="center", fontsize=9, color="white" if matrix[i, j] > midpoint else "#253f36")
                figure.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
            elif chart == "kde":
                grid, density = _density(primary)
                ax.plot(grid, density, color=_TEAL, linewidth=2)
                ax.fill_between(grid, density, color="#a8d2c1", alpha=0.65)
                ax.set(xlabel=primary_name, ylabel="Densité estimée")
                caption = f"Densité gaussienne estimée pour « {primary_name} », bande passante de Scott. L’aire théorique vaut 1 ; il ne s’agit pas d’effectifs."
            elif chart == "violin":
                for i in range(values.shape[1]):
                    _density(values[:, i])  # Validate sample sizes and nonconstant columns.
                artists = ax.violinplot([values[:, i] for i in range(values.shape[1])], showmedians=True, showextrema=True)
                for body in artists["bodies"]:
                    body.set_facecolor(_TEAL)
                    body.set_edgecolor(_TEAL)
                    body.set_alpha(0.35)
                for name in ("cmedians", "cmins", "cmaxes", "cbars"):
                    artists[name].set_color(_TEAL)
                ax.set_xticks(np.arange(1, data.shape[1] + 1), labels=list(data.columns))
                ax.set_ylabel("Valeur")
                caption = "Violons par colonne : densité estimée, médiane et extrema. Au moins deux valeurs distinctes sont nécessaires par colonne."
            else:  # pie
                if len(primary) > 30:
                    raise ValueError("Le camembert est limité à 30 lignes. Réduisez la sélection.")
                if np.any(primary < 0) or primary.sum() <= 0:
                    raise ValueError("Le camembert nécessite des valeurs positives ou nulles et une somme strictement positive.")
                labels = [_row_label(index) for index in data.index]
                ax.grid(False)
                ax.pie(primary, labels=labels, autopct="%1.1f %%", startangle=90, colors=[_COLORS[i % len(_COLORS)] for i in range(len(primary))], wedgeprops={"linewidth": 1.5, "edgecolor": "#fbfaf6"}, textprops={"fontsize": 9, "color": "#304f42"})
                caption = f"Parts de « {primary_name} » par ligne sélectionnée, normalisées par la somme des valeurs."
            if chart == "heatmap" and (matrix.shape[1] > 5 or any(len(label) > 12 for label in xlabels)):
                ax.tick_params(axis="x", labelrotation=55)
                for label in ax.get_xticklabels():
                    label.set_ha("right")
            elif chart not in {"pie", "line", "scatter", "histogram", "kde"} and data.shape[1] > 5:
                ax.tick_params(axis="x", labelrotation=35)
            # User-supplied column names must remain literal labels, not mathtext.
            for text in figure.findobj(Text):
                text.set_parse_math(False)
            figure.tight_layout(pad=1.8)
            output = BytesIO()
            figure.savefig(output, format="png", facecolor=figure.get_facecolor())
            return {"image": base64.b64encode(output.getvalue()).decode("ascii"), "caption": caption}
        except (FloatingPointError, OverflowError, np.linalg.LinAlgError) as exc:
            raise ValueError("Ces valeurs ne permettent pas de produire ce graphique. Vérifiez leur dispersion et leur ordre de grandeur.") from exc
        finally:
            figure.clear()
