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



&nbsp;

&nbsp;

&nbsp;

Refaça o modal "+ Novo veículo" seguindo um padrão de passo-a-passo. Cada passo deve exibir somente os informações daquele passo com um botão de "próximo" pro passo seguinte. Siga o fluxo do usuário abaixo pra projetar o passo-a-passo:

Tela 1: O usuário deve selecionar o Tipo do veículo e o Tipo de Entrada.
Tela 2: O usuário deve digitar a placa do veículo (deve ser o primeiro campo), Modelo, Cor, Ano e Quilometragem.
Tela 3: O usuário deve preencher o Preço de Compra e Investidor. 
Tela 4: O usuário deve Cadastrar os dados do Cliente que vendeu o veículo.  
