import base64
import json

from django.test import Client, SimpleTestCase

from .data import parse_table


class TableParsingTests(SimpleTestCase):
    def test_french_decimal_csv_and_bom(self):
        frame = parse_table("\ufeffPoids;Taille\n1,5;2,5\n3;4", header=True)
        self.assertEqual(list(frame.columns), ["Poids", "Taille"])
        self.assertEqual(frame.values.tolist(), [[1.5, 2.5], [3, 4]])

    def test_numeric_matrix_spaces_and_tabs(self):
        self.assertEqual(parse_table("1 2\n3 4", False).values.tolist(), [[1, 2], [3, 4]])
        self.assertEqual(parse_table("1\t2\n3\t4", False).shape, (2, 2))

    def test_invalid_data_is_rejected(self):
        for text, header in [("", False), ("\ufeff", False), ("a,b\n1", True), ("a,a\n1,2", True),
                             ("1,NaN", False), ("1,inf", False), ("1,,3", False), ("A,B\n1,2\n,", True),
                             ("a,b", True), ("1e101", False), ("1\n" * 201, False),
                             (",".join(["1"] * 21), False)]:
            with self.subTest(text=text[:30]), self.assertRaises(ValueError):
                parse_table(text, header)

    def test_quoted_column_name(self):
        frame = parse_table('"Notes, examen",Temps\n8,2\n12,4', True)
        self.assertEqual(frame.columns[0], "Notes, examen")


class AnalysisApiTests(SimpleTestCase):
    def post(self, url="/api/analyze/", **updates):
        data = {"data": "A,B\n1,2\n3,4\n5,8", "header": True, "chart": "none"}
        data.update(updates)
        return self.client.post(url, data=json.dumps(data), content_type="application/json")

    def test_page_and_operation_catalog(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'operations-data')
        self.assertContains(response, "Statio")

    def test_preview_roundtrip(self):
        response = self.post("/api/preview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["headers"], ["A", "B"])
        self.assertEqual(response.json()["row_count"], 3)

    def test_selection_controls_actual_calculation_and_preserves_labels(self):
        response = self.post(operation="mean", rows=[1, 3], columns=[2])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["rows"], [["B", 5]])
        self.assertEqual(response.json()["selected"]["indices"], [1, 3])
        response = self.post(operation="sum", rows=[3], columns=[1, 2], axis="rows")
        self.assertEqual(response.json()["result"]["rows"], [["Ligne 3", 13]])

    def test_default_population_and_optional_sample_variance(self):
        population = self.post(operation="variance", columns=[1]).json()
        sample = self.post(operation="variance", columns=[1], ddof=1).json()
        self.assertAlmostEqual(population["result"]["rows"][0][1], 8 / 3)
        self.assertEqual(sample["result"]["rows"][0][1], 4)

    def test_unsorted_median_and_matrix_product(self):
        response = self.post(operation="median", data="7\n1\n3", header=False)
        self.assertEqual(response.json()["result"]["rows"][0][1], 3)
        response = self.post(operation="matmul", data="1 2\n3 4", header=False,
                             second_data="1 0\n0 1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row[1:] for row in response.json()["result"]["rows"]], [[1, 2], [3, 4]])

    def test_real_chart_png(self):
        response = self.post(chart="scatter", x_column=1, y_column=2)
        self.assertEqual(response.status_code, 200)
        image = base64.b64decode(response.json()["plot"]["image"])
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertGreater(len(image), 5000)

    def test_invalid_options_and_shapes_return_actionable_errors(self):
        cases = [dict(rows=[]), dict(columns=[]), dict(rows=[0]), dict(columns=[3]),
                 dict(rows=[1, 1]), dict(columns=[True]), dict(ddof=True), dict(axis=[]),
                 dict(operation="__import__"), dict(chart={}), dict(bins=0), dict(x_column=9),
                 dict(operation="inverse"), dict(operation="matmul", second_data="1"),
                 dict(operation="variance", ddof=1, rows=[1]), dict(chart="pie", data="A\n-1\n2"),
                 dict(operation="correlation", data="A,B\n1,2\n1,3")]
        for case in cases:
            with self.subTest(case=case):
                response = self.post(**case)
                self.assertEqual(response.status_code, 400)
                self.assertIsInstance(response.json()["error"], str)

    def test_post_only_json_only(self):
        self.assertEqual(self.client.get("/api/analyze/").status_code, 405)
        for body in ["[1,2]", "{", '"abc"']:
            response = self.client.post("/api/analyze/", body, content_type="application/json")
            self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.post("/api/preview/", {"data": "1"}).status_code, 400)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post("/api/analyze/", '{}', content_type="application/json")
        self.assertEqual(response.status_code, 403)
        client.get("/")
        token = client.cookies["csrftoken"].value
        response = client.post("/api/preview/", json.dumps({"data": "1 2", "header": False}),
                               content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_oversized_request_is_rejected(self):
        response = self.client.post("/api/preview/", json.dumps({"data": "1" * 260000}),
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_excessive_json_nesting_is_rejected(self):
        response = self.client.post("/api/preview/", "[" * 2000 + "0" + "]" * 2000,
                                    content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("JSON", response.json()["error"])
