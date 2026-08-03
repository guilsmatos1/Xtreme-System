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
    // Componentes registrados nas etapas seguintes.
  });
})();
