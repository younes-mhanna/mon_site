"""Lecture de tableaux numériques et sélection par positions affichées (base 1)."""
import csv
import io
import math
import re

import pandas as pd

MAX_ROWS = 200
MAX_COLUMNS = 20
MAX_TEXT = 100_000
DELIMITERS = {"auto", ",", ";", "tab", "space"}


def parse_table(text, header=True, delimiter="auto"):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Saisissez des nombres ou importez un fichier CSV.")
    if len(text.encode("utf-8")) > MAX_TEXT:
        raise ValueError("Le tableau doit faire moins de 100 Ko.")
    if type(header) is not bool:
        raise ValueError("L’option d’en-tête doit être activée ou désactivée.")
    if not isinstance(delimiter, str) or delimiter not in DELIMITERS:
        raise ValueError("Séparateur inconnu. Choisissez automatique, virgule, point-virgule, tabulation ou espace.")
    text = text.lstrip("\ufeff")
    if not text.strip():
        raise ValueError("Le tableau est vide.")
    if delimiter == "auto":
        first = next(line for line in text.splitlines() if line.strip())
        delimiter = next((d for d in [";", "\t", ","] if d in first), "space")
    if delimiter == "space":
        records = [re.split(r"\s+", line.strip()) for line in text.splitlines() if line.strip()]
    else:
        try:
            records = [row for row in csv.reader(
                io.StringIO(text, newline=""), delimiter="\t" if delimiter == "tab" else delimiter,
                skipinitialspace=True, strict=True,
            ) if row and not (len(row) == 1 and not row[0].strip())]
        except csv.Error as exc:
            raise ValueError("CSV invalide : vérifiez les guillemets et le séparateur.") from exc
    if not records:
        raise ValueError("Le tableau est vide.")
    width = len(records[0])
    if width > MAX_COLUMNS:
        raise ValueError(f"Le tableau accepte au maximum {MAX_COLUMNS} colonnes.")
    if any(len(row) != width for row in records):
        raise ValueError("Chaque ligne doit avoir le même nombre de colonnes. Vérifiez le séparateur et les cases vides.")
    names = [cell.strip() for cell in records.pop(0)] if header else [f"Colonne {i + 1}" for i in range(width)]
    if not all(names) or len(set(names)) != len(names):
        raise ValueError("Chaque colonne doit avoir un nom non vide et unique.")
    if any(len(name) > 80 for name in names):
        raise ValueError("Les noms de colonnes sont limités à 80 caractères.")
    if not records:
        raise ValueError("Ajoutez au moins une ligne de nombres sous les noms des colonnes, ou désactivez l’en-tête.")
    if len(records) > MAX_ROWS:
        raise ValueError(f"Le tableau accepte au maximum {MAX_ROWS} lignes de données.")
    values = []
    for i, row in enumerate(records, 1):
        numbers = []
        for j, cell in enumerate(row, 1):
            try:
                number = float(cell.strip().replace(",", ".").replace("−", "-"))
            except ValueError as exc:
                raise ValueError(f"Ligne {i}, colonne {j} : « {cell[:40]} » n’est pas un nombre. Vérifiez aussi l’option d’en-tête.") from exc
            if not math.isfinite(number):
                raise ValueError(f"Ligne {i}, colonne {j} : les cases vides, NaN et les infinis ne sont pas acceptés.")
            if abs(number) > 1e100:
                raise ValueError("Utilisez des nombres dont la valeur absolue ne dépasse pas 10¹⁰⁰.")
            numbers.append(number)
        values.append(numbers)
    return pd.DataFrame(values, columns=names)


def positions(value, size, label):
    if value is None:
        return list(range(size))
    if not isinstance(value, list) or not value:
        raise ValueError(f"Sélectionnez au moins une {label}.")
    if any(type(n) is not int or not 1 <= n <= size for n in value):
        raise ValueError(f"Sélection de {label}s invalide : les indices commencent à 1 et doivent appartenir au tableau.")
    if len(value) != len(set(value)):
        raise ValueError(f"La sélection de {label}s contient des doublons.")
    return [n - 1 for n in value]
