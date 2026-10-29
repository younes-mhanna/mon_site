"""Interface web et API de calcul sans exécution de code utilisateur."""
import json

from django.core.exceptions import RequestDataTooBig
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .calculations import OPERATIONS, calculate
from .charts import render_plot
from .data import parse_table, positions

@require_GET
@ensure_csrf_cookie
def index(request):
    return render(request, "analysis/index.html", {"operations": OPERATIONS})


def payload(request):
    if request.content_type != "application/json":
        raise ValueError("Envoyez les données au format JSON.")
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as exc:
        raise ValueError("La requête JSON est invalide.") from exc
    if not isinstance(data, dict):
        raise ValueError("La requête doit contenir un objet JSON.")
    return data


def table_from(data, field="data"):
    if field == "second_data":
        return parse_table(data.get(field), data.get("second_header", False), data.get("second_delimiter", "auto"))
    return parse_table(data.get(field), data.get("header", True), data.get("delimiter", "auto"))


def response(data):
    result = JsonResponse(data, json_dumps_params={"ensure_ascii": False, "allow_nan": False})
    result["Cache-Control"] = "no-store"
    return result


def error_response(exc):
    return JsonResponse({"error": str(exc)}, status=400, json_dumps_params={"ensure_ascii": False})


@require_POST
def preview(request):
    try:
        frame = table_from(payload(request))
        return response({"headers": list(frame.columns), "rows": frame.values.tolist(),
                         "row_count": len(frame), "col_count": len(frame.columns)})
    except RequestDataTooBig:
        return error_response(ValueError("La requête est trop volumineuse (maximum 256 Ko)."))
    except ValueError as exc:
        return error_response(exc)


def chart_column(data, field, frame, selected, default):
    value = data.get(field, default)
    if type(value) is not int or value - 1 not in selected:
        raise ValueError("Choisissez les axes du graphique parmi les colonnes sélectionnées.")
    return str(frame.columns[value - 1])


@require_POST
def analyze(request):
    try:
        data = payload(request)
        frame = table_from(data)
        row_positions = positions(data.get("rows"), len(frame), "ligne")
        col_positions = positions(data.get("columns"), len(frame.columns), "colonne")
        selected = frame.iloc[row_positions, col_positions]
        operation = data.get("operation", "describe")
        metadata = next((op for op in OPERATIONS if op["id"] == operation), None)
        if metadata is None:
            raise ValueError("Choisissez un calcul proposé dans la liste.")
        second = table_from(data, "second_data") if metadata["needs_second"] else None
        result = calculate(selected, operation, data.get("axis", "columns"), data.get("ddof", 0), second)
        bins = data.get("bins", 10)
        if type(bins) is not int or not 1 <= bins <= 50:
            raise ValueError("L’histogramme doit contenir entre 1 et 50 classes.")
        chart = data.get("chart", "auto")
        if not isinstance(chart, str):
            raise ValueError("Choisissez un graphique proposé dans la liste.")
        x_column = chart_column(data, "x_column", frame, col_positions, col_positions[0] + 1)
        y_column = chart_column(data, "y_column", frame, col_positions, col_positions[min(1, len(col_positions) - 1)] + 1)
        plot = render_plot(selected, chart, operation, result, x_column, y_column, bins)
        notes = []
        if data.get("axis") == "all" and len(selected.columns) > 1 and metadata["accepts_axis"]:
            notes.append("Le calcul regroupe les cellules de toutes les colonnes sélectionnées. Vérifiez que leurs unités sont comparables.")
        return response({
            "selected": {"headers": list(selected.columns), "rows": selected.values.tolist(),
                         "indices": [i + 1 for i in row_positions]},
            "result": result, "plot": plot, "warnings": notes,
        })
    except RequestDataTooBig:
        return error_response(ValueError("La requête est trop volumineuse (maximum 256 Ko)."))
    except ValueError as exc:
        return error_response(exc)
