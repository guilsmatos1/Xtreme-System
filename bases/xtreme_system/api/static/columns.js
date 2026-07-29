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
  var GRIP_ICON =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" ' +
    'aria-hidden="true"><circle cx="9" cy="6" r="1"/><circle cx="15" cy="6" r="1"/>' +
    '<circle cx="9" cy="12" r="1"/><circle cx="15" cy="12" r="1"/>' +
    '<circle cx="9" cy="18" r="1"/><circle cx="15" cy="18" r="1"/></svg>';

  function ensureButton(table) {
    var actions = document.querySelector(".page-head__actions");
    if (!actions || actions.querySelector("[data-cols-btn]")) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn--ghost";
    btn.setAttribute("data-cols-btn", "");
    btn.innerHTML = COLS_ICON + " Colunas";
    btn.addEventListener("click", function () {
      openPanel(table);
    });
    actions.insertBefore(btn, actions.firstChild);
  }

  function dragAfter(list, y) {
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
    return closest;
  }

  function openPanel(table) {
    var tableKey = table.getAttribute("data-table");
    var defaults = defaultCols(table);
    var labels = colLabels(table);
    var prefs = load(tableKey);
    var order = resolvedOrder(prefs, defaults);
    var hidden = prefs.hidden || [];

    var overlay = document.createElement("div");
    overlay.className = "modal";
    overlay.innerHTML =
      '<div class="modal__panel" role="dialog" aria-modal="true" ' +
      'aria-label="Configurar colunas" style="max-width:400px">' +
      '<div class="modal__head"><h3>Colunas</h3></div>' +
      '<div class="modal__body">' +
      '<p class="cols-hint">Arraste para reordenar. Desmarque para ocultar.</p>' +
      '<ul class="cols-list"></ul></div>' +
      '<div class="modal__foot">' +
      '<button type="button" class="btn btn--default" data-reset>Restaurar padrão</button>' +
      '<button type="button" class="btn btn--primary" data-close>Fechar</button>' +
      "</div></div>";

    var list = overlay.querySelector(".cols-list");
    order.forEach(function (key) {
      var li = document.createElement("li");
      li.draggable = true;
      li.dataset.col = key;
      li.innerHTML =
        '<span class="cols-list__grip" aria-hidden="true">' +
        GRIP_ICON +
        "</span>" +
        '<label class="cols-list__label"><input type="checkbox"' +
        (hidden.indexOf(key) === -1 ? " checked" : "") +
        "><span>" +
        labels[key] +
        "</span></label>";
      list.appendChild(li);
    });

    function persist() {
      var newOrder = Array.prototype.map.call(list.children, function (li) {
        return li.dataset.col;
      });
      var newHidden = [];
      Array.prototype.forEach.call(list.children, function (li) {
        if (!li.querySelector("input").checked) newHidden.push(li.dataset.col);
      });
      save(tableKey, { order: newOrder, hidden: newHidden });
      applyPrefs(table);
    }

    var dragEl = null;
    list.addEventListener("dragstart", function (e) {
      dragEl = e.target.closest("li");
      if (dragEl) dragEl.classList.add("dragging");
    });
    list.addEventListener("dragend", function () {
      if (dragEl) dragEl.classList.remove("dragging");
      dragEl = null;
      persist();
    });
    list.addEventListener("dragover", function (e) {
      e.preventDefault();
      if (!dragEl) return;
      var after = dragAfter(list, e.clientY);
      if (after == null) list.appendChild(dragEl);
      else list.insertBefore(dragEl, after);
    });
    list.addEventListener("change", persist);

    function close() {
      overlay.remove();
      document.removeEventListener("keydown", onKey);
    }
    function onKey(ev) {
      if (ev.key === "Escape") close();
    }
    document.addEventListener("keydown", onKey);
    overlay.addEventListener("click", function (ev) {
      if (ev.target === overlay) close();
    });
    overlay.querySelector("[data-close]").addEventListener("click", close);
    overlay.querySelector("[data-reset]").addEventListener("click", function () {
      reset(tableKey);
      close();
      applyPrefs(table);
      openPanel(table);
    });

    document.body.appendChild(overlay);
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
})();
