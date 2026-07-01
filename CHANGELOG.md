# Histórico de versões

## 1.1.4

- Corrigida a formatação do texto dos sites deficitários no Relatório Gerencial.

## 1.1.3

- Corrigida a geração do PDF do Relatório Gerencial quando há sites deficitários detalhados.

## 1.1.2

- Relatório Gerencial passa a exibir ranking por receita direta e ranking por receita total com filhos.
- Sites deficitários passam a ser apresentados em texto simples com seus clientes, sem tabelas aninhadas.

## 1.1.1

- Relatório Gerencial passa a calcular receita pela soma direta dos clientes vinculados ao site.
- Relatório Gerencial remove o bloco de resumo da tela e do PDF.
- Sites deficitários passam a ser exibidos em blocos de site com seus respectivos clientes.

## 1.1.0

- Análises e Conciliação passa a contar com a subaba Relatório Gerencial.
- Relatório Gerencial consolida ranking, sites deficitários, clientes dos deficitários e sites ativos sem clientes.
- Relatório Gerencial pode ser baixado em PDF.

## 1.0.99

- Migração passa a recarregar latitude, longitude e altura ao trocar o cliente selecionado.
- Resultado anterior da migração é limpo quando o cliente muda, evitando cálculo antigo na tela.

## 1.0.98

- Migração passa a manter o site atual do cliente na lista de sites possíveis.
- Removida a coluna adicional de site atual nos resultados de migração.

## 1.0.97

- Migração deixa de solicitar altitude do terreno do cliente.
- Altitude do cliente em migração passa a ser sempre obtida via Open-Elevation durante o cálculo.
- Resultados de migração passam a exibir o site atual do cliente.

## 1.0.96

- Cálculo de visada passa a ter teste garantindo a altura aplicada nas duas pontas do enlace.
- Gráfico do perfil de visada passa a exibir hastes entre o solo e a altura final em origem e destino.
- Tooltip das pontas passa a mostrar solo, altura aplicada e altura final.

## 1.0.95

- Gráfico do perfil de visada passa a suavizar visualmente o terreno para reduzir aparência em degraus.
- Suavização não altera os dados técnicos, ponto crítico, margem ou classificação da visada.
- Hover do terreno passa a mostrar valor real e valor suavizado.

## 1.0.94

- Viabilidade passa a manter o último resultado calculado na sessão.
- Trocar o site no Perfil de visada deixa de apagar os resultados após o rerun do Streamlit.

## 1.0.93

- Gráfico do perfil de visada passa a usar escala vertical focada na altitude do trajeto.
- Terreno do perfil deixa de preencher a área até altitude zero, melhorando a leitura visual.
- Testes do gráfico de visada passam a validar escala, base visual e traços principais.

## 1.0.92

- Perfil de visada passa a ser exibido em gráfico interativo.
- Gráfico do perfil exibe relevo, linha de visada, zona de Fresnel e ponto crítico.
- Dados técnicos do perfil ficam recolhidos em detalhe para conferência.

## 1.0.91

- Novo módulo Viabilidade com subabas Viabilidade, Migração e Estudos de Engenharia.
- Viabilidade passa a calcular visada com curvatura da Terra, zona de Fresnel e elevação via Open-Elevation.
- Migração passa a salvar dados técnicos locais de clientes para latitude, longitude, altitude e altura.
- Sistema passa a ter configurações de Open-Elevation, frequência, Fresnel e amostragem.

## 1.0.90

- Sites Deficitários passa a gerar relatório executivo para apresentação à diretoria.
- Relatório executivo exibe resumo por site, justificativa, clientes associados e download em Excel.
- Exportação do relatório inclui abas de resumo, sites, clientes, ações, severidade e parâmetros usados.

## 1.0.89

- Ranking de sites passa a carregar o nome cadastral do resumo de Topologia.
- Coluna Nome Cadastro do ranking passa a ser exibida como Nome.

## 1.0.88

- Ranking de sites passa a exibir Nome Cadastro como primeira coluna.
- Ranking de sites passa a exibir Nome SNMPc como última coluna.

## 1.0.87

- Ranking de sites passa a usar o custo real do resumo de Topologia.
- Ranking de sites passa a exibir somente Nome SNMPc, Receita Total, Clientes Total e Custo.
- Valores numéricos do ranking passam a aceitar textos monetários simples sem zerar o custo.

## 1.0.86

- Ranking de sites passa a exibir a coluna Custo.
- Tabelas de maior e menor receita passam a usar uma visão padronizada do ranking.

## 1.0.85

- Módulo Mapa passa a ter subabas Mapa Geral e Mapa Personalizado.
- Mapa Geral exibe apenas busca e mapa, usando cache geral compilado.
- Mapa Personalizado preserva filtros, resumo, exportação e tabelas do mapa atual.

## 1.0.84

- Equipamentos > Buscar equipamentos passa a usar filtros por lista para Ícone, Fabricante, Modelo e Tipo.
- Filtros de equipamentos passam a ser encadeados, exibindo apenas opções compatíveis com os demais filtros selecionados.
- Busca de equipamentos passa a ter botão para limpar os filtros aplicados.

## 1.0.83

- Sistema passa a ter subaba Exportações para download pontual de dados operacionais.
- Exportações incluem Clientes, SNMPc, Sites, Equipamentos, Mapa, Produtos, Contatos, índice de documentos e LOG.
- Exportação não inclui arquivos sensíveis de usuários, sessões, senhas ou chaves de API.

## 1.0.82

- Base de equipamentos passa a usar Modelo no lugar de Nome.
- Base de equipamentos passa a ter os campos Fabricante e Software.
- Importação e leitura continuam aceitando planilhas antigas com a coluna Nome, convertendo para Modelo.

## 1.0.81

- Clientes > Consulta passa a detalhar equipamentos com nome e IP.
- Nome do equipamento prioriza cadastro da base de equipamentos e usa ícone SNMPc como fallback.
- IP do equipamento passa a vir do endereço importado do device no SNMPc.

## 1.0.80

- Clientes > Consulta passa a exibir o GoTo SNMPc do cliente.
- GoTo SNMPc é obtido da estrutura importada do SNMPc pelo número da assinatura.

## 1.0.79

- Clientes > Consulta passa a exibir Links úteis para Aquiles e Zabbix.
- Links úteis são gerados automaticamente a partir da assinatura do cliente.
- Links externos abrem em nova aba.

## 1.0.78

- Clientes > Consulta passa a exibir Site SNMPc e Setorial como links de texto.
- Links do resumo do cliente usam query params para abrir Gerenciamento de Sites ou Topologia.
- Navegação remove os parâmetros da URL após carregar o destino.

## 1.0.77

- Clientes > Consulta passa a permitir abrir o Site SNMPc no Gerenciamento de Sites.
- Clientes > Consulta passa a permitir abrir a Topologia pelo Setorial do cliente.
- Gerenciamento de Sites > Resumo Financeiro passa a exibir somente Clientes total e Sites filhos.

## 1.0.76

- Topologia passa a carregar automaticamente a tabela de clientes dos sites selecionados.
- Clientes da Topologia podem ser selecionados e abertos diretamente em Clientes > Consulta.
- Consulta de Clientes passa a aceitar abertura direta por assinatura vinda de outros módulos.

## 1.0.75

- Topologia passa a exibir o filtro de Sites antes do filtro de Tipos.
- Busca de sites na Topologia passa a fechar a lista após selecionar um site.
- Botão Limpar foi reposicionado ao lado de Tipos e reseta filtros sem alterar widgets já renderizados.

## 1.0.74

- Clientes > Consulta passa a usar base leve para carregar mais rápido.
- Busca de clientes passa a usar rótulos pré-calculados para evitar varreduras repetidas do DataFrame.
- Resumo do cliente passa a exibir Setorial.

## 1.0.73

- Clientes > Consulta passa a usar busca pesquisável em linha, no padrão da gestão de sites.
- Consulta de cliente passa a exibir resumo direto sem tabelas auxiliares.
- Base de clientes passa a propagar o campo Gerente Contas da planilha.

## 1.0.72

- Métrica de produtos por banda na Topologia passa a contar produtos com 100 Mbps ou mais.
- Rótulo da métrica foi ajustado para “Produtos a partir de 100 Mbps”.

## 1.0.71

- Topologia passa a exibir métricas de banda Telecom também no resumo dos sites selecionados.
- Resumo considera o mesmo escopo dos sites usados, respeitando a opção de incluir sites filhos.
- Cópia do resumo passa a incluir maior banda, somatória das bandas e produtos acima de 100 Mbps.

## 1.0.70

- Gerenciamento de Sites passa a ter botão discreto para criar novo site.
- Novo cadastro reutiliza a subaba Editar com formulário em branco.
- Fluxo de criação limpa a seleção atual sem alterar a edição de sites existentes.

## 1.0.69

- Módulo Ferramentas passa a ser exibido como Equipamentos, mantendo as chaves técnicas de permissão.
- Grade de permissões passa a agrupar Enlaces e bases de equipamentos em Equipamentos.
- Topologia passa a exibir maior banda Telecom ativa, somatória das bandas ativas e quantidade de produtos acima de 100 Mbps no resumo do site.

## 1.0.68

- Grade de permissões dos perfis passa a seguir a ordem lógica dos módulos do sistema.
- Permissões de Suporte, Ferramentas, Sistema, Valores e Tabelas foram reorganizadas visualmente.
- Rótulos das permissões foram padronizados sem alterar as chaves técnicas dos perfis.

## 1.0.67

- Criado módulo Suporte com subabas Agendamento, Retirada e Prédios.
- Subabas Retirada e Prédios foram movidas de Ferramentas para Suporte.
- Agendamento permite buscar uma assinatura e montar dados operacionais para visita técnica.

## 1.0.66

- Usuários Master passam a receber lembrete mensal quando a importação do SNMPc ou da base de clientes estiver pendente no mês atual.
- Lembrete usa o histórico de importações bem-sucedidas e mostra a última data conhecida de cada base.

## 1.0.65

- Gerenciamento de Sites > Documentos passa a exibir documentos ativos e arquivados em tabelas selecionáveis.
- Ações de baixar, arquivar, retornar e excluir definitivamente passam a operar sobre os documentos selecionados.
- Download de múltiplos documentos passa a gerar ZIP em memória.

## 1.0.64

- Gerenciamento de Sites > Documentos passa a exigir confirmação antes de arquivar documentos ativos.

## 1.0.63

- Gerenciamento de Sites > Documentos passa a exibir arquivados em tabela compacta nativa.
- Documentos arquivados podem ser retornados para a pasta principal do site mediante confirmação.
- Documentos arquivados podem ser excluídos definitivamente mediante confirmação textual.
- Versão exibida passa a usar o arquivo `VERSION`, evitando ficar presa em variável antiga do Docker.

## 1.0.62

- Gerenciamento de Sites > Documentos passa a aceitar múltiplos arquivos no upload por seleção ou arrastar e soltar.
- Lista de documentos arquivados passa a usar altura compacta para evitar espaços vazios grandes.

## 1.0.61

- Ferramentas > Enlaces passa a exibir aviso de carregamento durante a montagem dos enlaces.
- Filtro de enlaces de clientes cancelados passa a excluir infraestrutura e enlaces entre sites.
- Ferramentas > Buscar equipamentos passa a permitir filtrar somente equipamentos de clientes cancelados.

## 1.0.60

- Backup passa a usar sempre o destino persistente `/app/backups`, mapeado para `./backups` no servidor.
- Tela de Backup deixa de aceitar pasta livre para evitar gravação fora do volume Docker.
- Configurações antigas com caminhos customizados de backup são normalizadas automaticamente.

## 1.0.59

- Clone limpo passa a abrir uma tela de primeira execução quando os arquivos obrigatórios ainda não existem.
- Primeira execução permite restaurar backup ZIP ou importar inicialmente SNMPc, Sites e clientes.
- Versão dos dados passa a tratar SNMPc ausente sem derrubar o carregamento inicial.

## 1.0.58

- Backup passa a ter subaba própria dentro de Sistema, separado da aba Configurações.
- Perfis passam a exibir a permissão visual Backup na grade de permissões.

## 1.0.57

- Backup passa a ter restauração segura por snapshot, com validação do ZIP e confirmação textual.
- Restauração pode usar backup já salvo ou arquivo enviado por upload, sempre criando backup pré-restauração.
- Documentos dos sites em `contracts/` continuam opcionais no backup e também na restauração.

## 1.0.56

- Importador do SNMPc passa a identificar enlaces `Network` e enlaces por equipamentos backbone/OSPF entre sites, sem alterar a hierarquia principal.
- Mapa passa a desenhar enlaces SNMPc entre sites, incluindo POP x POP e POP x DC.
- Ferramentas > Enlaces passa a listar enlaces SNMPc entre sites com origem, destino e metadados do link.

## 1.0.55

- Mapa passa a permitir exportação em KML e KMZ.
- Exportador permite escolher escopo, itens e informações incluídas no arquivo.
- KMZ é gerado com `doc.kml`, compatível com Google Earth.

## 1.0.54

- Cadastro de sites passa a permitir opção vazia nos campos de seleção da aba Editar.
- Campo Tipo passa a incluir a opção Cliente e deixa de assumir POP por padrão.
- Campo Relacionamento passa a incluir Sem histórico.

## 1.0.53

- Corrigida exibição da conta para não depender do campo legado `role`.
- Barra superior passa a usar `profile` como identificação principal e `role` apenas como fallback visual.
- Adicionado teste de regressão para usuários migrados sem `role`.

## 1.0.52

- Backup passa a exibir prévia de conteúdo com tamanho e quantidade de arquivos por fonte.
- Adicionado backup separado de documentos dos sites para incluir a pasta `contracts` sob demanda.
- Backup automático permanece leve por padrão, sem documentos dos sites, e a interface passa a alertar quando eles estão fora do backup.

## 1.0.51

- Arquivos vinculados aos sites passam a ser tratados como documentos do site, sem exibição de versão de contrato.
- Adicionada ação para arquivar documentos, movendo o arquivo para a subpasta `Arquivado` do respectivo site.
- Adicionada subaba Sites x Documentos em Análises e Conciliação para comparar sites cadastrados com pastas existentes em `contracts`.

## 1.0.50

- Contratos passam a usar a pasta raiz `contracts` como armazenamento definitivo.
- Adicionada indexação das subpastas por Nome SNMPc em Sistema > Configurações.
- Arquivos `.msg` passam a ser aceitos como documentos contratuais, e arquivos de sistema como `Thumbs.db` são ignorados.

## 1.0.49

- Tabelas passam a diferenciar colunas monetárias de percentuais.
- Margem e rentabilidade passam a ser exibidas como percentual, enquanto receita, custo, resultado e prejuízo permanecem em R$.
- Clientes impactados passa a indicar Vínculo Direto ou Indireto.

## 1.0.48

- Corrigido o botão Copiar tabela para usar componente HTML executável no Streamlit.
- A cópia continua respeitando permissões de cópia e de visualização de valores.
- Mantido o formato TSV para colar diretamente em planilhas.

## 1.0.47

- Sites Deficitários e Baixa Margem passa a incluir sites filhos e clientes dos filhos por padrão.
- Receita, custo, clientes, resultado, margem, custo por cliente e ticket médio passam a considerar a árvore completa quando a opção está ativa.
- Tabela de clientes impactados acompanha o mesmo escopo da análise e passa a listar clientes dos sites filhos.

## 1.0.46

- Sites Deficitários passa a apoiar também análise de sites positivos com baixa margem ou baixo lucro.
- Adicionado filtro opcional de Resultado mínimo para analisar faixas específicas de resultado.
- Campos Resultado máximo, Prejuízo mínimo e Margem máxima receberam textos de ajuda para orientar análises de baixa rentabilidade.

## 1.0.45

- Sites Deficitários passa a aceitar prejuízo mínimo negativo para analisar sites próximos do equilíbrio.
- O critério negativo cria uma faixa por resultado, permitindo incluir pequenos prejuízos, equilíbrio e pequeno lucro conforme o Resultado máximo configurado.
- Mantido Prejuízo Mensal como valor visual não negativo para preservar a leitura financeira do relatório.

## 1.0.44

- Sites Deficitários passa a permitir configurar critérios operacionais de entrada na lista.
- Adicionados parâmetros para incluir ou restringir sites ativos, presentes no SNMPc e com clientes.
- Critérios financeiros como resultado máximo, prejuízo mínimo, margem, custo por cliente e clientes necessários para equilíbrio passam a controlar a montagem da lista.

## 1.0.43

- Adicionada subaba Sites Deficitários em Análises e Conciliação.
- O relatório lista somente sites ativos, presentes no SNMPc, com clientes e resultado financeiro negativo.
- Incluídas métricas de prejuízo, filtros decisórios, ranking de sites, clientes impactados e resumo por ação sugerida.

## 1.0.42

- Custos x receita passa a selecionar sites diretamente na tabela Resumo por site escolhido.
- Adicionado botão Carregar novo filtro para substituir o filtro principal pelos sites marcados no resumo.
- Removido o campo separado Refinar pelos sites do resultado.

## 1.0.41

- Custos x receita passa a permitir refinar o resultado selecionando sites da tabela gerada pelo filtro inicial.
- Métricas e detalhamento do relatório passam a considerar o refinamento pelos sites selecionados.
- Adicionada tabela final com clientes e sites associados ao escopo filtrado, incluindo assinatura, produto, receita e setorial.

## 1.0.40

- Tela de criação/edição de usuários deixa de exibir a lista completa de permissões herdadas como texto fixo.
- Seleção de perfil passa a atualizar fora do formulário e mostra apenas a contagem de permissões.
- Detalhes das permissões herdadas ficam disponíveis em uma grade expansível.

## 1.0.39

- Removido o uso de perfis e permissões legadas baseadas em `role`, permissões por usuário e flags antigas.
- Permissões efetivas passam a vir somente do perfil associado ao usuário.
- Tela de usuários deixa de exibir perfil legado e passa a salvar apenas o perfil atual.
- Usuários existentes foram migrados para perfis e os campos legados foram removidos do arquivo de usuários.

## 1.0.38

- Tela de perfis passa a exibir permissões em grade por módulo, com seleção por checkbox.
- Perfil Master permanece bloqueado com todas as permissões habilitadas.
- Corrigido o arquivo `VERSION` para acompanhar a versão mais recente do histórico.

## 1.0.37

- Círculos do mapa passam a usar 25% de transparência, ficando mais opacos.
- Clientes passam de azul para cinza.
- Pontos de sites priorizam o tipo no próprio nome, evitando BH aparecer verde por herança de POP.

## 1.0.36

- Clientes do mapa passam a ser exibidos em azul com 50% de transparência.
- Círculos de sites, clientes e busca foram reduzidos para 50% do tamanho anterior.
- Linhas até clientes passam a usar a cor do site de origem.

## 1.0.35

- Corrigidos os accessors do PyDeck nos círculos do mapa para usarem colunas técnicas sem espaços.
- Cores POP, BH e REP deixam de cair para preto durante a renderização dos marcadores.

## 1.0.34

- Padronizadas as cores dos círculos do mapa: POP em verde, BH em laranja e REP em amarelo.
- Círculos passam a usar 50% de transparência e o cache do mapa foi versionado para evitar reaproveitar cores antigas.

## 1.0.33

- Círculos do mapa passam a usar limites mínimo e máximo em pixels, mantendo visibilidade durante zoom manual.
- Raios continuam representados em metros, mas agora não somem quando o mapa está afastado nem crescem demais quando aproximado.

## 1.0.32

- Círculos do mapa passam a usar raio em metros com escala dinâmica baseada no zoom inicial.
- Em mapas afastados, os círculos aumentam automaticamente para permanecerem visíveis; em zoom próximo, retornam ao tamanho base.

## 1.0.31

- Corrigidos os círculos do mapa para usarem tamanho fixo em pixels, evitando que desapareçam no zoom/satélite.
- Mantidos círculos simples e transparentes, agora com borda clara para melhorar contraste.

## 1.0.30

- Marcadores do mapa voltam a usar círculos simples em metros, agora menores e mais transparentes.
- Removidos halo e centro dos marcadores para reduzir poluição visual sobre ruas e satélite.

## 1.0.29

- Adicionado halo claro aos marcadores do mapa para melhorar a visibilidade sobre satélite.
- Marcadores passam a usar borda escura e centro colorido pela setorial, com linhas de vínculo menos opacas.

## 1.0.28

- Ampliado novamente o tamanho dos marcadores do mapa para ficarem próximos ao tamanho de um cursor na tela.
- Reforçadas bordas e centro dos marcadores para melhorar a leitura sobre imagens de satélite.

## 1.0.27

- Aumentado o tamanho dos marcadores do mapa para melhorar a leitura sobre ruas e satélite.
- Sites, clientes e busca mantêm tamanho fixo em pixels, agora com raio e centro mais visíveis.

## 1.0.26

- Corrigida a exibição dos pontos do mapa usando marcadores geométricos em pixels no lugar de `IconLayer`.
- Sites, clientes e busca passam a usar pontos pequenos com borda e centro contrastante, mantendo cores por setorial.

## 1.0.25

- Corrigida novamente a renderização dos ícones do mapa, trocando SVG inline por PNG base64 gerado internamente.
- Mantidos pinos para sites e busca, alvo menor para clientes, cores por setorial e compatibilidade com `IconLayer`.

## 1.0.24

- Corrigida a renderização dos marcadores do mapa, substituindo símbolos em texto por ícones SVG embutidos via `IconLayer`.
- Mantidas as cores por setorial, tooltips, rótulos de distância e vínculos, com marcadores visíveis também em visualização satélite.

## 1.0.23

- Substituídos os círculos grandes do mapa por marcadores tipo pino e alvos discretos na coordenada exata.
- Sites, clientes e endereço pesquisado passam a usar marcadores visuais diferentes sem alterar o cache do mapa.
- Mantidos tooltips, vínculos e rótulos de distância com melhor leitura sobre ruas e satélite.

## 1.0.22

- Corrigido o botão Limpar busca do mapa para evitar alteração tardia do estado do widget.
- A busca do mapa passa a centralizar e aproximar os resultados sem ocultar os demais itens plotados.
- Endereços externos encontrados por geocodificação passam a abrir com zoom mais próximo no marcador temporário.

## 1.0.21

- Adicionada busca na aba Mapa para localizar sites, clientes, vínculos, itens não plotados e endereços externos.
- A busca filtra e centraliza os itens plotados encontrados, refletindo também nas tabelas do mapa.
- Endereços externos encontrados por geocodificação passam a aparecer como marcador temporário sem alterar o cache do mapa.

## 1.0.20

- Adicionadas configurações avançadas do mapa para distância máxima site x site, distância máxima site x cliente e limite padrão de clientes.
- A compilação do mapa passa a usar os limites configurados e registra o limite aplicado nos itens não plotados.
- A chave de cache do mapa passa a considerar os limites configurados para evitar reaproveitamento indevido.

## 1.0.19

- Criado o módulo principal Insights com subabas gerenciais para visão geral, financeiro, clientes, sites, operacional e riscos.
- Adicionadas permissões específicas para Insights e bloqueio de acesso para usuários sem visualização de valores de clientes e custos.
- Centralizados os cálculos gerenciais em serviço dedicado, usando dados de sites, clientes, produtos, equipamentos, contatos e cache do mapa.

## 1.0.18

- Criado o módulo principal Clientes com consulta, ficha detalhada, relatórios e insights.
- Adicionadas permissões específicas para Clientes, Consulta, Relatórios e Insights.
- Centralizada a montagem da base de clientes ativos em serviço dedicado, com enriquecimento por site, produto e equipamentos.

## 1.0.17

- Padronizada a execução dos testes dentro do ambiente Docker da aplicação.
- Adicionado script `scripts/test_in_container.sh` para construir a imagem e executar a suíte em container temporário.
- Incluída a pasta `tests` na imagem Docker para permitir validação no mesmo ambiente da aplicação.
- Atualizada a documentação de testes para evitar execução no Python local do host.

## 1.0.16

- Alterado o mapa interativo da edição de sites para usar satélite MapTiler por padrão quando configurado.
- Adicionada confirmação antes de aplicar coordenadas escolhidas por clique no mapa.
- Mantido fallback em OpenStreetMap quando não houver chave MapTiler configurada.

## 1.0.15

- Adicionado mapa interativo na edição de sites para definir Latitude e Longitude clicando no mapa.
- Mantido o preenchimento por endereço como ponto inicial para ajuste manual/interativo.
- Adicionadas dependências `folium` e `streamlit-folium` para suporte ao mapa interativo.

## 1.0.14

- Alterado o padrão do mapa para abrir em visualização por satélite.
- Reduzido o limite padrão de clientes na compilação do mapa para 100.

## 1.0.13

- Movida a aba SVA para dentro de Produtos como subaba.
- Criada a aba Histórico com subabas para Sites removidos e Clientes cancelados.
- Mantida compatibilidade com permissões antigas e redirecionamento das abas removidas para a nova estrutura.

## 1.0.12

- Ajustado o logout para retornar diretamente à tela de login após revogar a sessão.
- Tokens antigos no cookie passam a ser ignorados quando a sessão já foi revogada, evitando tela parada em `Saindo...`.

## 1.0.11

- Ajustado novamente o logout para limpar o cookie fora do popover e evitar tela vazia após clicar em Sair.
- Removido o uso de iframe para limpeza do cookie de autenticação.

## 1.0.10

- Corrigido o botão Sair para revogar a sessão, apagar o cookie de autenticação e interromper o fluxo da página imediatamente.
- Centralizada a limpeza do cookie de sessão em um helper dedicado no módulo `app/ui/session.py`.

## 1.0.9

- Extraído o fluxo de autenticação, sessão, cookies e barra superior para `app/ui/session.py`.
- Centralizada a troca de senha obrigatória e o logout no módulo de sessão.
- Reduzido o `dashboard.py` para delegar a preparação do usuário autenticado antes de carregar os módulos.

## 1.0.8

- Extraída a aba Topologia do `dashboard.py` para `app/ui/views/topology.py`.
- Centralizada a configuração da view de Topologia com os componentes compartilhados de tabela, cópia e formatação.
- Reduzido o `dashboard.py` para ficar mais próximo de um orquestrador das abas principais.

## 1.0.7

- Extraído o módulo de Mapa do `dashboard.py` para `app/ui/views/map.py`.
- Movidas regras de escopo e resumo de seleção de sites para `app/services/site_metrics.py`.
- Reduzido o acoplamento do dashboard com serviços internos de mapa, mantendo-o como orquestrador das abas.

## 1.0.6

- Ajustado o padrão visual do mapa para linhas vermelhas entre sites e linhas verdes entre site e cliente.
- Adicionados distância, setorial e equipamento no detalhe dos clientes no mapa.
- O equipamento exibido no mapa passa a usar o nome cadastrado na base de equipamentos ou o ícone quando não houver nome.

## 1.0.5

- Atualizado o mapa para colorir sites, clientes e vínculos por setorial.
- Adicionados rótulos de distância nas linhas de vínculo do mapa.
- Enriquecidos os detalhes dos pontos do mapa com endereço, coordenadas, quantidade de clientes, produto e receita.

## 1.0.4

- Removido o fundo preto do contêiner da logo no cabeçalho e na tela de login.
- A logo configurada passa a ser usada também como ícone da aba do navegador.

## 1.0.3

- Removido o fundo, borda e sombra da caixa de identidade visual para aproveitar melhor a imagem de fundo.
- A área com logo, título e descritivo passa a ficar transparente no cabeçalho e na tela de login.

## 1.0.2

- Corrigido loop de login/logout quando a URL ficava presa com `?logout=1`.
- Tokens inválidos passam a limpar o cookie diretamente, sem inserir parâmetro de logout na URL.
- O sistema remove automaticamente o parâmetro legado `logout` quando ele aparece na URL.

## 1.0.1

- Adicionado suporte a imagem de fundo carregada de `config/IMG` ou `config/img`.
- O sistema passa a procurar automaticamente arquivos `fundo`, `fundo.png`, `fundo.jpg`, `fundo.jpeg`, `fundo.webp` ou `fundo.svg`.
- Aplicado overlay claro/escuro para manter legibilidade da interface sobre a imagem.

## 1.0.0

- Varredura de pré-publicação para estabilizar a primeira versão pública da plataforma.
- Removidos dados persistidos acidentalmente dentro de `app/config/`, impedindo que usuários e histórico entrem na imagem Docker.
- Bloqueado `app/config/` no `.dockerignore` e no `.gitignore`.
- Removido arquivo residual `teste.py` e limpos arquivos `__pycache__`.
- Substituído `streamlit.components.v1.html` por `st.html` com JavaScript controlado para evitar API depreciada.
- Adicionado atributo `Secure` ao cookie de sessão quando o SGS estiver publicado em HTTPS.
- Adicionado bloqueio temporário de login após 5 falhas consecutivas por usuário.
- Ajustadas permissões locais de arquivos sensíveis sempre que permitido pelo sistema de arquivos.

## 2026.06.12-2144

- Substituídas as subabas internas por navegação persistente com estado de sessão.
- Corrigido o retorno automático para a primeira subaba em Gerenciamento de Sites, Ferramentas, Produtos, Sistema, Análises e Ajuda.
- Criado componente comum de subnavegação para padronizar o comportamento em toda a plataforma.

## 2026.06.12-2136

- Criado manual interativo no botão de ajuda, com busca por palavra-chave e navegação por seção.
- Adicionada aba FAQ na ajuda, com perguntas frequentes pesquisáveis.
- Criado arquivo `docs/FAQ.md` para manutenção das respostas frequentes.

## 2026.06.12-2130

- Removida a tabela redundante com uma única linha em Gerenciamento de Sites > Resumo Financeiro.
- O resumo financeiro individual passa a exibir apenas os indicadores e as tabelas de detalhamento financeiro.

## 2026.06.12-2125

- Adicionado botão "Carregar mapa" na Topologia para abrir o Mapa com os sites filtrados.
- Adicionado botão "Carregar na Topologia" no Mapa para retornar à Topologia com o filtro atual.
- A navegação preserva seleção de sites e opção de incluir sites filhos.

## 2026.06.12-2122

- Renomeada a interface "Base de produtos" para "Editar Produtos".
- Renomeada a interface "Base de equipamentos" para "Editar Equipamentos".
- Atualizado o rótulo da permissão de equipamentos para refletir a nova nomenclatura.

## 2026.06.12-2112

- Corrigida a instabilidade da chave do seletor "Colunas exibidas".
- A seleção de colunas deixa de ser desfeita instantaneamente nas tabelas do mapa, incluindo "Clientes".

## 2026.06.12-2109

- Corrigida a atualização das tabelas ao alterar "Colunas exibidas".
- A grade passa a ser recriada quando a seleção de colunas muda, evitando exibição presa no estado anterior.
- Adicionado botão "Restaurar" para voltar a exibir todas as colunas de uma tabela.

## 2026.06.12-2104

- O mapa passa a calcular e armazenar distâncias entre cliente e site pai e entre site pai e site filho.
- Clientes e sites filhos com distância acima de 30 km deixam de ser plotados para evitar erros de endereço ou geocodificação.
- A aba "Não plotados" passa a registrar o motivo, a distância calculada e o limite aplicado.

## 2026.06.12-2054

- Adicionado MapTiler como provedor padrão de geocodificação de endereços.
- A configuração do mapa passa a permitir escolher o provedor de geocodificação.
- O cache de geocodificação passa a separar resultados por provedor para evitar reaproveitar falhas antigas.

## 2026.06.12-2049

- Movidas as configurações do mapa para Sistema > Configurações.
- A visualização por satélite passa a usar `config/map_config.json` antes das variáveis de ambiente.
- Adicionado formulário para configurar provedor, chave MapTiler, estilo MapTiler e chave Mapbox.

## 2026.06.12-2045

- Adicionado suporte ao MapTiler como provedor padrão da visualização por satélite.
- Expostas as variáveis `MAPTILER_API_KEY`, `MAPTILER_TOKEN`, `MAP_SATELLITE_PROVIDER` e `MAPTILER_SATELLITE_STYLE_ID` no Docker.
- Mantido fallback para Mapbox quando `MAP_SATELLITE_PROVIDER=mapbox`.

## 2026.06.12-1457

- O botão "Compilar mapa" passa a refazer também a geocodificação dos clientes do escopo.
- Endereços de clientes com cache negativo deixam de ser reaproveitados durante recompilação manual.
- Atualizado o texto do mapa para indicar que a compilação refaz a geocodificação do escopo.

## 2026.06.12-1448

- Corrigida a navegação das tabelas internas do Mapa.
- A seleção de linha em "Não plotados" deixa de retornar a subaba para "Sites".
- As visões Sites, Clientes, Vinculos e Não plotados passam a preservar a seleção durante reruns.

## 2026.06.12-1442

- Adicionada aba "Não plotados" no Mapa.
- A compilação do mapa passa a registrar sites, clientes e vínculos não exibidos.
- A nova tabela mostra o motivo de cada item não plotado, incluindo ausência de coordenada, endereço não localizado e vínculo sem ponto de origem/destino.

## 2026.06.12-1434

- Adicionada normalização para coordenadas legadas já gravadas com escala incorreta no Excel.
- Valores como `-467617514.17` passam a ser tratados como `-46.761751417` quando usados como longitude.

## 2026.06.12-1428

- Corrigida a leitura de Latitude e Longitude da planilha de Sites.
- Coordenadas com ponto decimal deixam de ser interpretadas como milhares, evitando longitudes inválidas no mapa.
- O mapa passa a plotar corretamente sites filhos que tinham coordenadas válidas no cadastro.

## 2026.06.12-1417

- Adicionado detalhamento no Gerenciamento de Sites > Resumo Financeiro.
- Incluídos filtros para exibir tabelas de Clientes diretos, Clientes indiretos, Clientes total e Sites filhos.
- As tabelas mostram dados operacionais e financeiros dos clientes/sites vinculados ao site selecionado.

## 2026.06.12-1406

- Adicionada opção "Carregar endereço no mapa" na edição do cadastro do site.
- O endereço preenchido passa a gerar Latitude e Longitude automaticamente pela geocodificação.
- A tela mostra o ponto no mapa e permite ajuste manual das coordenadas antes de salvar.
- As coordenadas editadas manualmente passam a ser os valores salvos no cadastro do site.

## 2026.06.12-1353

- Corrigido erro ao usar "Abrir site selecionado" após a navegação principal já estar renderizada.
- A troca para Gerenciamento de Sites agora usa navegação pendente aplicada no próximo rerun do Streamlit.

## 2026.06.12-1349

- Adicionado botão "Abrir site selecionado" nas tabelas que possuem coluna de site.
- Ao selecionar uma linha e abrir o site, o sistema navega para Gerenciamento de Sites com o site carregado.
- A localização do site aceita nome SNMPc, código Aquiles, código Microsiga, nome cadastral ou rótulo completo da seleção.

## 2026.06.12-1338

- Alterada a navegação principal para preservar a tela atual durante reruns do Streamlit.
- A interface deixa de voltar automaticamente para a primeira tela após cliques, salvamentos ou atualizações internas.
- A navegação principal passa a renderizar apenas a tela selecionada, reduzindo processamento desnecessário.

## 2026.06.12-1328

- Corrigida a recompilação do mapa após alteração de endereço de site.
- A chave do cache do mapa passa a considerar endereço, coordenadas e demais campos de localização dos sites.
- Ao clicar em "Compilar mapa", o sistema força nova geocodificação dos sites pelo endereço atualizado.
- O cache de mapa foi versionado para evitar reaproveitamento de pacotes antigos.

## 2026.06.12-1318

- Removida a compatibilidade com tokens antigos em URL e `localStorage`.
- A autenticação persistente passa a depender apenas do cookie `sgs_auth_token`.
- Corrigido o botão Sair para revogar a sessão e remover o cookie antes de recarregar a página.
- Removida a opção "Manter conectado neste navegador"; a sessão do navegador passa a seguir sempre a política de 24 horas.

## 2026.06.12-1307

- A sessão persistente passa a usar cookie `sgs_auth_token` com validade de 24 horas.
- O token deixa de permanecer visível na URL no fluxo normal de login.
- Tokens antigos em URL ou `localStorage` são migrados/limpos automaticamente quando possível.

## 2026.06.12-1258

- Removida a tela bloqueante "Verificando sessão salva neste navegador".
- O token persistente passa a permanecer na URL durante a sessão de 24 horas, permitindo F5 sem novo login.
- A restauração por `localStorage` fica apenas como apoio e não impede a exibição do login quando não houver token válido.

## 2026.06.12-1248

- A sessão persistente do navegador passa a durar até 24 horas.
- Ajustado o fluxo de restauração de login para reaproveitar o token salvo após F5 ou fechamento/reabertura do navegador.
- O logout passa a revogar também o token ativo mantido na sessão do Streamlit.

## 2026.06.12-1132

- Criada a subaba Sistema > Configurações.
- Adicionada rotina de backup do SGS com geração de arquivo ZIP.
- Incluídas configurações de backup automático, frequência, pasta de destino, retenção e conteúdo do backup.
- Adicionado backup manual pela interface e listagem dos backups disponíveis.
- O Docker Compose passa a montar a pasta `backups` em `/app/backups`.

## 2026.06.12-1112

- Ajustada a Base de produtos para considerar todos os produtos da planilha de clientes ativos.
- Produtos sem vínculo com site/topologia SNMPc, como itens `NEOFIREWALL`, passam a aparecer na lista de produtos.
- A base mantém o vínculo de Site e Setorial quando a assinatura estiver relacionada a um site.
- Novos produtos detectados na planilha passam a ser gravados automaticamente na base de produtos, preservando classificações existentes.

## 2026.06.12-1012

- Corrigida a identificação de sites no SNMPc quando o nome contém espaço antes do sufixo `_IP` ou `_MAC`.
- O site `CVN_BH_113520 _IP` passa a ser tratado como `CVN_BH_113520_IP` durante a importação da topologia.
- A chave de cruzamento com a planilha de Sites também normaliza esse padrão, evitando divergência entre TXT do SNMPc e cadastro.

## 2026.06.12-0959

- Criada base persistente de produtos em `config/product_catalog.json`.
- Adicionada subaba "Base de produtos" dentro da aba Produtos, com edição manual, atualização a partir dos produtos ativos e importação Excel.
- A base classifica produtos por Nome, Tipo, Grupo, Família, Velocidade e Variação.
- Incluídas classificações Telecom/SVA, Internet/VPN, NeoSoft, NeoTotal, VPN, CARRIER, NeoWifi, NeoFirewall, NeoBalance e NeoCaptive.
- Os relatórios Produtos x equipamentos e SVA passam a ser enriquecidos com a classificação da base de produtos.

## 2026.06.12-0921

- Garantida a presença da coluna `Favorecido` na tabela "Sites sem clientes na base de clientes".
- Atualizada a chave da grade dessa tabela para regenerar as preferências de colunas e permitir selecionar `Favorecido`.

## 2026.06.12-0335

- Novos usuários passam a ser marcados para troca obrigatória de senha no primeiro login.
- Redefinições de senha feitas pela administração também exigem troca no próximo acesso do usuário.
- A troca obrigatória bloqueia o carregamento do sistema até a senha ser alterada com sucesso.
- A troca de senha remove automaticamente a exigência e atualiza a sessão ativa.

## 2026.06.12-0331

- Corrigido erro ao abrir a administração de usuários causado pela coluna textual `Visualiza Valores` ser interpretada como coluna monetária.
- A detecção de colunas de custo passa a considerar apenas campos financeiros específicos, como `Custo`, `Valor Base`, `Valor Equipamento` e `Resultado`.
- O formatador monetário agora preserva valores textuais quando recebe conteúdo não numérico.

## 2026.06.12-0329

- Revisado o modelo de permissões para controlar acesso por abas e subabas.
- Adicionadas permissões especiais para visualizar valores dos clientes, visualizar valores de custos, ver a barra superior de resumo e copiar tabelas.
- O perfil Master passa a ter acesso total; os demais perfis obedecem às permissões marcadas.
- A administração de usuários separa permissões de abas/subabas das permissões especiais.
- Tabelas passam a ocultar separadamente valores de clientes e valores de custos, e botões de cópia só aparecem para usuários autorizados.

## 2026.06.12-0316

- Ajustada a aba Ferramentas > Enlaces para permitir busca por ícone, nome e tipo de equipamento.
- Os enlaces passam a ser enriquecidos com Nome, Tipo, Código e Valor da Base de equipamentos a partir do ícone do SNMPc.

## 2026.06.12-0309

- Ajustada a aba Ferramentas > Buscar equipamentos para exibir todos os equipamentos do SNMPc por padrão.
- Equipamentos sem cadastro na base de equipamentos deixam de ser filtrados automaticamente pelo campo Tipo.
- A busca garante colunas de Nome, Tipo, Código e Valor mesmo quando o ícone ainda não possui cadastro na base.

## 2026.06.12-0306

- Renomeada a aba Ferramentas > Equipamentos para Ferramentas > Equipamentos por Site.
- Criada a aba Ferramentas > Buscar equipamentos para localizar equipamentos por ícone, nome ou tipo.
- A busca exibe os dados da base de equipamentos vinculados ao SNMPc, incluindo Nome, Tipo, Código e Valor.

## 2026.06.12-0257

- Criada a aba Ferramentas > Retirada para consulta de equipamentos por assinatura.
- A nova consulta lista os equipamentos encontrados no SNMPc vinculados à assinatura informada.
- A listagem usa a base de equipamentos para exibir Ícone, Nome, Código, Tipo e Valor, além dos detalhes SNMPc de apoio.

## 2026.06.12-0245

- Adicionada importação em massa via Excel na aba Ferramentas > Base de equipamentos.
- A importação atualiza a base pelo campo `Ícone`, adicionando novos itens e preservando registros não informados na planilha.
- Incluído modelo Excel para download com as colunas `Ícone`, `Nome`, `Tipo`, `Código` e `Valor`.

## 2026.06.12-0238

- Restaurada a estrutura anterior da aba Equipamentos, removendo as subabas internas.
- Movida "Base de equipamentos" para uma aba própria dentro de Ferramentas, ao lado de Enlaces, Equipamentos e Prédios.

## 2026.06.12-0231

- Criada base persistente de equipamentos em `config/equipment_catalog.json`.
- Adicionada subaba "Base de equipamentos" dentro de Ferramentas > Equipamentos para gerenciar Ícone, Nome, Tipo, Código e Valor.
- A consulta de equipamentos passa a exibir os dados da base de referência vinculados pelo ícone do SNMPc.
- Adicionada opção para atualizar a base usando os ícones encontrados na topologia SNMPc.

## 2026.06.12-0214

- Ajustada a aba Conciliação para ignorar sites com status `Cancelado` na planilha de Sites.
- Sites cancelados deixam de ser exibidos e contabilizados tanto em "Sites ausentes no SNMPc" quanto em "Sites no SNMPc e ausentes na lista de Sites".
- A validação do status passa a tolerar variações de caixa e acentuação.

## 2026.06.12-0205

- Corrigido o salvamento da planilha `Sites.xlsx` após edição de sites para preservar a formatação original do Excel.
- A atualização do cadastro agora usa `openpyxl` para alterar células existentes em vez de recriar a pasta de trabalho com `pandas`.
- A coluna `CUSTO` passa a ser gravada como valor numérico quando informado em formato monetário, mantendo a formatação original da célula.

## 2026.06.12-0159

- Corrigida a ordem de inicialização dos callbacks das páginas extraídas para evitar `NameError` ao carregar o dashboard.
- A configuração de Análises, Gerenciamento, Produtos e Ferramentas agora ocorre após a definição dos callbacks usados por esses módulos.

## 2026.06.12-0158

- Renomeado o pacote interno de páginas de `app/ui/pages` para `app/ui/views` para evitar que o Streamlit crie a navegação lateral automática.
- Configurada a aplicação para iniciar com sidebar colapsada e ocultar os controles nativos de sidebar, preservando a navegação por abas do SGS.

## 2026.06.12-0154

- Criado `app/services/products.py` para centralizar regras de Produtos, SVA e leitura da base de clientes para métricas.
- Criado `app/ui/pages/products.py` para renderizar as abas Produtos e SVA fora do dashboard principal.
- Removidos do dashboard os blocos duplicados de Produtos/SVA, reduzindo o arquivo principal para cerca de 2.950 linhas.

## 2026.06.12-0150

- Migrado para `app/ui/pages/tools.py` o relatório Enlaces.
- Centralizadas no módulo de Ferramentas as regras de identificação de enlaces Site x Cliente e Site Pai x Filho.
- Removidos do dashboard os blocos duplicados de Enlaces e helpers compartilhados que ficaram órfãos, reduzindo o arquivo principal para cerca de 3.528 linhas.

## 2026.06.12-0147

- Migrado para `app/ui/pages/tools.py` o relatório Equipamentos.
- Centralizadas no módulo de Ferramentas a montagem, filtros, status de cliente e ranking de equipamentos.
- Removidos do dashboard os blocos duplicados de Equipamentos, reduzindo o arquivo principal para cerca de 3.960 linhas.

## 2026.06.12-0144

- Migrado para `app/ui/pages/tools.py` o relatório Prédios.
- Centralizada no módulo de Ferramentas a montagem de prédios por site e o botão de cópia dos códigos.
- Removidos do dashboard os blocos duplicados de Prédios, reduzindo o arquivo principal para cerca de 4.275 linhas.

## 2026.06.12-0141

- Criado `app/ui/pages/tools.py` para iniciar a separação estrutural da área Ferramentas.
- Movida para o novo módulo a orquestração das subabas Enlaces, Equipamentos e Prédios.
- O dashboard passa a delegar a montagem das subabas de Ferramentas para a página dedicada, mantendo os relatórios individuais como callbacks temporários.

## 2026.06.12-0139

- Migrada para `app/ui/pages/analysis.py` a Conciliação SNMPc x Sites.
- Centralizadas no módulo de Análises as regras de comparação entre topologia SNMPc, planilha Sites e referências por equipamento.
- Removidos do dashboard os blocos duplicados de conciliação, reduzindo o arquivo principal para cerca de 4.458 linhas.

## 2026.06.12-0137

- Migrado para `app/ui/pages/analysis.py` o relatório Custos x receita.
- Mantido o cálculo financeiro em `app/reports/site_financials.py`, com a renderização e filtros agora centralizados na página de Análises.
- Removidos do dashboard os blocos duplicados do relatório financeiro e o import obsoleto correspondente.

## 2026.06.12-0134

- Migrados para `app/ui/pages/analysis.py` os relatórios Sem vínculo e Ranking.
- Removidos do dashboard os blocos duplicados desses relatórios.
- Reduzido o arquivo principal do dashboard para cerca de 4.874 linhas.

## 2026.06.12-0132

- Migrados para `app/ui/pages/analysis.py` os relatórios Sites sem clientes e Clientes no SNMPc cancelado.
- Centralizadas no módulo de Análises as montagens de dados e filtros desses dois relatórios.
- Removidos do dashboard os blocos duplicados desses relatórios, reduzindo o arquivo principal para cerca de 5.009 linhas.

## 2026.06.12-0130

- Criado `app/ui/pages/analysis.py` para iniciar a separação estrutural da área Análises e Conciliação.
- Movida para o novo módulo a orquestração das subabas de relatórios e a regra unificada de permissões.
- O dashboard passa a delegar a montagem das subabas de análise para a página dedicada, mantendo os relatórios individuais como callbacks temporários.

## 2026.06.12-0128

- Migrado para `app/ui/pages/site_management.py` o formulário da subaba Editar do Gerenciamento de Sites.
- Centralizados no módulo de Gerenciamento os helpers de CEP, opções cadastradas, normalização e montagem do registro de site.
- Removidos do dashboard os helpers antigos de cadastro/edição e os imports de cadastro que ficaram obsoletos.

## 2026.06.12-0124

- Removidos do `app/ui/dashboard.py` os blocos duplicados de contatos e a tela legada de gerenciamento antigo de sites.
- Limpados imports de contatos e exportação de sites que ficaram obsoletos no dashboard.
- Reduzido o arquivo principal do dashboard para cerca de 6.127 linhas, mantendo contatos no módulo `app/ui/pages/site_management.py`.

## 2026.06.12-0122

- Migrado para `app/ui/pages/site_management.py` o editor de contatos usado na aba Gerenciamento de Sites.
- A subaba Contatos passa a usar funções próprias do módulo de Gerenciamento, sem depender de callback do dashboard.
- Adicionadas ao módulo de Gerenciamento as rotinas de listagem, inclusão, edição, exclusão e importação de contatos.

## 2026.06.12-0119

- Removidos do `app/ui/dashboard.py` os helpers legados de Resumo Financeiro, Detalhes e Arquivos de contrato já migrados para `app/ui/pages/site_management.py`.
- Removidos imports de contrato que ficaram obsoletos no dashboard.
- Reduzido o arquivo principal do dashboard para cerca de 7.035 linhas, mantendo o Gerenciamento de Sites delegado ao módulo de página.

## 2026.06.11-1655

- Migradas para `app/ui/pages/site_management.py` as renderizações de Resumo Financeiro, Detalhes e Arquivos de contrato da aba Gerenciamento de Sites.
- Adicionada configuração de callbacks da página de Gerenciamento para grid, moeda e usuário logado.
- Reduzida a dependência da página em callbacks temporários do dashboard, preservando a seleção de site e as subabas existentes.

## 2026.06.11-1650

- Criado `app/ui/pages/site_management.py` para iniciar a separação estrutural da aba Gerenciamento de Sites.
- A seleção do site e a orquestração das subabas de Resumo Financeiro, Detalhes, Arquivos de contrato, Contatos e Editar passam a ser delegadas ao módulo de página.
- Mantidos os helpers existentes no dashboard como callbacks temporários para preservar comportamento durante a migração gradual.

## 2026.06.11-1645

- Removidos do dashboard os blocos legados de Usuários, LOG e Importação após a extração da aba Sistema.
- Limpados imports que ficaram obsoletos no `app/ui/dashboard.py`.
- Reduzido o arquivo principal do dashboard, mantendo a aba Sistema delegada ao módulo `app/ui/pages/system.py`.

## 2026.06.11-1640

- Criado o pacote `app/ui/pages/` para separar páginas principais da interface.
- Extraída a área Sistema para `app/ui/pages/system.py`, incluindo subabas de Importação, LOG e Usuários.
- O dashboard passa a delegar a renderização da aba Sistema para o módulo dedicado, preservando permissões, logs, importação e limpeza de cache.

## 2026.06.11-1635

- Extraída a lógica de mapa e geocoding para `app/services/map_service.py`.
- Centralizados cache do mapa, cache de geocoding, chave de compilação, montagem de pontos, vínculos e dataframes do mapa.
- O dashboard passa a manter apenas a renderização PyDeck e os callbacks visuais de progresso.

## 2026.06.11-1630

- Extraídos componentes de tabela para `app/ui/components/tables.py`.
- Centralizados AgGrid, dataframe nativo, seleção de colunas, tradução de cabeçalhos e botões de cópia em módulo reutilizável.
- O dashboard passa a configurar callbacks de permissão, moeda e preferências para os componentes de tabela.

## 2026.06.11-1625

- Extraído o tema visual do dashboard para `app/ui/theme.py`.
- O CSS global, regras responsivas mobile, estilos de métricas, abas, botões e tabelas passam a ficar centralizados em módulo próprio.
- O arquivo principal do dashboard foi reduzido e mantém apenas a chamada de aplicação do tema.

## 2026.06.11-1620

- Extraído o branding do dashboard para `app/ui/branding.py`.
- Centralizada a resolução da logo, fallback SVG e bloco visual SGS em módulo dedicado.
- O dashboard passa a consumir o branding por importação, reduzindo acoplamento visual no arquivo principal.

## 2026.06.11-1615

- Iniciada a refatoração estrutural do dashboard, extraindo cálculos puros para módulos dedicados.
- Criado `app/services/site_metrics.py` para métricas de árvore de sites, receita e descendentes.
- Criado `app/reports/site_financials.py` para consolidação financeira/cadastral e relatório `Custos x receita`.
- O dashboard passa a delegar essas regras para os novos módulos, reduzindo acoplamento entre UI e cálculo.

## 2026.06.11-1610

- Adicionado cache em sessão para os detalhes consolidados de sites, reduzindo recálculos entre abas.
- Melhorada a responsividade mobile de cabeçalho, abas, métricas, botões e tabelas.
- Adicionada paginação automática no AgGrid para tabelas com mais de 100 linhas.
- Substituídos prints de importação e sincronização por registros no log do sistema.

## 2026.06.11-1605

- Adicionada a opção `Apenas sites ativos` no relatório `Custos x receita`, marcada por padrão.
- O cálculo padrão passa a ignorar sites cancelados, inclusive quando eles aparecem como filhos de sites selecionados.
- A lista de seleção do relatório passa a exibir apenas sites ativos enquanto a opção estiver marcada.

## 2026.06.11-1600

- Ajustado o layout dos indicadores para evitar corte em valores longos de receita, custo e resultado.
- Os cards passam a adaptar a fonte e permitir quebra segura do texto conforme o espaço disponível.

## 2026.06.11-1555

- Criada a subaba `Custos x receita` em `Análises e Conciliação`.
- O relatório permite escolher um ou mais sites e definir se os sites filhos entram no cálculo.
- Adicionados resumo por site escolhido, totais de receita/custo/resultado/margem e detalhamento dos sites considerados.

## 2026.06.11-1550

- Incluído suporte à coluna `Favorecido` da planilha `Sites`.
- O campo passa a ser lido, exibido nos detalhes do site, editável no cadastro e mantido na exportação para Excel.
- A busca do gerenciamento de sites passa a considerar também o nome do favorecido.

## 2026.06.11-1545

- Revisados os textos exibidos aos usuários com correções ortográficas em português brasileiro.
- Ajustados rótulos de menus, mensagens, filtros, mapa, usuários, logs e documentação de uso.
- Mantidas chaves internas e nomes técnicos das planilhas sem alteração para preservar importações e regras de processamento.

## 2026.06.11-1540

- Removida a exibição da lista de clientes cancelados legados.
- Limpo o histórico legado de cancelamentos gerado pela regra antiga.
- O controle de clientes cancelados passa a considerar apenas novas importações.

## 2026.06.11-1535

- Renomeada a aba `Sites` para `Topologia`.
- Criada a aba `Ferramentas` com subabas `Enlaces`, `Equipamentos` e `Prédios`.
- Criada a aba `Sistema` com subabas `Importação`, `LOG` e `Usuários`.
- As permissões antigas continuam controlando quais subabas cada usuário acessa.

## 2026.06.11-1530

- Criada a pasta persistente `config/branding` para armazenar a logo do sistema.
- A logo passa a ser carregada primeiro de `config/branding/Neovia-Logo-Branco.png`.
- Tambem sao aceitos os formatos `.jpg`, `.jpeg` e `.svg` com o mesmo nome base.
- Mantido o SVG interno como fallback quando nao houver arquivo na pasta de branding.

## 2026.06.11-1525

- Corrigido o enquadramento da logo Neovia para evitar corte no cabecalho.
- Incluida a identidade visual `SGS` tambem na tela de login.
- Incluida a mesma identidade visual no fluxo de criacao do primeiro usuario Master.

## 2026.06.11-1520

- Alterada a identidade visual do sistema para `SGS`.
- Atualizado o descritivo para `Sistema de gerenciamento de Sites`.
- Adicionada a logo Neovia Solutions no cabecalho do sistema.
- Atualizado o titulo do navegador e o manual de uso com o novo nome.

## 2026.06.11-1510

- Modernizado o layout geral do sistema com nova camada visual responsiva.
- Atualizado o cabecalho com identidade visual, chip de versao e melhor organizacao.
- Melhorada a aparencia de abas, metricas, botoes, filtros, expansores, alertas, grids e rodape.
- Mantida a estrutura operacional das telas existentes.

## 2026.06.10-1500

- Unificadas as abas `Conciliação`, `Ranking`, `Sem vinculo`, `Sites sem clientes` e `Clientes no SNMPc cancelado` em `Análises e Conciliação`.
- A nova aba usa subabas internas para manter os relatorios separados.
- As permissoes antigas continuam controlando quais subabas cada usuario pode acessar.

## 2026.06.10-1455

- Realizada checagem de seguranca no sistema.
- O token de autenticacao passa a ser removido da URL apos sincronizacao com o navegador.
- Downloads de contratos passam a validar que o arquivo esta dentro da pasta de contratos.
- Uploads de contratos passam a validar extensao e limite de tamanho no backend.
- Arquivos JSON gravados pelo sistema passam a usar permissao restrita `600`.

## 2026.06.10-1450

- Adicionada a aba "Sites sem clientes".
- A nova aba lista sites sem clientes vinculados na base atual, com detalhes cadastrais e valores do site.
- Incluidos filtros por busca, tipo e status, alem de metricas de custo, receita e resultado.

## 2026.06.10-1445

- Adicionada a aba "Clientes no SNMPc cancelado".
- A nova aba lista assinaturas existentes no SNMPc que nao existem na base de clientes atual.
- A listagem inclui detalhes encontrados na topologia SNMPc e nos equipamentos vinculados a assinatura.
- Usuarios com acesso a "Clientes cancelados" tambem podem acessar a nova aba.

## 2026.06.10-1440

- A migracao do historico de clientes cancelados preserva a data real da ultima importacao.

## 2026.06.10-1435

- Corrigida a regra de "Clientes cancelados" para usar comparacao entre bases de clientes sucessivas.
- Registros antigos gerados pela diferenca SNMPc x base de clientes foram movidos para uma area legada do historico.
- A aba "Clientes cancelados" passa a separar cancelamentos reais de registros legados/inconsistentes.
- A importacao deixa de classificar assinaturas presentes no SNMPc e ausentes na base como cancelamentos comerciais.

## 2026.06.10-1420

- A aba "Clientes sem vinculo" passa a exibir tambem as colunas `Produto` e `Mensalidade`.
- A importacao de clientes preserva produto e mensalidade nos registros sem vinculo.
- A busca de clientes sem vinculo passa a considerar cliente, assinatura e produto.

## 2026.06.10-1415

- Padronizada a exibicao dos sites em seletores e listas de busca unica no formato `Nome SNMPc - Codigo Aquiles / Nome - Codigo Microsiga`.
- Aplicado em detalhes contratuais, contatos, gerenciamento unificado, predios, equipamentos e enlaces.
- Campos de selecao multipla de sites permanecem sem alteracao.

## 2026.06.10-1410

- Padronizados os campos de busca/selecao unica de site para iniciar em branco e pesquisar diretamente no seletor.
- A mudanca foi aplicada a detalhes contratuais legado, contatos legado, sites removidos, predios, equipamentos e enlaces.
- Campos que permitem selecionar varios sites continuam inalterados.

## 2026.06.10-1400

- A selecao de site no "Gerenciamento de Sites" voltou a usar o seletor nativo do Streamlit.
- A lista fecha corretamente apos a escolha do site pesquisado.
- O campo continua iniciando em branco e permite pesquisar diretamente na lista.

## 2026.06.10-1355

- Corrigida a selecao no campo unico de busca do "Gerenciamento de Sites".
- Os resultados do autocomplete agora usam links de navegacao para carregar o site selecionado de forma confiavel.
- O campo de busca passa a adaptar cores ao tema claro/escuro do navegador.

## 2026.06.10-1350

- A selecao de site no "Gerenciamento de Sites" passa a usar um unico campo de busca com lista de resultados integrada.
- A lista interna exibe somente sites cujo rotulo contenha exatamente os caracteres digitados.
- Ao selecionar um resultado, o site e aberto diretamente nas subabas de gerenciamento.

## 2026.06.10-1345

- Corrigida a pesquisa de sites no "Gerenciamento de Sites" para exibir somente itens cujo rotulo contenha exatamente os caracteres buscados.
- A busca foi separada do filtro flexivel nativo do seletor, evitando resultados indevidos como correspondencias aproximadas.

## 2026.06.10-1340

- Na aba "Gerenciamento de Sites", a busca de site voltou para uma unica linha.
- O seletor inicia em branco e permite pesquisar diretamente no campo antes da selecao.

## 2026.06.10-1335

- Na aba "Gerenciamento de Sites", a selecao de site passa a iniciar em branco.
- Adicionado campo de pesquisa antes da selecao do site.
- A lista de sites passa a exibir somente resultados que contenham os caracteres pesquisados.

## 2026.06.10-1330

- Na aba "Gerenciamento de Sites", os arquivos de contrato foram separados em subaba propria.
- Subabas renomeadas para `Resumo Financeiro`, `Detalhes`, `Arquivos de contrato`, `Contatos` e `Editar`.
- A subaba `Contatos` passa a aparecer antes de `Editar`.
- A selecao do site passa a exibir `Nome SNMPc - Codigo Aquiles / Nome - Codigo Microsiga`.

## 2026.06.10-1325

- Unificadas as abas `Detalhes financeiros`, `Detalhes contratuais`, `Gerenciar Sites` e `Contatos dos Sites` em uma unica aba `Gerenciamento de Sites`.
- A nova aba exige primeiro a selecao de um site e, a partir dela, apresenta subabas de detalhes financeiros, detalhes contratuais, cadastro e contatos.
- Mantida compatibilidade de permissao para usuarios que tinham acesso as abas antigas de detalhes financeiros ou contratuais.

## 2026.06.10-1310

- As novas pastas de contratos passam a incluir o nome do site junto ao `Codigo Aquiles`, facilitando a localizacao manual dos arquivos.
- Contratos ja registrados continuam apontando para o caminho original salvo no historico.

## 2026.06.10-1305

- Adicionada gestao de arquivos de contrato na aba "Detalhes contratuais".
- Cada site pode receber varias versoes de contrato vinculadas ao `Codigo Aquiles`.
- O historico registra versao sequencial, identificacao, observacao, arquivo original, usuario, data e tamanho.
- Contratos ficam persistidos em `config/contracts` e o indice em `config/site_contracts.json`.
- A tela permite baixar qualquer versao enviada.

## 2026.06.10-1245

- Contatos de sites agora aceitam multiplos telefones e multiplos emails por contato.
- A aba `CONTATOS` passa a exportar as colunas `Telefones` e `Emails`, mantendo compatibilidade de importacao com `Telefone` e `Email`.
- Os formularios de inclusao/edicao de contatos usam campos de texto multilinha para telefones e emails.

## 2026.06.10-1235

- Criada a aba "Contatos dos Sites" para visualizar e gerenciar contatos por site.
- Ao selecionar um site, a aba apresenta os contatos vinculados ao `Codigo Aquiles`.
- A aba permite incluir, editar e excluir contatos com tipo, nome, telefone e email.
- A nova aba reutiliza a permissao de "Gerenciar Sites" para manter acesso aos usuarios atuais.

## 2026.06.10-1225

- A aba `CONTATOS` passa a preservar tambem a coluna `Nome`, mantendo o layout atualizado enviado na planilha de Sites.
- O campo `CUSTO` no cadastro de Sites passa a aceitar texto, preservando valores como `Permuta`.
- A leitura do cadastro normaliza `CUSTO` como texto para evitar avisos de conversao no grid quando houver valores mistos.

## 2026.06.10-1215

- Atualizadas as nomenclaturas da aba "Conciliação SNMPc x Sites" para `Sites ausentes no SNMPc` e `Sites no SNMPc e ausentes na lista de Sites`.
- A aba `CONTATOS` da planilha `Sites.xlsx` passa a usar somente `Codigo Aquiles` como chave do contato.
- Importacoes antigas com coluna `SMNPC` em contatos continuam sendo aceitas, mas a coluna nao e mais mantida na exportacao.

## 2026.06.10-1200

- Atualizado o cadastro de Sites para o novo layout com `Codigo Aquiles`, `Codigo Microsiga`, `Codigo Condominio`, `Abreviacao` e `Relacionamento`.
- Mantida compatibilidade de leitura com colunas antigas como `Codigo` e `Microsiga`.
- Criada a aba/tabela `CONTATOS` no arquivo `Sites.xlsx`, permitindo varios contatos por site com tipo de contato, telefone e email.
- Adicionada gestao de contatos no modulo "Gerenciar Sites", com inclusao, remocao, consulta e importacao em massa por Excel/CSV.
- A exportacao de Sites passa a gerar as abas `BASE` e `CONTATOS`.

## 2026.06.03-1556

- Quando um site nao possui latitude/longitude cadastradas, o mapa passa a tentar localizar o site pelo endereco usando o cache local de geocoding.
- A configuracao do Mapbox foi exposta no Docker via `MAPBOX_API_KEY` e enviada explicitamente ao PyDeck para a visualizacao por satelite.
- O cache compilado do mapa recebeu uma nova versao de schema para evitar reaproveitamento de pacotes gerados antes da geocodificacao por endereco dos sites.

## 2026.06.03-1545

- Reformulada a aba "Mapa" para selecionar multiplos sites antes da exibicao.
- Adicionadas opcoes para carregar sites filhos e clientes no escopo selecionado.
- O mapa passa a compilar e salvar um pacote local em cache por escopo, reduzindo a carga durante o uso.
- Adicionadas visualizacoes de ruas e satelite.
- Sites sao marcados com icone de torre, clientes com pontos coloridos, clientes ligados ao site por linha verde e sites filhos ligados ao pai por linha vermelha mais grossa.

## 2026.06.03-1504

- Ajustado historico de sites removidos para reconhecer renomeacoes por `Predio`.
- Quando um site muda de nome/tipo, por exemplo `REP` para `BH`, mas permanece com o mesmo predio ativo, ele nao e mais registrado como removido.

## 2026.06.03-1134

- Adicionado botao de ajuda no cabecalho, ao lado do usuario.
- O botao abre o manual de uso `docs/USO.md` dentro do dashboard.

## 2026.06.03-1130

- Criada documentacao de uso em `docs/USO.md`.
- Atualizado `README.md` com referencia ao manual.

## 2026.06.03-1030

- Removido o campo `ENDEREÇO COMPLETO` do cadastro/exportacao de Sites.
- A secao "Localizacao" do formulario de sites foi reorganizada na ordem: `CEP`, `Endereco`, `Numero`, `Bairro`, `Cidade`, `UF`, `Latitude`, `Longitude`.

## 2026.06.03-1025

- Adicionado campo `NUMERO` ao cadastro/exportacao de Sites.
- A base antiga com numero junto em `ENDEREÇO` passa a ser separada automaticamente quando houver padrao `Endereco, numero`.
- `Endereco completo` permanece como campo consolidado com endereco, numero, bairro, cidade e UF.

## 2026.06.03-1020

- No modulo "Gerenciar Sites", o preenchimento do CEP agora consulta automaticamente o endereco via ViaCEP quando houver 8 digitos.
- Os campos `Endereco`, `Bairro`, `Cidade`, `UF` e `Endereco completo` passam a ser preenchidos automaticamente quando o CEP for encontrado.
- A edicao de sites deixou de usar `st.form` para permitir atualizacao imediata dos campos ao digitar o CEP.

## 2026.06.03-1016

- Na aba "Gerenciar Sites", a secao "Incluir ou editar site" passa a aparecer antes da consulta/exportacao.

## 2026.06.03-1012

- Removido o botao separado "Marcar site como cancelado" do modulo "Gerenciar Sites".
- O cancelamento de site passa a ser feito apenas pela alteracao do campo `Status` no formulario de edicao.

## 2026.06.03-1009

- No modulo "Gerenciar Sites", os campos `Contrato`, `Categoria`, `Perfil`, `Restricao` e `Status` agora usam listas predefinidas a partir dos valores ja cadastrados na planilha `Sites`.
- O valor atual do registro permanece disponivel mesmo quando estiver fora da lista ja cadastrada.

## 2026.06.03-1000

- Adicionado modulo "Gerenciar Sites".
- O modulo permite consultar e exportar a lista de sites em Excel no formato da planilha `Sites`.
- Usuarios Master/Adm podem incluir sites, editar detalhes contratuais/operacionais/localizacao e marcar sites como cancelados.
- Adicionados campos de contato ao cadastro e exibicao dos contatos na aba "Detalhes contratuais".
- Alteracoes no cadastro geram backup automatico da planilha anterior em `imports/archive`.

## 2026.06.03-0946

- Adicionado controle "Incluir sites filhos" na aba "Detalhes financeiros".
- Ao selecionar sites, o filtro pode considerar automaticamente todos os descendentes.
- O filtro de status da aba "Detalhes financeiros" passa a abrir por padrao com apenas "Ativo" selecionado quando esse status existir.

## 2026.06.03-0938

- Alterado o filtro da aba "Detalhes financeiros" para selecao multipla de sites.
- O seletor segue o mesmo comportamento da aba "Sites", permitindo escolher varios sites diretamente.

## 2026.06.03-0936

- Adicionado campo "Buscar sites" na aba "Detalhes financeiros".
- A busca aceita um ou varios termos separados por virgula, ponto e virgula ou quebra de linha.
- A busca considera `Site SNMPc`, `SNMPc`, `Nome Cadastro`, `Codigo` e `Microsiga`.

## 2026.06.03-0933

- Adicionada identificacao de versao visivel no dashboard.
- Adicionado arquivo `VERSION` como fonte local da versao atual.
- Adicionado `CHANGELOG.md` para historico humano das alteracoes.
- Mantidas melhorias da rodada anterior: configuracao centralizada, storage JSON atomico,
  carregamento de dados em servico, testes basicos e Docker com persistencia explicita.
