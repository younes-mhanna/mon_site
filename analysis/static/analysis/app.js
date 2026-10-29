"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const form = byId("analysis-form");
  const dataInput = byId("data-input");
  const headerInput = byId("has-header");
  const delimiterInput = byId("delimiter");
  const sampleData = dataInput.value;
  const operations = JSON.parse(byId("operations-data").textContent);
  const state = {
    preview: null,
    identity: null,
    selectedRows: new Set(),
    selectedColumns: new Set(),
    previewSequence: 0,
    requestSequence: 0,
    result: null,
    busy: false,
  };
  const formatNumber = new Intl.NumberFormat("fr-FR", { maximumSignificantDigits: 10 });
  const identity = () => JSON.stringify([dataInput.value, headerInput.checked, delimiterInput.value]);
  const inputPayload = () => ({ data: dataInput.value, header: headerInput.checked, delimiter: delimiterInput.value });

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined && text !== null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function displayValue(value) {
    if (value === null || value === undefined) return "—";
    if (typeof value === "number") return formatNumber.format(value);
    return String(value);
  }

  function clearError() {
    byId("error-message").hidden = true;
    byId("error-message").textContent = "";
  }

  function showError(message, focus = true) {
    const banner = byId("error-message");
    banner.textContent = message;
    banner.hidden = false;
    if (focus) banner.focus({ preventScroll: false });
  }

  function clearResult() {
    state.result = null;
    byId("results-content").hidden = true;
    byId("results-placeholder").hidden = false;
    byId("results-title").textContent = "Les données ont une histoire.";
    byId("chart-image").removeAttribute("src");
    byId("download-png").removeAttribute("href");
  }

  function invalidateAnalysis() {
    state.requestSequence += 1;
    clearResult();
    clearError();
  }

  function invalidateData() {
    invalidateAnalysis();
    state.previewSequence += 1;
    state.preview = null;
    state.identity = null;
    state.selectedRows.clear();
    state.selectedColumns.clear();
    byId("selection-count").textContent = "Données modifiées — actualisez le tableau";
    byId("preview-table").replaceChildren(element("p", "Actualisez le tableau pour sélectionner les nouvelles données.", "table-empty"));
    updateChartColumns();
  }

  async function postJSON(url, payload) {
    let response;
    try {
      response = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": form.querySelector("[name=csrfmiddlewaretoken]").value,
        },
        body: JSON.stringify(payload),
      });
    } catch (_error) {
      throw new Error("Impossible de joindre le serveur. Vérifiez la connexion, puis réessayez.");
    }
    let body;
    try {
      body = await response.json();
    } catch (_error) {
      throw new Error(response.status === 403 ? "Votre session a expiré. Rechargez la page avant de réessayer." : "Le serveur n’a pas pu traiter la demande. Réessayez dans un instant.");
    }
    if (!response.ok) throw new Error(body.error || "La demande n’a pas pu être traitée.");
    return body;
  }

  function updateSelectionCount() {
    const rowCount = state.selectedRows.size;
    const columnCount = state.selectedColumns.size;
    byId("selection-count").textContent = `${rowCount} ligne${rowCount > 1 ? "s" : ""} × ${columnCount} colonne${columnCount > 1 ? "s" : ""} sélectionnée${columnCount > 1 ? "s" : ""}`;
  }

  function updateChartColumns() {
    const x = byId("x-column");
    const y = byId("y-column");
    const previousX = x.value;
    const previousY = y.value;
    x.replaceChildren();
    y.replaceChildren();
    if (!state.preview) return;
    const columns = [...state.selectedColumns].sort((a, b) => a - b);
    columns.forEach((column) => {
      const label = `${column}. ${state.preview.headers[column - 1]}`;
      x.add(new Option(label, String(column)));
      y.add(new Option(label, String(column)));
    });
    if (columns.includes(Number(previousX))) x.value = previousX;
    if (columns.includes(Number(previousY))) y.value = previousY;
    else if (columns.length > 1) y.value = String(columns[1]);
  }

  function checkbox(checked, label, onChange) {
    const input = element("input");
    input.type = "checkbox";
    input.checked = checked;
    input.setAttribute("aria-label", label);
    input.addEventListener("change", () => onChange(input.checked));
    return input;
  }

  function renderPreview() {
    const preview = state.preview;
    const table = element("table", null, "data-table");
    const head = element("thead");
    const headerRow = element("tr");
    const corner = element("th", "Ligne", "row-index");
    corner.scope = "col";
    headerRow.append(corner);
    preview.headers.forEach((header, index) => {
      const column = index + 1;
      const th = element("th");
      th.scope = "col";
      th.classList.toggle("selected", state.selectedColumns.has(column));
      const label = element("label", null, "checkbox-label");
      label.append(checkbox(state.selectedColumns.has(column), `Inclure la colonne ${column} : ${header}`, (checked) => {
        checked ? state.selectedColumns.add(column) : state.selectedColumns.delete(column);
        th.classList.toggle("selected", checked);
        updateSelectionCount();
        updateChartColumns();
        invalidateAnalysis();
      }), element("span", header));
      th.append(label);
      headerRow.append(th);
    });
    head.append(headerRow);
    table.append(head);
    const body = element("tbody");
    preview.rows.forEach((row, index) => {
      const rowNumber = index + 1;
      const tr = element("tr");
      tr.classList.toggle("selected", state.selectedRows.has(rowNumber));
      const th = element("th", null, "row-index");
      th.scope = "row";
      const label = element("label", null, "checkbox-label");
      label.append(checkbox(state.selectedRows.has(rowNumber), `Inclure la ligne ${rowNumber}`, (checked) => {
        checked ? state.selectedRows.add(rowNumber) : state.selectedRows.delete(rowNumber);
        tr.classList.toggle("selected", checked);
        updateSelectionCount();
        invalidateAnalysis();
      }), element("span", rowNumber));
      th.append(label);
      tr.append(th);
      row.forEach((value) => tr.append(element("td", displayValue(value))));
      body.append(tr);
    });
    table.append(body);
    byId("preview-table").replaceChildren(table);
    updateSelectionCount();
    updateChartColumns();
  }

  async function loadPreview() {
    const currentIdentity = identity();
    if (state.preview && state.identity === currentIdentity) return state.preview;
    const sequence = ++state.previewSequence;
    const previewButton = byId("preview-button");
    previewButton.disabled = true;
    try {
      const preview = await postJSON("/api/preview/", inputPayload());
      if (sequence !== state.previewSequence || currentIdentity !== identity()) return null;
      state.preview = preview;
      state.identity = currentIdentity;
      state.selectedRows = new Set(preview.rows.map((_, index) => index + 1));
      state.selectedColumns = new Set(preview.headers.map((_, index) => index + 1));
      renderPreview();
      return preview;
    } catch (error) {
      if (sequence === state.previewSequence && currentIdentity === identity()) throw error;
      return null;
    } finally {
      // A newer request may still be in flight; this button remains safe to retry.
      if (sequence === state.previewSequence || !state.preview) previewButton.disabled = false;
    }
  }

  function selectedOperation() {
    return operations.find((operation) => operation.id === byId("operation").value);
  }

  function updateOperation() {
    const operation = selectedOperation();
    byId("operation-description").textContent = operation ? operation.description : "";
    byId("axis-field").hidden = !operation?.accepts_axis;
    byId("ddof-field").hidden = !["describe", "variance", "std", "covariance"].includes(operation?.id);
    byId("second-field").hidden = !operation?.needs_second;
  }

  function updateChartSettings() {
    const chart = byId("chart").value;
    byId("x-field").hidden = !["line", "scatter"].includes(chart);
    byId("y-field").hidden = !["auto", "histogram", "kde", "pie", "line", "scatter"].includes(chart);
    document.querySelector('label[for="y-column"]').textContent = ["line", "scatter"].includes(chart) ? "Colonne Y" : "Colonne à visualiser";
    byId("bins-field").hidden = !["auto", "histogram"].includes(chart);
    byId("chart-settings").hidden = ["none", "box", "bar", "heatmap", "violin"].includes(chart);
  }

  function renderResults(response) {
    state.result = response.result;
    byId("results-placeholder").hidden = true;
    byId("results-content").hidden = false;
    byId("results-title").textContent = response.result.title;
    const selected = response.selected;
    byId("result-meta").textContent = `${selected.rows.length} ligne${selected.rows.length > 1 ? "s" : ""} · ${selected.headers.length} colonne${selected.headers.length > 1 ? "s" : ""} · ${selectedOperation()?.label || "Analyse"}`;
    const table = element("table", null, "data-table");
    const head = element("thead");
    const headerRow = element("tr");
    response.result.columns.forEach((column) => {
      const th = element("th", column);
      th.scope = "col";
      headerRow.append(th);
    });
    head.append(headerRow);
    table.append(head);
    const body = element("tbody");
    response.result.rows.forEach((row) => {
      const tr = element("tr");
      row.forEach((value) => tr.append(element("td", displayValue(value))));
      body.append(tr);
    });
    table.append(body);
    byId("result-table").replaceChildren(table);
    byId("result-note").textContent = response.result.note || "";
    const warnings = byId("result-warnings");
    warnings.replaceChildren();
    (response.warnings || []).forEach((warning) => warnings.append(element("li", warning)));
    warnings.hidden = !warnings.childElementCount;
    byId("chart-frame").hidden = !response.plot;
    byId("download-png").hidden = !response.plot;
    if (response.plot) {
      const url = `data:image/png;base64,${response.plot.image}`;
      byId("chart-image").src = url;
      byId("chart-image").alt = response.plot.caption || "Visualisation des données sélectionnées";
      byId("chart-caption").textContent = response.plot.caption;
      byId("download-png").href = url;
    }
  }

  function setBusy(busy) {
    state.busy = busy;
    byId("analyze-button").disabled = busy;
    byId("submit-label").textContent = busy ? "Calcul en cours…" : "Calculer et visualiser";
    byId("submit-spinner").hidden = !busy;
    byId("submit-arrow").hidden = busy;
    byId("resultats").setAttribute("aria-busy", String(busy));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy) return;
    clearError();
    clearResult();
    const sequence = ++state.requestSequence;
    setBusy(true);
    try {
      const preview = await loadPreview();
      if (!preview || sequence !== state.requestSequence) return;
      if (!state.selectedRows.size || !state.selectedColumns.size) throw new Error("Sélectionnez au moins une ligne et une colonne dans le tableau.");
      const bins = Number(byId("bins").value);
      if (["auto", "histogram"].includes(byId("chart").value) && (!Number.isInteger(bins) || bins < 1 || bins > 50)) throw new Error("Le nombre de classes doit être un entier compris entre 1 et 50.");
      const payload = {
        ...inputPayload(),
        rows: [...state.selectedRows].sort((a, b) => a - b),
        columns: [...state.selectedColumns].sort((a, b) => a - b),
        operation: byId("operation").value,
        axis: selectedOperation()?.accepts_axis ? byId("axis").value : "columns",
        ddof: Number(byId("ddof").value),
        second_data: byId("second-data").value,
        second_header: false,
        second_delimiter: "auto",
        chart: byId("chart").value,
        x_column: Number(byId("x-column").value) || payloadFallbackColumn(),
        y_column: Number(byId("y-column").value) || payloadFallbackColumn(),
        bins: Number.isInteger(bins) && bins > 0 && bins <= 50 ? bins : 8,
      };
      const response = await postJSON("/api/analyze/", payload);
      if (sequence !== state.requestSequence) return;
      renderResults(response);
      if (window.matchMedia("(max-width: 1199px)").matches) byId("resultats").scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      if (sequence === state.requestSequence) showError(error.message);
    } finally {
      setBusy(false);
    }
  });

  function payloadFallbackColumn() {
    return [...state.selectedColumns].sort((a, b) => a - b)[0] || 1;
  }

  byId("preview-button").addEventListener("click", async () => {
    clearError();
    try { await loadPreview(); } catch (error) { showError(error.message); }
  });

  for (const [id, selected] of [["select-all", true], ["select-none", false]]) {
    byId(id).addEventListener("click", () => {
      if (!state.preview) return;
      state.selectedRows = new Set(selected ? state.preview.rows.map((_, index) => index + 1) : []);
      state.selectedColumns = new Set(selected ? state.preview.headers.map((_, index) => index + 1) : []);
      invalidateAnalysis();
      renderPreview();
    });
  }

  dataInput.addEventListener("input", invalidateData);
  headerInput.addEventListener("change", invalidateData);
  delimiterInput.addEventListener("change", invalidateData);
  for (const id of ["axis", "ddof", "second-data", "x-column", "y-column", "bins"]) {
    byId(id).addEventListener(id === "second-data" || id === "bins" ? "input" : "change", invalidateAnalysis);
  }
  byId("operation").addEventListener("change", () => { invalidateAnalysis(); updateOperation(); });
  byId("chart").addEventListener("change", () => { invalidateAnalysis(); updateChartSettings(); });

  byId("sample-button").addEventListener("click", async () => {
    dataInput.value = sampleData;
    headerInput.checked = true;
    delimiterInput.value = "auto";
    byId("csv-file").value = "";
    byId("file-status").textContent = "Exemple chargé : évolution des ventes et des coûts sur six périodes.";
    invalidateData();
    try { await loadPreview(); } catch (error) { showError(error.message); }
  });

  byId("csv-file").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    if (file.size > 100000) {
      showError("Le fichier doit faire moins de 100 Ko. Importez un extrait de 200 lignes maximum.");
      event.target.value = "";
      return;
    }
    const beforeRead = identity();
    try {
      const text = await file.text();
      if (event.target.files[0] !== file || beforeRead !== identity()) return;
      dataInput.value = text.replace(/^\uFEFF/, "");
      invalidateData();
      byId("file-status").textContent = `Fichier importé : ${file.name}. Vérifiez le séparateur et la présence d’en-têtes.`;
      await loadPreview();
    } catch (error) { showError(error.message || "Ce fichier n’a pas pu être lu."); }
  });

  function csvCell(value) {
    let text = value === null || value === undefined ? "" : String(value);
    // Spreadsheet formula prefixes are escaped only for string cells.
    if (typeof value === "string" && /^[\s\u0000-\u001f]*[=+\-@]/.test(text)) text = `'${text}`;
    return `"${text.replace(/"/g, '""')}"`;
  }

  byId("download-csv").addEventListener("click", () => {
    if (!state.result) return;
    const rows = [state.result.columns, ...state.result.rows];
    const csv = "\uFEFF" + rows.map((row) => row.map(csvCell).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = element("a");
    link.href = url;
    link.download = "statio-resultat.csv";
    document.body.append(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  const groups = new Map();
  operations.forEach((operation) => {
    if (!groups.has(operation.group)) {
      const group = element("optgroup");
      group.label = operation.group;
      groups.set(operation.group, group);
      byId("operation").append(group);
    }
    groups.get(operation.group).append(new Option(operation.label, operation.id));
  });
  if (operations.some((operation) => operation.id === "describe")) byId("operation").value = "describe";
  updateOperation();
  updateChartSettings();
  loadPreview().catch((error) => showError(error.message, false));
})();
