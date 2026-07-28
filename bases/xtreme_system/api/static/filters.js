/* Filtro de tabelas: troca o campo de valor entre texto e select conforme
   a coluna escolhida, sem round-trip ao servidor. Cada <option> da coluna
   carrega as opções em data-options (JSON [[valor, rótulo], ...] ou []). */
(function () {
  "use strict";

  function normalizeDecimal(value) {
    var normalized = String(value).trim().replace(/\s/g, "");
    if (normalized.indexOf(",") !== -1) {
      return normalized.replace(/\./g, "").replace(",", ".");
    }
    return normalized;
  }

  function formatDecimalInput(input) {
    if (!input.value.trim()) return;

    var value = Number(normalizeDecimal(input.value));
    if (!Number.isFinite(value)) return;

    input.value = value.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  }

  function formatDecimalInputs(root) {
    root.querySelectorAll('input[inputmode="decimal"]').forEach(formatDecimalInput);
  }

  document.addEventListener("DOMContentLoaded", function () {
    formatDecimalInputs(document);
  });

  document.addEventListener("blur", function (e) {
    if (e.target.matches('input[inputmode="decimal"]')) {
      formatDecimalInput(e.target);
    }
  }, true);

  document.body.addEventListener("htmx:load", function (e) {
    formatDecimalInputs(e.detail.elt);
  });

  document.addEventListener("change", function (e) {
    var select = e.target;
    if (!select.matches("[data-filter-col]")) return;

    var form = select.closest("form");
    var valueField = form.querySelector("[data-filter-val]");
    var opt = select.options[select.selectedIndex];
    var options;
    try {
      options = JSON.parse(opt.getAttribute("data-options") || "[]");
    } catch (err) {
      options = [];
    }

    var current = valueField.value;
    var replacement;
    if (options.length) {
      replacement = document.createElement("select");
      var html = '<option value="">Todos</option>';
      options.forEach(function (pair) {
        var isSelected = pair[0] === current ? " selected" : "";
        html += '<option value="' + pair[0] + '"' + isSelected + ">" + pair[1] + "</option>";
      });
      replacement.innerHTML = html;
    } else {
      replacement = document.createElement("input");
      replacement.type = "text";
      replacement.value = current;
      replacement.placeholder = "Valor…";
    }
    replacement.name = "filter_val";
    replacement.className = "input";
    replacement.setAttribute("data-filter-val", "");
    replacement.setAttribute("aria-label", "Valor do filtro");
    valueField.replaceWith(replacement);
  });

  document.body.addEventListener("htmx:configRequest", function (e) {
    document.querySelectorAll('input[inputmode="decimal"]').forEach(function (input) {
      if (e.detail.parameters[input.name] !== undefined) {
        e.detail.parameters[input.name] = normalizeDecimal(e.detail.parameters[input.name]);
      }
    });

    if (!e.target.closest("[data-omit-empty-params]")) return;

    Object.keys(e.detail.parameters).forEach(function (key) {
      if (e.detail.parameters[key] === "") delete e.detail.parameters[key];
    });
  });
})();
