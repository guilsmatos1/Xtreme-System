- [x] Dashboard com métricas. Total de veículos, valor em estoque, por status, por marca, por faixa de preço.
- [x] Upload de fotos dos veículos. Galeria por veículo, imagem principal e múltiplas fotos.
- [x] Log de auditoria. Registrar quem criou/alterou/excluiu registros principais.
- [x] O badge da coluna "veiculos" deve ter cores diferentes pra carro e moto.
- [x] Trocar o nome na UI de "Xtreme Estoque" para "Xtreme Motors".
- [x] Trocar a permissão "leitor" para "vendedor" na ui.
- [x] Adicionar o Status "Reservado" pros veículos.
- [x] Na tela de Clientes, troque "Documento" por "CPF".
- [x] No modal de Nova venda, deve ter um busca por nome do cliente e do veiculo por placa ou modelo. A data da venda deve ser preenchida automaticamente na tabela ao Salvar, não é necessário no modal. 
- [x] Arrumar a função de ordenação das tabelas da ui. todas devem ter. deve classificar por ordem alfabetica apresentando as setas, pra cima e pra baixo quando alternado a ordem alfabética. 
- [x] Todas as tabelas devem ter a função de Exportar dados alinhado à direita. 
- [x] Na tabela Veiculos da UI deve ter a coluna de Procurador.
- [x] Na tabela de Investidores, adicione uma coluna com o número de veiculos , valor total em veículos e as informações do Caixa: Valor total investido
- [x] Adicionar campos de documentos do veículo na tabela Veículo.
- [x] Criar tabela de imagens do veiculo e com o id do veiculo.
- [x] Criar uma tabela de imagens de comprovantes de venda
- [x] Troque o nome da tabela "`lancamento_caixa`" por "lancamento_investimento"
- [x] Criar a tabela "compra" com as colunas: id, client_id, veiculo_id, `data_compra, valor_compra, debitos, observacoes`
- [x] Adicione o campo débitos na tabela "venda"
- [x] Criar uma tabela de imagem de documentos do cliente
- [x] Adicionar um campo de comprovante de pagamento na tabela "compra"
- [x] Adicionar um campo de tipo de entrada (compra ou consignação) e um campo de revisão (tipo boolean) na tabela "veiculo". adicione os campos na tabela da ui. 
- [ ] Integrar sistema que puxa dados do veículo pela placa.
- [x] Quando comprar o veiculo, deve pedir o documento do cliente vendedor e do veiculo. O documento do veiculo e do cliente vendedor deve ficar disponível na tabela de veiculo.

## Melhorias de arquitetura e confiabilidade

- [x] Expor endpoint `/compras` na JSON API com CRUD completo (atualmente o componente `compra` só é usado internamente pela UI).
- [x] Otimizar dashboard: mover agregações (contagem por status, valor em estoque, taxa de conversão) para queries SQL com `func.count()` e `func.sum()` em vez de carregar todos os veículos e filtrar em Python.
- [x] Integrar e expor o log de auditoria na UI/API: adicionar tela de consulta de auditoria com filtros por usuário, data e tabela. Atualmente o componente `auditoria` existe mas não é acessível.
- [x] Validar tipo e tamanho de arquivos em todos os uploads de imagens/documentos. Aceitar apenas `.jpg`, `.jpeg`, `.png`, `.webp` e `.pdf`, com limite de 5 MB por arquivo e 20 MB por request.

## Melhorias de funcionalidade e UX

- [ ] Sincronizar status do veículo automaticamente ao criar/atualizar/cancelar venda: venda concluída → `veiculo.status = vendido`; venda cancelada → reverter para `disponivel`.
- [ ] Template de mensagem do WhatsApp customizável: adicionar campo `mensagem_template` em `whatsapp_config` com placeholders (`{cliente}`, `{veiculo}`, `{valor}`, etc.) editável na tela de Configurações.
- [ ] Dashboard com métricas de venda por período: adicionar seletor de período (30d, 90d, 12m) e dados agregados por semana/mês para visualização de tendência temporal.

## Melhorias técnicas

- [ ] Adicionar coluna `updated_at` na tabela `lancamento_investimento` para rastrear edições de lançamentos.
- [ ] Implementar rate limiting na API: limitar tentativas de login (ex: 5 por minuto por IP) e requests gerais da API (ex: 100/min).
- [x] Adicionar endpoint `GET /health` (sem auth) para health check de Docker/k8s, verificando status da aplicação e conexão com o banco.



Refaça o modal "+ Novo veículo" seguindo um padrão de passo-a-passo. Cada passo deve exibir somente os informações daquele passo com um botão de "próximo" pro passo seguinte. Siga o fluxo do usuário abaixo pra projetar o passo-a-passo:

Tela 1: O usuário deve selecionar o Tipo do veículo e o Tipo de Entrada.
Tela 2: O usuário deve digitar a placa do veículo (deve ser o primeiro campo), Modelo, Cor, Ano e Quilometragem.
Tela 3: O usuário deve preencher o Preço de Compra e Investidor. 
Tela 4: O usuário deve Cadastrar os dados do Cliente que vendeu o veículo.  
