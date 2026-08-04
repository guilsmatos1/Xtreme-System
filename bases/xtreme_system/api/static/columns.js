/* Configuração de colunas das tabelas: ordenar, ocultar e exibir.
   100% client-side — preferências persistem em localStorage por tabela.
   O servidor renderiza todas as colunas; aqui reordenamos/ocultamos as
   células no DOM (thead + linhas), reaplicando após cada swap do HTMX. */
(function () {
  "use strict";

  var PREFIX = "cols:";

  function load(tableKey) {
    try {
      return JSON.parse(localStorage.getItem(PREFIX + tableKey)) || {};
    } catch (e) {
      return {};
    }
  }
  function save(tableKey, prefs) {
    localStorage.setItem(PREFIX + tableKey, JSON.stringify(prefs));
  }
  function reset(tableKey) {
    localStorage.removeItem(PREFIX + tableKey);
  }

  // Ordem padrão das colunas gerenciáveis (exclui as fixas, ex.: Ações),
  // capturada uma vez a partir do thead antes de qualquer reordenação.
  function defaultCols(table) {
    if (!table._defaultCols) {
      var ths = table.querySelectorAll(
        "thead th[data-col]:not([data-col-fixed])"
      );
      table._defaultCols = Array.prototype.map.call(ths, function (th) {
        return th.getAttribute("data-col");
      });
    }
    return table._defaultCols;
  }

  function colLabels(table) {
    var map = {};
    var ths = table.querySelectorAll(
      "thead th[data-col]:not([data-col-fixed])"
    );
    Array.prototype.forEach.call(ths, function (th) {
      map[th.getAttribute("data-col")] =
        th.getAttribute("data-col-label") || th.textContent.trim();
    });
    return map;
  }

  function resolvedOrder(prefs, defaults) {
    var saved = (prefs.order || []).filter(function (k) {
      return defaults.indexOf(k) !== -1;
    });
    var rest = defaults.filter(function (k) {
      return saved.indexOf(k) === -1;
    });
    return saved.concat(rest);
  }

  // Reordena e alterna a visibilidade das células de uma linha.
  function applyRow(row, order, hidden) {
    var cells = Array.prototype.slice.call(row.children);
    var byKey = {};
    var fixed = [];
    for (var i = 0; i < cells.length; i++) {
      var key = cells[i].getAttribute("data-col");
      if (!key) return; // linha sem colunas nomeadas (ex.: estado vazio)
      if (cells[i].hasAttribute("data-col-fixed")) fixed.push(cells[i]);
      else byKey[key] = cells[i];
    }
    order.forEach(function (key) {
      var cell = byKey[key];
      if (cell) {
        cell.classList.toggle("col-hidden", hidden.indexOf(key) !== -1);
        row.appendChild(cell);
        delete byKey[key];
      }
    });
    Object.keys(byKey).forEach(function (key) {
      row.appendChild(byKey[key]);
    });
    fixed.forEach(function (cell) {
      row.appendChild(cell);
    });
  }

  function applyPrefs(table) {
    var tableKey = table.getAttribute("data-table");
    var prefs = load(tableKey);
    var defaults = defaultCols(table);
    var order = resolvedOrder(prefs, defaults);
    var defaultHidden = (table.getAttribute("data-default-hidden") || "")
      .split(",")
      .filter(Boolean);
    var hidden = (
      Object.prototype.hasOwnProperty.call(prefs, "hidden")
        ? prefs.hidden
        : defaultHidden
    ).filter(function (k) {
      return defaults.indexOf(k) !== -1;
    });
    var rows = table.querySelectorAll("thead tr, tbody tr");
    Array.prototype.forEach.call(rows, function (row) {
      applyRow(row, order, hidden);
    });
  }

  var COLS_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/>' +
    '<path d="M9 3v18M15 3v18"/></svg>';
  function ensureButton(table) {
    var actions = document.querySelector(".page-head__actions");
    if (!actions || actions.querySelector("[data-cols-btn]")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn--ghost";
    btn.setAttribute("data-cols-btn", "");
    btn.innerHTML = COLS_ICON + " Colunas";
    btn.addEventListener("click", function () {
      window.dispatchEvent(new CustomEvent("abrir-colunas", { detail: { table: table } }));
    });
    actions.insertBefore(btn, actions.firstChild);
  }

  // Reordenação por drag: opera sobre um array (colunas do componente Alpine)
  // via índice, em vez de mover nós do DOM — ver templates/_modal_colunas.html.
  function dragIndexAfter(list, y) {
    var items = Array.prototype.slice.call(
      list.querySelectorAll("li:not(.dragging)")
    );
    var closest = null;
    var closestOffset = -Infinity;
    items.forEach(function (item) {
      var box = item.getBoundingClientRect();
      var offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closestOffset) {
        closestOffset = offset;
        closest = item;
      }
    });
    return closest ? Number(closest.dataset.idx) : -1;
  }

  function initAll() {
    var tables = document.querySelectorAll("table[data-table]");
    Array.prototype.forEach.call(tables, function (table) {
      applyPrefs(table);
      ensureButton(table);
    });
  }

  document.addEventListener("DOMContentLoaded", initAll);
  document.body.addEventListener("htmx:afterSwap", function () {
    var tables = document.querySelectorAll("table[data-table]");
    Array.prototype.forEach.call(tables, applyPrefs);
  });

  // Exposto para o componente Alpine "colunas" (static/components.js), que
  // monta o painel via templates/_modal_colunas.html.
  window.ColunasJS = {
    load: load,
    save: save,
    reset: reset,
    defaultCols: defaultCols,
    colLabels: colLabels,
    resolvedOrder: resolvedOrder,
    applyPrefs: applyPrefs,
    dragIndexAfter: dragIndexAfter,
  };
})();
