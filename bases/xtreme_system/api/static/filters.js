/* Campos decimais: formata em pt-BR na exibição (1.234,56) e normaliza de
   volta para ponto decimal antes de cada requisição do HTMX. Também remove
   parâmetros vazios em formulários marcados com data-omit-empty-params. */
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
