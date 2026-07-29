/ui/veiculos
- oculte a coluna marca por padrão.
- No modal de Edição, adicione uma opção de alterar o Estado do veículo pra "Indisponível" e "Disponível".
- Ao fazer uma venda na página /ui/vendas, o carro vendido não aparece como vendido na página /ui/veiculos.

/ui/compras, no modal de editar compra:
- exiba apenas os dados do cliente e veículo, mas sem a opção de edição.
- ao cancelar uma compra, o veículo vinculado deve ter o status cancelado.
- O Estado da compra deve ser Pendente, Concluído e Cancelado.

/ui/custo:
- Adicione valores de categorias padrão no modal de "novo custo".





geral
- Quando o status do veiculo for Cancelado, ele não deve aparece em nenhuma lista de veículos para operações (lançar venda, lançar custo, etc), também não deve aparecer na página /ui/veiculos.
- Assim que for feita