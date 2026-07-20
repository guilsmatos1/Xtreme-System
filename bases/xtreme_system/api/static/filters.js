/* Filtro de tabelas: troca o campo de valor entre texto e select conforme
   a coluna escolhida, sem round-trip ao servidor. Cada <option> da coluna
   carrega as opções em data-options (JSON [[valor, rótulo], ...] ou []). */
(function () {
  "use strict";

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
    if (!e.target.closest("[data-omit-empty-params]")) return;

    Object.keys(e.detail.parameters).forEach(function (key) {
      if (e.detail.parameters[key] === "") delete e.detail.parameters[key];
    });
  });
})();
