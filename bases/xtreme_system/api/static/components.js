/* Componentes Alpine do sistema.

   Convenção deste projeto: toda a lógica mora aqui, registrada via
   Alpine.data(). Os templates só referenciam o componente pelo nome
   (x-data="wizard(3)") e usam diretivas simples (x-show, x-bind, x-on).

   Duas razões para não escrever expressões complexas nos atributos:
   1. Mantém a lógica em um arquivo só, em vez de espalhada por 78 templates.
   2. O build CSP-friendly do Alpine proíbe arrow functions, template
      literals, destructuring, spread e acesso a document/window/JSON dentro
      de atributos. Concentrando tudo aqui, migrar para ele é trocar o
      arquivo vendorizado — nenhum template precisa mudar.

   Alpine é para estado EFÊMERO DE VIEW (passo do wizard, aberto/fechado,
   mostrar/esconder campo). Estado de domínio continua no servidor, via htmx.
   Ver rules/frontend.md. */
(function () {
  "use strict";

  document.addEventListener("alpine:init", function () {
    /* Estado do diálogo de confirmação, num store (não em appShell) porque
       #modal precisa lê-lo para desligar o próprio x-trap enquanto o
       confirm-dialog estiver aberto — dois x-trap.inert ativos ao mesmo
       tempo em elementos irmãos se marcam mutuamente como inert/aria-hidden,
       o que deixava o confirm-dialog inacessível assim que aparecia por
       cima de um #modal já aberto (dirty check e hx-confirm de formulários
       dentro de modal). Ver #modal e #confirm-dialog em base.html. */
    Alpine.store("confirmacao", {
      aberto: false,
      pergunta: "",
      callback: null,
    });

    /* Foco dos modais servidos pelo servidor.

       Os modais chegam por swap do HTMX dentro de #modal, então não há um
       x-data por modal: o componente vive no container, que é permanente, e
       observa a chegada/saída do conteúdo.

       x-trap cobre o que antes eram ~50 linhas manuais: foca o primeiro
       elemento ao abrir, cicla o Tab dentro do painel, marca o fundo com
       aria-hidden (.inert, que não existia antes) e trava o scroll da página
       (.noscroll).

       O retorno de foco fica com .noreturn, ou seja, por nossa conta: o x-trap
       memoriza o que estava focado no instante em que o trap ativa, e nesse
       momento o htmx já fez o swap e o botão que abriu o modal já perdeu o
       foco. Capturamos o gatilho antes disso, em htmx:beforeRequest. */
    Alpine.data("modalFoco", function () {
      return {
        aberto: false,
        gatilho: null,
        limpezaTimer: null,
        // $el do Alpine, nas expressões x-on dos filhos, aponta para o
        // elemento do clique (ex.: botão Fechar) — não para #modal. Guardamos
        // a raiz no init para fechar/sincronizar sempre operarem no container.
        root: null,

        init: function () {
          var self = this;
          this.root = this.$el;
          this.sincronizar();
          new MutationObserver(function () {
            self.sincronizar();
          }).observe(this.root, { childList: true });

          // O gatilho e capturado ANTES do swap: quando o modal entra, o htmx
          // ja trocou o conteudo e o botao perdeu o foco, entao o retorno
          // automatico do x-trap (.noreturn desliga) restauraria o alvo errado.
          document.body.addEventListener("htmx:beforeRequest", function (e) {
            var alvo = e.detail && e.detail.target;
            if (alvo && alvo.id === "modal") self.gatilho = document.activeElement;
          });
        },

        sincronizar: function () {
          var aberto = !!this.root.querySelector(".modal");
          if (this.aberto && !aberto) this.restaurarFoco();
          if (!aberto) {
            clearTimeout(this.limpezaTimer);
            this.limpezaTimer = null;
          } else if (!this.aberto && aberto) {
            // x-mask reformata valores (~1 frame após o swap). Adiamos a
            // baseline do dirty check; fecharComConfirmacao faz flush se o
            // usuário fechar antes do timer.
            var self = this;
            clearTimeout(this.limpezaTimer);
            this.limpezaTimer = setTimeout(function () {
              self.limpezaTimer = null;
              self.marcarComoLimpo();
            }, 50);
          }
          this.aberto = aberto;
        },

        garantirBaseline: function () {
          if (!this.limpezaTimer) return;
          clearTimeout(this.limpezaTimer);
          this.limpezaTimer = null;
          this.marcarComoLimpo();
        },

        // Alinha defaultValue/defaultSelected/defaultChecked ao estado atual
        // do formulário, para o dirty check não tratar máscara, botões ou
        // <select> sem atributo selected como "alterado".
        marcarComoLimpo: function () {
          var form = this.root.querySelector("form");
          if (!form) return;
          Array.prototype.forEach.call(form.elements, function (field) {
            if (field.type === "checkbox" || field.type === "radio") {
              field.defaultChecked = field.checked;
            } else if (field.tagName === "SELECT") {
              Array.prototype.forEach.call(field.options, function (option) {
                option.defaultSelected = option.selected;
              });
            } else if (
              field.tagName !== "BUTTON" &&
              field.type !== "button" &&
              field.type !== "submit" &&
              field.type !== "reset" &&
              field.type !== "file"
            ) {
              field.defaultValue = field.value;
            }
          });
        },

        restaurarFoco: function () {
          var gatilho = this.gatilho;
          this.gatilho = null;
          if (gatilho && document.contains(gatilho)) gatilho.focus();
        },

        fechar: function () {
          if (this.aberto) this.root.innerHTML = "";
        },

        // Fecha com confirmação se o formulário do modal tiver mudado —
        // substitui closeModalOnBackdrop(modal), que fazia o mesmo dirty
        // check à mão. Usado pelo clique no backdrop e pelos botões
        // "Cancelar"/fechar dos formulários de _form_*.html.
        fecharComConfirmacao: function () {
          this.garantirBaseline();
          var form = this.root.querySelector("form");
          var changed = form && Array.prototype.some.call(form.elements, function (field) {
            if (field.disabled) return false;
            if (
              field.tagName === "BUTTON" ||
              field.type === "button" ||
              field.type === "submit" ||
              field.type === "reset"
            ) {
              return false;
            }
            if (field.type === "file") return field.files && field.files.length > 0;
            if (field.type === "checkbox" || field.type === "radio") {
              return field.checked !== field.defaultChecked;
            }
            if (field.tagName === "SELECT") {
              return Array.prototype.some.call(field.options, function (option) {
                return option.selected !== option.defaultSelected;
              });
            }
            return field.value !== field.defaultValue;
          });
          var self = this;
          if (changed) {
            window.dispatchEvent(new CustomEvent("pedir-confirmacao", {
              detail: {
                pergunta: "Descartar as alterações?",
                onConfirmar: function () { self.fechar(); },
              },
            }));
          } else {
            this.fechar();
          }
        },
      };
    });

    /* Troca de veículo no formulário de venda.

       Estado real, depois de destrinchar o JS que estava inline:
         ativo      = checkbox "Houve troca de veículo?"
         veiculoId  = id resolvido pelo typeahead (reference.js é quem escreve
                      o hidden; aqui só lemos, via evento referencechange)
         modoNovo   = usuário optou por cadastrar um veículo que não existe

       Derivações:
         campos [data-troca] e o aviso "Cadastrar novo veículo" <- visíveis sse ativo
         bloco de cadastro inline <- visível sse ativo && !veiculoId && modoNovo
         hidden veiculo_troca_novo <- exatamente a visibilidade do bloco acima,
                                      que é o que o servidor precisa saber

       A visibilidade é declarativa (x-show). Habilitar/limpar os campos do
       bloco inline continua imperativo, mas centralizado aqui: sao ~12 campos
       e o comportamento original limpa valores so em parte das transicoes. */
    Alpine.data("trocaVeiculo", function (ativoInicial, modoNovoInicial) {
      return {
        ativo: !!ativoInicial,
        modoNovo: String(modoNovoInicial) === "1",
        veiculoId: "",

        init: function () {
          var hidden = this.hiddenId();
          this.veiculoId = hidden ? hidden.value : "";
          this.$watch("ativo", this.aplicar.bind(this));
          this.$watch("veiculoId", this.aplicar.bind(this));
          this.$watch("modoNovo", this.aplicar.bind(this));
          this.aplicar();
        },

        hiddenId: function () {
          return this.$el.querySelector("#veiculo-troca-search");
        },

        busca: function () {
          return this.$el.querySelector("#veiculo-troca-input");
        },

        // Fonte da verdade da UI e do que vai para o servidor.
        get mostrarNovos() {
          return this.ativo && !this.veiculoId && this.modoNovo;
        },

        get modoNovoEnviado() {
          return this.mostrarNovos ? "1" : "0";
        },

        // reference.js limpa o hidden no "input" antes de disparar
        // referencechange (que so vem depois do fetch), entao os dois eventos
        // precisam ser observados para o estado nao ficar defasado.
        aoBuscar: function () {
          var hidden = this.hiddenId();
          if (hidden) hidden.value = "";
          this.veiculoId = "";
          this.preencherPlaca();
        },

        aoResolverReferencia: function () {
          var hidden = this.hiddenId();
          this.veiculoId = hidden ? hidden.value : "";
        },

        cadastrarNovo: function () {
          var hidden = this.hiddenId();
          if (hidden) hidden.value = "";
          this.veiculoId = "";
          this.modoNovo = true;
          this.preencherPlaca();
        },

        // Adianta a placa digitada na busca, sem sobrescrever o que o usuario
        // ja tiver corrigido no formulario de cadastro.
        preencherPlaca: function () {
          if (!this.modoNovo) return;
          var placa = this.$el.querySelector("#veic-troca-placa");
          var busca = this.busca();
          if (placa && busca && !placa.value) {
            placa.value = busca.value.trim().toUpperCase();
          }
        },

        aplicar: function () {
          var mostrar = this.mostrarNovos;
          // O original so zera valores ao desligar a troca ou ao escolher um
          // veiculo existente; ao apenas recolher o bloco, preserva o digitado.
          var limpar = !this.ativo || !!this.veiculoId;
          var campos = this.$el.querySelectorAll(
            "[data-novo-veiculo-troca] input, [data-novo-veiculo-troca] select"
          );
          Array.prototype.forEach.call(campos, function (campo) {
            campo.disabled = !mostrar;
            if (!mostrar && limpar) campo.value = "";
          });

          if (!this.ativo) {
            var hidden = this.hiddenId();
            var busca = this.busca();
            if (hidden) hidden.value = "";
            if (busca) busca.value = "";
            this.veiculoId = "";
            this.modoNovo = false;
          }
        },
      };
    });

    /* Painel de colunas das tabelas (ordenar/ocultar).

       columns.js (window.ColunasJS) continua dono de localStorage,
       aplicação de preferências na tabela e do drag-and-drop no nível de
       DOM (cálculo de posição por coordenadas do mouse); este componente é
       só a UI do modal. O array `colunas` é a fonte da verdade da ordem
       durante o drag — reordenamos o array por índice em vez de mover nós,
       assim ele nunca diverge do que será persistido. */
    Alpine.data("colunas", function () {
      return {
        aberto: false,
        colunas: [],
        tableEl: null,
        tableKey: "",
        dragIdx: null,

        init: function () {
          var self = this;
          window.addEventListener("abrir-colunas", function (e) {
            self.abrir(e.detail.table);
          });
        },

        abrir: function (table) {
          var C = window.ColunasJS;
          this.tableEl = table;
          this.tableKey = table.getAttribute("data-table");
          var defaults = C.defaultCols(table);
          var labels = C.colLabels(table);
          var prefs = C.load(this.tableKey);
          var order = C.resolvedOrder(prefs, defaults);
          var hidden = prefs.hidden || [];
          this.colunas = order.map(function (key) {
            return { key: key, label: labels[key], visivel: hidden.indexOf(key) === -1 };
          });
          this.aberto = true;
        },

        persistir: function () {
          var order = this.colunas.map(function (col) { return col.key; });
          var hidden = this.colunas
            .filter(function (col) { return !col.visivel; })
            .map(function (col) { return col.key; });
          window.ColunasJS.save(this.tableKey, { order: order, hidden: hidden });
          window.ColunasJS.applyPrefs(this.tableEl);
        },

        restaurar: function () {
          var table = this.tableEl;
          window.ColunasJS.reset(this.tableKey);
          window.ColunasJS.applyPrefs(table);
          this.abrir(table);
        },

        fechar: function () {
          this.aberto = false;
        },

        arrastar: function (event, idx) {
          this.dragIdx = idx;
          event.target.classList.add("dragging");
        },

        sobreArrastar: function (event) {
          event.preventDefault();
          if (this.dragIdx === null) return;
          var list = event.currentTarget.closest(".cols-list");
          var after = window.ColunasJS.dragIndexAfter(list, event.clientY);
          var from = this.dragIdx;
          var to = after === -1 ? this.colunas.length - 1 : after;
          if (to === from) return;
          var moved = this.colunas.splice(from, 1)[0];
          this.colunas.splice(to, 0, moved);
          this.dragIdx = to;
        },

        soltar: function () {
          var dragging = this.$el.querySelector(".dragging");
          if (dragging) dragging.classList.remove("dragging");
          this.dragIdx = null;
          this.persistir();
        },
      };
    });

    /* Wizard multi-step dos formulários de compra, venda e veículo.

       Uso: x-data="wizard(N)" na <form>, onde N é o passo inicial vindo do
       servidor (o formulário volta renderizado no passo que falhou validação).

       O total de passos é contado do DOM, não passado como argumento: cada
       formulário tem um número diferente (5/4/4) e alguns passos podem ser
       condicionais por permissão.

       Os passos NÃO usam x-show: .wizard-step é display:none no CSS e
       .is-active é display:grid, então o display:'' que o x-show aplicaria
       cairia de volta em display:none. A visibilidade é feita por :class. */
    Alpine.data("wizard", function (inicial) {
      return {
        step: Number(inicial) || 1,
        total: 1,

        init: function () {
          this.total = this.$el.querySelectorAll(".wizard-step").length || 1;
        },

        proximo: function () {
          if (!this.validStep(this.step)) return;
          this.step = Math.min(this.step + 1, this.total);
        },

        voltar: function () {
          this.step = Math.max(this.step - 1, 1);
        },

        // Só valida o passo visível: os demais têm campos required que ainda
        // não foram preenchidos, e o submit nativo do browser ignora campos
        // com display:none, então validar tudo travaria o avanço.
        validStep: function (n) {
          var passo = this.$el.querySelector('.wizard-step[data-step="' + n + '"]');
          if (!passo) return true;
          var controls = passo.querySelectorAll("input, select, textarea");
          for (var i = 0; i < controls.length; i++) {
            if (controls[i].disabled) continue;
            if (!controls[i].checkValidity()) {
              controls[i].reportValidity();
              return false;
            }
          }
          return true;
        },
      };
    });

    /* Soma dos percentuais de rateio no fechamento de venda
       (_modal_fechamento_venda.html). Uso: x-data="rateioLucro(N)", onde N é
       o número de investidores. O submit fica desabilitado até a soma bater
       100%, dentro da tolerância de centavos do arredondamento.

       `percentuais` é um array reativo, um valor por investidor
       (x-model.number="percentuais[i]"); total()/valido() derivam dele em
       vez de reler o DOM a cada input, que é o que a primeira versão fazia e
       se mostrou frágil dentro do escopo aninhado de modalFoco. */
    Alpine.data("rateioLucro", function (n) {
      return {
        percentuais: new Array(Number(n) || 0).fill(0),

        total: function () {
          return this.percentuais.reduce(function (sum, valor) {
            return sum + (Number(valor) || 0);
          }, 0);
        },

        valido: function () {
          return Math.round(this.total() * 100) === 10000;
        },
      };
    });

    /* Alternar visibilidade de um campo de senha/API key (configuracoes.html).
       :type troca password<->text no input irmão; o componente só guarda o
       booleano, o input e o botão ficam declarativos. */
    Alpine.data("campoSenha", function () {
      return {
        visivel: false,
        alternar: function () {
          this.visivel = !this.visivel;
        },
      };
    });

    /* Inserir um placeholder ({cliente}, {veiculo}, ...) na posição do
       cursor de um textarea (configuracoes.html, template da mensagem). */
    Alpine.data("templateComPlaceholders", function () {
      return {
        inserir: function (ph) {
          var textarea = this.$refs.textarea;
          var start = textarea.selectionStart || textarea.value.length;
          var value = textarea.value;
          textarea.value = value.slice(0, start) + "{" + ph + "}" + value.slice(start);
          textarea.focus();
        },
      };
    });

    /* Casca da página (x-data no <body>): tema, drawer mobile, toast (#msg)
       e o diálogo de confirmação compartilhado por hx-confirm e pelo dirty
       check de modalFoco.fecharComConfirmacao(). Fica aqui, e não em vários
       listeners soltos em base.html, pela mesma convenção do resto do
       arquivo — ver cabeçalho. */
    Alpine.data("appShell", function () {
      return {
        navAberto: false,
        mensagem: "",
        msgTimeout: null,

        fecharDrawer: function () {
          this.navAberto = false;
        },

        alternarDrawer: function () {
          this.navAberto = !this.navAberto;
        },

        fecharDrawerAoNavegar: function (event) {
          if (event.target.closest(".nav__link, .sidebar__user-link")) this.navAberto = false;
        },

        alternarTema: function () {
          var el = document.documentElement;
          var atual = el.getAttribute("data-theme")
            || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
          var proximo = atual === "dark" ? "light" : "dark";
          el.setAttribute("data-theme", proximo);
          localStorage.setItem("theme", proximo);
        },

        // Feedback compartilhado das submissões htmx bem-sucedidas
        // (HX-Trigger: htmx:toast).
        receberToast: function (event) {
          var self = this;
          this.mensagem = event.detail.message;
          clearTimeout(this.msgTimeout);
          this.msgTimeout = setTimeout(function () { self.mensagem = ""; }, 3500);
        },

        // HX-Trigger dispara antes do htmx trocar/assentar a resposta que o
        // carregou, entao limpar #modal aqui de forma sincrona colidiria com
        // o proprio swap do htmx e quebraria silenciosamente qualquer OOB
        // swap (linhas de tabela, paginacao, stats) empacotado na mesma
        // resposta.
        fecharModalAposHtmx: function () {
          setTimeout(function () {
            document.getElementById("modal").innerHTML = "";
          }, 0);
        },

        abrirConfirmacao: function (pergunta, callback) {
          var store = Alpine.store("confirmacao");
          store.pergunta = pergunta;
          store.callback = callback;
          store.aberto = true;
          this.$nextTick(function () {
            if (this.$refs.confirmOk) this.$refs.confirmOk.focus();
          }.bind(this));
        },

        // Substitui o window.confirm() nativo por trás de hx-confirm.
        receberHtmxConfirm: function (event) {
          if (!event.detail.question) return;
          event.preventDefault();
          this.abrirConfirmacao(event.detail.question, function () {
            event.detail.issueRequest(true);
          });
        },

        confirmar: function () {
          var store = Alpine.store("confirmacao");
          var callback = store.callback;
          store.aberto = false;
          store.callback = null;
          if (callback) callback();
        },

        cancelarConfirmacao: function () {
          var store = Alpine.store("confirmacao");
          store.aberto = false;
          store.callback = null;
        },
      };
    });
  });
})();
