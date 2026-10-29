import base64
import unittest
from unittest.mock import patch

import pandas as pd

from .charts import render_plot
from matplotlib.figure import Figure


class ChartTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({"Temps": [1.0, 2.0, 3.0], "Valeur": [4.0, 7.0, 9.0]}, index=[1, 3, 5])

    def test_histogram_is_png_and_identifies_source(self):
        plot = render_plot(self.data)
        self.assertTrue(base64.b64decode(plot["image"]).startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("Temps", plot["caption"])
        self.assertIn("3 observations", plot["caption"])

    def test_scatter_requires_two_columns(self):
        with self.assertRaisesRegex(ValueError, "deux colonnes"):
            render_plot(self.data[["Temps"]], chart="scatter")

    def test_pie_rejects_negative_values(self):
        with self.assertRaisesRegex(ValueError, "positives"):
            render_plot(pd.DataFrame({"a": [-1.0, 2.0]}), chart="pie")

    def test_matrix_auto_uses_calculated_output(self):
        result = {"columns": ["Ligne", "C1"], "rows": [["L1", 27.0], ["L2", 42.0]]}
        plot = render_plot(self.data, operation="matmul", result=result)
        self.assertIn("résultat", plot["caption"])
        self.assertIn("2 lignes × 1 colonnes", plot["caption"])

    def test_degenerate_density_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "distinctes"):
            render_plot(pd.DataFrame({"a": [2.0, 2.0]}), chart="kde")

    def test_custom_y_and_literal_math_labels(self):
        data = pd.DataFrame({"$invalid{math}$": [1.0, 2.0, 3.0], "Autre": [3.0, 4.0, 8.0]})
        plot = render_plot(data, chart="histogram", y_column="$invalid{math}$")
        self.assertIn("$invalid{math}$", plot["caption"])

    def test_none_and_invalid_chart(self):
        self.assertIsNone(render_plot(self.data, chart="none"))
        with self.assertRaisesRegex(ValueError, "disponible"):
            render_plot(self.data, chart="unknown")

    def test_large_values_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "trop grandes"):
            render_plot(pd.DataFrame({"a": [1e200]}))

    def test_plot_labels_preserve_original_row_positions(self):
        data = pd.DataFrame({"a": [4.0, 6.0, 9.0]}, index=[0, 2, 5])
        rendered_labels = []
        original_savefig = Figure.savefig

        def capture_labels(figure, *args, **kwargs):
            ax = figure.axes[0]
            rendered_labels.append({text.get_text() for text in [*ax.get_yticklabels(), *ax.texts]})
            return original_savefig(figure, *args, **kwargs)

        with patch.object(Figure, "savefig", capture_labels):
            render_plot(data, chart="heatmap")
            render_plot(data, chart="pie")
        for labels in rendered_labels:
            self.assertTrue({"Ligne 1", "Ligne 3", "Ligne 6"} <= labels)
            self.assertNotIn("Ligne 0", labels)

    def test_wide_result_heatmap_samples_labels_without_losing_cells(self):
        result = {
            "columns": ["Ligne", *[f"Observation très longue numéro {i}" for i in range(200)]],
            "rows": [["L1", *range(200)], ["L2", *range(200, 400)]],
        }
        captured = {}
        original_savefig = Figure.savefig

        def capture_axes(figure, *args, **kwargs):
            ax = figure.axes[0]
            captured["ticks"] = [text.get_text() for text in ax.get_xticklabels()]
            captured["shape"] = ax.images[0].get_array().shape
            return original_savefig(figure, *args, **kwargs)

        with patch.object(Figure, "savefig", capture_axes):
            render_plot(self.data, operation="transpose", result=result)
        self.assertEqual(captured["shape"], (2, 200))
        self.assertEqual(len(captured["ticks"]), 20)
        self.assertTrue(all(len(label) <= 28 for label in captured["ticks"]))
