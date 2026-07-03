# Perfil NOC - Principais funcoes no SGS

Este documento resume as principais funcoes do SGS recomendadas para usuarios
do perfil NOC. O objetivo do perfil NOC e apoiar monitoramento, diagnostico,
consulta operacional, suporte a atendimento e validacao rapida de informacoes
de sites, clientes, equipamentos e mapa.

As telas disponiveis podem variar conforme as permissoes configuradas no perfil.
Valores financeiros, custos e acoes de edicao podem ficar ocultos quando o
perfil nao possuir permissao especifica.

## Objetivos do perfil NOC

- Localizar rapidamente sites, clientes e equipamentos.
- Validar vinculos entre clientes, sites, setoriais e equipamentos.
- Consultar topologia e mapa para apoio a incidentes.
- Identificar clientes sem vinculo, clientes cancelados ainda no SNMPc e
  equipamentos relacionados a assinaturas.
- Apoiar agendamentos, retiradas e analises de viabilidade/migracao.
- Consultar informacoes sem alterar dados cadastrais criticos.

## Modulos principais

### Topologia

Use a Topologia para entender a estrutura dos sites e seus relacionamentos.

Principais usos:

- Buscar um site por nome SNMPc, codigo ou nome cadastral.
- Visualizar sites filhos e clientes associados ao site selecionado.
- Conferir receita/clientes quando o perfil tiver permissao para valores.
- Carregar o filtro para o mapa.
- Abrir clientes diretamente na consulta de clientes.

Quando usar:

- Incidentes envolvendo um POP, BH ou REP.
- Validacao de quais clientes podem ser impactados por um site.
- Conferencia de sites filhos abaixo de um ponto da rede.

### Mapa

Use o Mapa para visualizar sites, clientes e vinculos geograficos.

Principais usos:

- Consultar o mapa geral.
- Buscar site, cliente ou endereco.
- Identificar clientes e sites nao plotados.
- Validar distancias entre cliente e site pai.
- Exportar KML/KMZ quando liberado.

Quando usar:

- Apoio a incidentes regionais.
- Validacao de endereco ou coordenadas.
- Conferencia de clientes muito distantes do site de atendimento.
- Apoio a migracoes e estudos de atendimento.

### Clientes > Consulta

Use a Consulta de Clientes para localizar uma assinatura e ver o resumo
operacional do cliente.

Principais informacoes:

- Assinatura.
- Nome do cliente.
- Produto contratado.
- Gerente de contas.
- Site SNMPc vinculado.
- Setorial.
- GoTo SNMPc.
- Equipamentos e IPs.
- Links uteis para Aquiles e Zabbix.

Quando usar:

- Atendimento a chamado por assinatura.
- Confirmar em qual site/setorial o cliente esta vinculado.
- Abrir rapidamente o cliente no Zabbix ou Aquiles.
- Conferir equipamentos associados ao cliente.

### Equipamentos

O modulo Equipamentos concentra buscas e analises da base SNMPc/equipamentos.

Principais subabas:

- **Enlaces**: consulta enlaces, filtros por tipo, icone, nome e status do
  cliente.
- **Equipamentos por Site**: lista equipamentos relacionados a um site.
- **Buscar Equipamentos**: busca por icone, fabricante, modelo e tipo.
- **Editar Equipamentos**: normalmente deve ficar restrito a administracao ou
  equipe responsavel pelo cadastro.

Quando usar:

- Localizar equipamentos por assinatura, icone, modelo ou tipo.
- Identificar equipamentos de clientes cancelados ainda presentes no SNMPc.
- Verificar equipamentos de infraestrutura relacionados a um site.
- Apoiar retirada de equipamentos e diagnosticos de inventario.

### Suporte

O modulo Suporte centraliza funcoes operacionais de atendimento.

Principais subabas:

- **Agendamento**: informa uma assinatura e monta dados para visita tecnica.
- **Retirada**: localiza equipamentos relacionados a uma assinatura.
- **Predios**: consulta informacoes de predios quando disponivel.

Quando usar:

- Preparar visita tecnica.
- Levantar equipamentos do cliente antes de uma retirada.
- Consultar endereco, codigo de predio, setorial e caminho ate o POP.

### Viabilidade

O modulo Viabilidade apoia analises tecnicas de atendimento e migracao.

Principais subabas:

- **Viabilidade**: informa um endereco e avalia sites proximos.
- **Migracao**: busca um cliente e mostra sites que poderiam atende-lo.
- **Estudos de Engenharia**: area reservada para analises futuras.

Quando usar:

- Avaliar possibilidade de atender um novo endereco.
- Avaliar migracao de cliente para outro site.
- Verificar visada, distancia e perfil do enlace quando houver dados suficientes.

### Analises e Conciliacao

Para o NOC, as analises mais uteis sao as operacionais.

Principais usos:

- **Conciliação SNMPc x Sites**: identificar sites ausentes em uma base ou outra.
- **Sem Vinculo**: localizar clientes sem site vinculado.
- **Sites sem clientes**: identificar sites ativos sem clientes associados.
- **Clientes no SNMPc cancelado**: localizar clientes que ainda aparecem no
  SNMPc, mas nao existem mais na lista ativa de clientes.
- **Ranking**: consultar ranking de sites quando liberado.

Quando usar:

- Rotina de saneamento de base.
- Validacao pos-importacao mensal.
- Identificacao de divergencias entre SNMPc, lista de Sites e lista de Clientes.

### Insights

Use Insights para uma leitura gerencial/operacional resumida.

Principais usos:

- Visao geral de indicadores.
- Filtros por cidade, contrato, categoria, perfil, produto e vinculo.
- Insights operacionais de equipamentos, produtos e clientes sem equipamento.
- Insights de riscos, como sites sem contato ou cadastro incompleto.

Quando usar:

- Acompanhar qualidade da base.
- Identificar concentracoes de problema.
- Priorizar saneamentos operacionais.

## Rotina sugerida para o NOC

### Diario

1. Consultar **Insights > Visao Geral** para identificar alertas.
2. Verificar **Clientes no SNMPc cancelado**, se houver rotina de saneamento.
3. Consultar **Equipamentos > Buscar Equipamentos** para demandas de inventario
   ou incidentes.
4. Usar **Clientes > Consulta** para chamados por assinatura.
5. Usar **Mapa** para incidentes regionais ou duvidas de localizacao.

### Apos importacao mensal

1. Conferir **Conciliação SNMPc x Sites**.
2. Conferir **Sem Vinculo**.
3. Conferir **Clientes no SNMPc cancelado**.
4. Conferir **Sites sem clientes**.
5. Validar se mapas e geocodificacao precisam ser recompilados.

### Durante incidente

1. Buscar o cliente em **Clientes > Consulta**.
2. Conferir site SNMPc, setorial, GoTo e equipamentos.
3. Abrir links Aquiles/Zabbix, se necessario.
4. Abrir o site na **Topologia** para identificar clientes e sites filhos
   impactados.
5. Abrir o **Mapa** para validar localizacao e proximidade.
6. Consultar **Equipamentos > Enlaces** se o incidente envolver conexao,
   equipamento ou enlace.

## Permissoes recomendadas para o perfil NOC

As permissoes exatas devem ser definidas pelo Master conforme a politica da
empresa. Como referencia, o perfil NOC normalmente deve ter acesso de consulta a:

- Topologia.
- Clientes > Consulta.
- Insights e subabas operacionais.
- Analises e Conciliação operacionais.
- Equipamentos > Enlaces.
- Equipamentos > Equipamentos por Site.
- Equipamentos > Buscar Equipamentos.
- Suporte > Agendamento.
- Suporte > Retirada.
- Suporte > Predios.
- Mapa.
- Viabilidade > Viabilidade.
- Viabilidade > Migracao.
- Historico, se a equipe precisar consultar removidos/cancelados.

Permissoes que normalmente devem ser avaliadas com cuidado:

- Editar cadastro de sites.
- Editar contatos dos sites.
- Editar documentos dos sites.
- Executar importacoes.
- Editar configuracoes.
- Editar base de equipamentos.
- Editar produtos.
- Visualizar valores dos clientes.
- Visualizar valores de custos.
- Copiar tabelas.

## Boas praticas

- Sempre confirmar se a base foi importada recentemente antes de concluir uma
  analise.
- Usar a assinatura como chave principal nas consultas de cliente.
- Validar site, setorial e equipamento antes de acionar campo.
- Em caso de divergencia entre SNMPc e lista de clientes, registrar o caso para
  saneamento.
- Evitar alteracoes cadastrais diretas pelo NOC, salvo quando houver processo
  definido para isso.

## Limites conhecidos

- A qualidade do mapa depende de coordenadas ou endereco valido.
- Dados financeiros podem estar ocultos por permissao.
- Viabilidade e visada dependem de coordenadas, altura e dados de elevacao.
- Informacoes do SNMPc dependem da importacao TXT mais recente.
- Informacoes de clientes dependem da ultima planilha de clientes importada.
