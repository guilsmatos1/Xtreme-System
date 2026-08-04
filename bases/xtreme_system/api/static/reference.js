/* Campos de referência (chave estrangeira) com busca assíncrona.

   Markup esperado, por campo:
     <input id="X-input" list="Y-list" data-reference-url="/ui/.../referencias/z"
            data-selected-id="123" [data-reference-autoload]>
     <input id="X-search" name="z_id" type="hidden">      <- id enviado ao servidor
     <datalist id="Y-list"></datalist>
     <button data-reference-list="Y-list" hidden>Carregar mais</button>   <- opcional

   O <input> visível carrega o rótulo; o hidden irmão (mesmo id com -input
   trocado por -search) carrega o id. O endpoint devolve JSON
   {items: [{id, label}], has_more}. Ver register_reference_lookup_routes
   em crud_ui/registrars.py.

   Eventos emitidos: "referencechange" no input visível sempre que o id
   resolvido muda — usado pelo fluxo de veículo de troca em _form_venda.html.

   data-reference-autoload: continua paginando sozinho até esgotar has_more.
   Necessário quando o campo precisa da lista completa no datalist para que
   a seleção por digitação funcione sem o usuário clicar em "Carregar mais". */
(function () {
  "use strict";

  function setupReference(input) {
    var hidden = document.getElementById(input.id.replace("-input", "-search"));
    var list = document.getElementById(input.getAttribute("list"));
    if (!hidden || !list) return;
    // O botão "Carregar mais" é opcional: campos com autoload não têm um.
    var more = document.querySelector('[data-reference-list="' + list.id + '"]');

    var offset = 0;
    var query = "";
    var requestNumber = 0;
    var selectedId = input.dataset.selectedId || hidden.value || "";

    function optionFor(item) {
      var option = document.createElement("option");
      option.value = item.label;
      option.dataset.id = item.id;
      return option;
    }

    function sync() {
      var match = Array.prototype.slice.call(list.options).filter(function (option) {
        return option.value === input.value;
      })[0];
      hidden.value = match ? match.dataset.id || "" : "";
      input.dispatchEvent(new CustomEvent("referencechange"));
    }

    function load(reset, ids) {
      var currentQuery = input.value.trim();
      if (reset) {
        offset = 0;
        query = currentQuery;
        list.innerHTML = "";
      }
      var params = new URLSearchParams({
        q: query,
        limit: "20",
        offset: String(offset),
      });
      (ids || []).forEach(function (id) {
        params.append("ids", id);
      });
      // Descarta respostas fora de ordem: só a requisição mais recente aplica.
      var request = ++requestNumber;
      fetch(input.dataset.referenceUrl + "?" + params.toString(), {
        credentials: "same-origin",
      })
        .then(function (response) {
          if (!response.ok) throw new Error("lookup failed");
          return response.json();
        })
        .then(function (data) {
          if (request !== requestNumber) return;
          data.items.forEach(function (item) {
            list.appendChild(optionFor(item));
            if (selectedId && String(item.id) === String(selectedId)) {
              input.value = item.label;
              hidden.value = item.id;
            }
          });
          if (more) more.hidden = !data.has_more;
          offset += data.items.length;
          sync();
          if (data.has_more && input.hasAttribute("data-reference-autoload")) {
            load(false);
          }
        })
        .catch(function () {
          if (more) more.hidden = true;
        });
    }

    input.addEventListener("input", function () {
      selectedId = "";
      hidden.value = "";
      load(true);
    });
    input.addEventListener("change", sync);
    if (more) {
      more.addEventListener("click", function () {
        load(false);
      });
    }
    load(true, selectedId ? [selectedId] : []);
  }

  function init(element) {
    if (element.dataset.referenceReady) return;
    element.dataset.referenceReady = "1";
    setupReference(element);
  }

  function initAll(root) {
    if (root.matches && root.matches("[data-reference-url]")) init(root);
    if (!root.querySelectorAll) return;
    root.querySelectorAll("[data-reference-url]").forEach(init);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAll(document);
  });

  // Os formulários chegam por swap do HTMX (modal), depois do load inicial.
  // Sem isto os campos de referência de qualquer form aberto ficariam mortos.
  document.body.addEventListener("htmx:load", function (e) {
    initAll(e.detail.elt);
  });
})();
