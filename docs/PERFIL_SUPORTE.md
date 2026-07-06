# Manual Suporte - Utilidades disponiveis no SGS

Este documento apresenta as utilidades, dados e possibilidades que o SGS
disponibiliza para o perfil **Suporte**.

O conteudo abaixo nao define procedimento operacional. Ele serve como referencia
para entender quais informacoes o sistema oferece ao Suporte e em quais telas
essas informacoes podem ser consultadas.

## Visao geral

O perfil Suporte possui acesso a recursos voltados para atendimento, consulta de
clientes, contatos de sites, equipamentos e apoio a visitas ou retiradas.

Principais possibilidades:

- consulta de clientes;
- consulta de detalhes e contatos dos sites;
- atualizacao de contatos dos sites;
- consulta de equipamentos;
- apoio a agendamento tecnico;
- apoio a retirada de equipamentos;
- consulta de predios;
- copia de tabelas.

## Clientes > Consulta

A Consulta de Clientes centraliza a visao operacional de uma assinatura.

Utilidades disponiveis:

- busca de clientes por assinatura, nome, produto, gerente ou site;
- visualizacao do resumo do cliente;
- acesso ao site SNMPc vinculado;
- acesso ao setorial;
- identificacao do GoTo SNMPc;
- visualizacao de equipamentos e IPs;
- links externos para sistemas de apoio.

Dados que podem ser exibidos:

- assinatura;
- nome do cliente;
- produto contratado;
- gerente de contas, quando disponivel;
- site SNMPc;
- setorial;
- GoTo SNMPc;
- equipamentos;
- IP dos equipamentos;
- link Aquiles;
- link Zabbix.

Possibilidades de uso:

- consulta de dados operacionais por assinatura;
- conferencia de vinculo cliente x site;
- conferencia de equipamento e IP;
- apoio a atendimento tecnico;
- apoio a consulta em sistemas externos.

## Gerenciamento de Sites > Detalhes

A area de detalhes apresenta informacoes cadastrais e operacionais do site.

Utilidades disponiveis:

- consulta de dados gerais do site;
- visualizacao de informacoes cadastrais;
- visualizacao de dados tecnicos e de localizacao;
- apoio a conferencia de dados usados por outras telas.

Dados que podem ser exibidos:

- nome SNMPc;
- nome cadastral;
- codigos do site;
- endereco;
- cidade;
- UF;
- tipo;
- status;
- categoria;
- perfil;
- latitude;
- longitude;
- altura;
- informacoes de relacionamento e cadastro, quando preenchidas.

Possibilidades de uso:

- conferencia cadastral;
- verificacao de dados tecnicos;
- apoio a validacao de endereco e coordenadas;
- consulta de informacoes do site a partir de outras telas.

## Gerenciamento de Sites > Contatos

A area de contatos apresenta e permite manter contatos associados aos sites.

Utilidades disponiveis:

- consulta de contatos cadastrados;
- inclusao ou atualizacao de contatos;
- organizacao de informacoes de acionamento;
- manutencao de referencias operacionais.

Dados que podem ser exibidos:

- nome do contato;
- telefone;
- email, quando cadastrado;
- observacao;
- tipo ou referencia do contato;
- data de atualizacao, quando disponivel.

Possibilidades de uso:

- consulta de responsaveis locais;
- apoio a acionamentos;
- apoio a visitas tecnicas;
- manutencao de contatos operacionais.

## Equipamentos > Buscar Equipamentos

A busca de equipamentos apresenta dados importados do SNMPc enriquecidos pela
base de equipamentos.

Utilidades disponiveis:

- filtros por icone;
- filtros por fabricante;
- filtros por modelo;
- filtros por tipo;
- visualizacao de equipamentos relacionados a clientes;
- visualizacao de status do cliente associado;
- identificacao de equipamentos de clientes cancelados, quando aplicavel.

Dados que podem ser exibidos:

- equipamento;
- icone SNMPc;
- IP;
- site;
- setorial;
- assinatura;
- status do cliente;
- modelo;
- fabricante;
- software;
- tipo;
- codigo;
- valor, quando o perfil tiver permissao.

Possibilidades de uso:

- localizacao de equipamentos por caracteristica;
- consulta de inventario operacional;
- identificacao de equipamentos associados a assinaturas;
- apoio a atendimento por equipamento ou IP;
- verificacao de equipamentos ainda presentes no SNMPc.

## Suporte > Agendamento

A tela de Agendamento consolida dados uteis para visitas tecnicas.

Utilidades disponiveis:

- consulta por assinatura;
- consolidacao de dados do cliente;
- consolidacao de dados de predio;
- exibicao de equipamentos relacionados;
- exibicao de caminho operacional ate o POP, quando disponivel.

Dados que podem ser exibidos:

- numero da assinatura;
- codigo do predio;
- endereco;
- cidade;
- bairro;
- equipamento base;
- equipamento cliente;
- caminho ate o POP;
- setorial;
- lista de equipamentos e IPs;
- produto contratado.

Possibilidades de uso:

- apoio a visitas tecnicas;
- consulta de dados operacionais do cliente;
- conferencia de equipamentos e IPs;
- centralizacao de informacoes para atendimento de campo.

## Suporte > Retirada

A tela de Retirada apoia a consulta de equipamentos associados a clientes.

Utilidades disponiveis:

- busca por assinatura;
- identificacao de equipamentos associados;
- consulta de IPs;
- visualizacao de site e setorial relacionados.

Dados que podem ser exibidos:

- assinatura;
- cliente;
- equipamento;
- IP;
- site;
- setorial;
- produto;
- status do cliente.

Possibilidades de uso:

- apoio a retirada de equipamentos;
- consulta de equipamentos por assinatura;
- verificacao de itens ainda presentes no SNMPc;
- apoio a saneamento operacional.

## Suporte > Predios

A tela de Predios apresenta informacoes relacionadas a codigos e enderecos de
predios.

Utilidades disponiveis:

- consulta de predios;
- consulta de codigos;
- consulta de enderecos;
- apoio a atendimento tecnico em locais compartilhados.

Dados que podem ser exibidos:

- codigo do predio;
- endereco;
- cidade;
- bairro;
- sites ou clientes relacionados, quando disponivel.

Possibilidades de uso:

- conferencia de informacoes prediais;
- apoio a visitas tecnicas;
- consulta de localidade por codigo;
- suporte a validacao de endereco.

## Tabelas

O perfil Suporte possui permissao para copiar tabelas.

Utilidades disponiveis:

- copia de resultados exibidos em tabelas;
- uso dos dados em chamados, mensagens internas e planilhas de apoio.

Dados que podem ser copiados:

- depende da tabela aberta;
- respeita as permissoes de visualizacao do perfil.

Possibilidades de uso:

- compartilhamento de dados operacionais;
- apoio a registro de chamados;
- conferencia externa de informacoes consultadas no SGS.

## Informacoes externas integradas

O perfil Suporte pode visualizar links externos quando relacionados ao cliente.

Links disponiveis na consulta de cliente:

- Aquiles;
- Zabbix.

Possibilidades de uso:

- abertura da assinatura no Aquiles;
- pesquisa da assinatura no Zabbix;
- cruzamento de informacoes do SGS com sistemas externos de apoio.

## Dados mais uteis para o Suporte

Dados de cliente:

- assinatura;
- nome;
- produto;
- site SNMPc;
- setorial;
- GoTo SNMPc;
- equipamentos;
- IPs.

Dados de site:

- nome SNMPc;
- nome cadastral;
- endereco;
- contatos;
- coordenadas;
- altura;
- tipo;
- status.

Dados de equipamento:

- icone SNMPc;
- equipamento;
- IP;
- modelo;
- fabricante;
- software;
- tipo;
- assinatura associada;
- site relacionado.

Dados de suporte:

- codigo de predio;
- endereco;
- caminho ate o POP;
- equipamento base;
- equipamento cliente;
- lista de equipamentos e IPs.

## Lista tecnica do perfil Suporte

Permissoes cadastradas no perfil `Suporte`:

```text
buscar_equipamentos
clientes
clientes_consulta
copiar_tabelas
editar_contatos_sites
gerenciar_sites_contatos
gerenciar_sites_detalhes
predios
retirada
suporte
suporte_agendamento
```
