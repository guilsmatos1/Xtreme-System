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
    /* Wizard multi-step dos formulários de compra, venda e veículo.

       Uso: x-data="wizard(N)" na <form>, onde N é o passo inicial vindo do
       servidor (o formulário volta renderizado no passo que falhou validação).

       O total de passos é contado do DOM, não passado como argumento: cada
       formulário tem um número diferente (5/4/5) e alguns passos podem ser
       condicionais por permissão.

       Os passos NÃO usam x-show: .wizard-step é display:none no CSS e
       .is-active é display:grid, então o display:'' que o x-show aplicaria
       cairia de volta em display:none. A visibilidade é feita por :class. */
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

        init: function () {
          var self = this;
          this.sincronizar();
          new MutationObserver(function () {
            self.sincronizar();
          }).observe(this.$el, { childList: true });

          // O gatilho e capturado ANTES do swap: quando o modal entra, o htmx
          // ja trocou o conteudo e o botao perdeu o foco, entao o retorno
          // automatico do x-trap (.noreturn desliga) restauraria o alvo errado.
          document.body.addEventListener("htmx:beforeRequest", function (e) {
            var alvo = e.detail && e.detail.target;
            if (alvo && alvo.id === "modal") self.gatilho = document.activeElement;
          });
        },

        sincronizar: function () {
          var aberto = !!this.$el.querySelector(".modal");
          if (this.aberto && !aberto) this.restaurarFoco();
          this.aberto = aberto;
        },

        restaurarFoco: function () {
          var gatilho = this.gatilho;
          this.gatilho = null;
          if (gatilho && document.contains(gatilho)) gatilho.focus();
        },

        fechar: function () {
          if (this.aberto) this.$el.innerHTML = "";
        },
      };
    });

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
  });
})();
