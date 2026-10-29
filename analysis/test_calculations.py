"""Exemples de référence et cas limites des calculs numériques."""

import json
import unittest

import numpy as np
import pandas as pd

from analysis.calculations import OPERATIONS, calculate


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.data = pd.DataFrame({"A": [1, 2, 3, 4], "B": [2, 4, 6, 8]})

    def test_describe_population_and_unsorted_median(self):
        frame = pd.DataFrame({"Valeur": [8, 2, 4, 2]})
        result = calculate(frame)
        row = dict(zip(result["columns"], result["rows"][0]))
        self.assertEqual(row["Effectif"], 4)
        self.assertEqual(row["Moyenne"], 4)
        self.assertEqual(row["Médiane"], 3)
        self.assertEqual(row["Variance"], 6)
        self.assertAlmostEqual(row["Écart-type"], np.sqrt(6))
        self.assertEqual(row["Q1"], 2)
        self.assertEqual(row["Q3"], 5)

    def test_sample_variance_and_insufficient_sample(self):
        variance = calculate(self.data, "variance", ddof=1)
        self.assertAlmostEqual(variance["rows"][0][1], 5 / 3)
        self.assertAlmostEqual(variance["rows"][1][1], 20 / 3)
        self.assertAlmostEqual(calculate(self.data, "std", ddof=1)["rows"][0][1], np.sqrt(5 / 3))
        self.assertIn("n − 1", variance["note"])
        selected = self.data.iloc[[1, 3]]
        self.assertEqual(calculate(selected, "variance", axis="rows", ddof=1)["rows"], [["Ligne 2", 2], ["Ligne 4", 8]])
        with self.assertRaisesRegex(ValueError, "deux valeurs"):
            calculate(self.data.iloc[:1], "std", ddof=1)

    def test_axes_preserve_selected_labels(self):
        selected = self.data.iloc[[1, 3]]
        self.assertEqual(calculate(selected, "sum", axis="rows")["rows"], [["Ligne 2", 6], ["Ligne 4", 12]])
        self.assertEqual(calculate(selected, "mean", axis="all")["rows"], [["Toutes les valeurs", 4.5]])

    def test_tied_modes_and_frequency(self):
        frame = pd.DataFrame({"x": [3, 1, 3, 1, 2]})
        self.assertEqual(calculate(frame, "mode")["rows"], [["x", "1; 3"]])
        frequency = calculate(frame, "frequency")
        self.assertEqual(frequency["rows"], [["x", 1, 2, 40, 40], ["x", 2, 1, 20, 60], ["x", 3, 2, 40, 100]])
        combined = calculate(self.data, "frequency", axis="all")
        self.assertEqual(sum(row[2] for row in combined["rows"]), 8)
        self.assertTrue(all(row[0] == "Toutes les valeurs" for row in combined["rows"]))

    def test_frequency_respects_columns_rows_and_selected_indices(self):
        frame = pd.DataFrame({"A": [1, 1, 2, 4], "B": [2, 1, 2, 4]})
        selected = frame.iloc[[1, 3]]
        self.assertEqual(calculate(selected, "frequency", axis="columns")["rows"], [
            ["A", 1, 1, 50, 50], ["A", 4, 1, 50, 100],
            ["B", 1, 1, 50, 50], ["B", 4, 1, 50, 100],
        ])
        self.assertEqual(calculate(selected, "frequency", axis="rows")["rows"], [
            ["Ligne 2", 1, 2, 100, 100], ["Ligne 4", 4, 2, 100, 100],
        ])
        selected_columns = frame.iloc[[0, 2], [1]]
        self.assertEqual(calculate(selected_columns, "frequency", axis="columns")["rows"], [["B", 2, 2, 100, 100]])

    def test_quartiles_linear_interpolation(self):
        result = calculate(pd.DataFrame({"x": [1, 2, 3, 4]}), "quartiles")
        self.assertEqual(result["rows"], [["x", 1.75, 2.5, 3.25, 1.5]])

    def test_correlation_and_covariance_population(self):
        correlation = calculate(self.data, "correlation")
        np.testing.assert_allclose([row[1:] for row in correlation["rows"]], np.ones((2, 2)))
        covariance = calculate(self.data, "covariance")
        np.testing.assert_allclose([row[1:] for row in covariance["rows"]], [[1.25, 2.5], [2.5, 5]])
        with self.assertRaisesRegex(ValueError, "constante"):
            calculate(pd.DataFrame({"x": [1, 1], "y": [2, 3]}), "correlation")

    def test_transpose_determinant_and_inverse(self):
        matrix = pd.DataFrame([[1, 2], [3, 4]], columns=["a", "b"])
        self.assertEqual(calculate(matrix, "transpose")["rows"], [["a", 1, 3], ["b", 2, 4]])
        self.assertAlmostEqual(calculate(matrix, "determinant")["rows"][0][1], -2)
        inverse = calculate(matrix, "inverse")
        np.testing.assert_allclose([row[1:] for row in inverse["rows"]], [[-2, 1], [1.5, -0.5]])
        with self.assertRaisesRegex(ValueError, "carrée"):
            calculate(self.data, "inverse")
        with self.assertRaisesRegex(ValueError, "singulière"):
            calculate(pd.DataFrame([[1, 2], [2, 4]]), "inverse")

    def test_binary_products_and_dimension_validation(self):
        a = pd.DataFrame([[1, 2, 3], [4, 5, 6]])
        b = pd.DataFrame([[7, 8], [9, 10], [11, 12]])
        product = calculate(a, "matmul", second=b)
        np.testing.assert_equal([row[1:] for row in product["rows"]], [[58, 64], [139, 154]])
        elementwise = calculate(a, "multiply", second=a)
        np.testing.assert_equal([row[1:] for row in elementwise["rows"]], [[1, 4, 9], [16, 25, 36]])
        with self.assertRaisesRegex(ValueError, "doivent être égaux"):
            calculate(a, "matmul", second=a)
        with self.assertRaisesRegex(ValueError, "mêmes dimensions"):
            calculate(a, "multiply", second=b)
        with self.assertRaisesRegex(ValueError, "seconde matrice"):
            calculate(a, "matmul")

    def test_vector_products(self):
        a = pd.DataFrame([[1, 2, 3]])
        b = pd.DataFrame([[4], [5], [6]])
        self.assertEqual(calculate(a, "dot", second=b)["rows"][0][1], 32)
        self.assertEqual(calculate(a, "cross", second=b)["rows"], [["x", -3], ["y", 6], ["z", -3]])
        with self.assertRaisesRegex(ValueError, "seule ligne"):
            calculate(self.data, "dot", second=self.data)
        with self.assertRaisesRegex(ValueError, "trois composantes"):
            calculate(pd.DataFrame([[1, 2]]), "cross", second=pd.DataFrame([[3, 4]]))

    def test_invalid_settings_and_nonfinite_results(self):
        for kwargs in [{"operation": "unknown"}, {"operation": []}, {"axis": "x"}, {"axis": []}, {"ddof": 2}, {"ddof": True}]:
            with self.assertRaises(ValueError):
                calculate(self.data, **kwargs)
        for values in [[[float("inf")]], [[float("nan")]], [["hello"]], []]:
            with self.assertRaises(ValueError):
                calculate(pd.DataFrame(values))
        with self.assertRaisesRegex(ValueError, "précision numérique"):
            calculate(pd.DataFrame({"x": [1e308, 1e308]}), "sum")

    def test_every_operation_returns_strict_json(self):
        a = pd.DataFrame([[1, 2, 3]])
        for operation in OPERATIONS:
            identifier = operation["id"]
            if identifier in {"dot", "cross"}:
                result = calculate(a, identifier, second=a)
            elif identifier in {"determinant", "inverse", "matmul", "multiply"}:
                matrix = pd.DataFrame([[1, 2], [3, 4]])
                result = calculate(matrix, identifier, second=matrix)
            else:
                result = calculate(self.data, identifier, axis="all" if identifier == "frequency" else "columns")
            json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
