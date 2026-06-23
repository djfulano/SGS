# FAQ - SGS

## Como identifico a versão do sistema?

A versão aparece no cabeçalho do SGS, ao lado da identidade visual. Ela também
pode ser conferida no arquivo `VERSION` e no histórico `CHANGELOG.md`.

## Como encontro rapidamente uma função do sistema?

Abra o botão de ajuda no cabeçalho e use o campo de busca do manual. Pesquise
por termos como `mapa`, `backup`, `contatos`, `importação`, `contratos`,
`produtos`, `equipamentos` ou `permissões`.

## Como atualizo os dados do SNMPc e da base de clientes?

Acesse **Sistema > Importação**, envie o TXT do SNMPc e/ou a planilha de
clientes, informe a data da importação e clique em **Validar e importar dados**.

## Onde configuro usuários e permissões?

Acesse **Sistema > Usuários**. Usuários Master podem liberar acesso a abas,
subabas, visualização de valores, resumo superior e cópia de tabelas.

## Como altero a senha?

Use o ícone do usuário no cabeçalho e clique em **Trocar senha**. Novos usuários
devem alterar a senha no primeiro login.

## Como gerencio um site?

Acesse **Gerenciamento de Sites**, selecione o site no campo de busca e navegue
pelas subabas **Resumo Financeiro**, **Detalhes**, **Arquivos de contrato**,
**Contatos** e **Editar**.

## Como cancelo um site?

Abra o site em **Gerenciamento de Sites > Editar**, altere o campo **Status**
para `Cancelado` e salve.

## Como adiciono contatos de um site?

Abra **Gerenciamento de Sites > Contatos**, selecione ou crie o contato e adicione
telefones e e-mails conforme necessário.

## Como envio contratos?

Abra **Gerenciamento de Sites > Arquivos de contrato**. É possível enviar várias
versões, mantendo histórico por site.

## Como uso o mapa?

Acesse **Mapa**, selecione os sites, escolha se deseja carregar sites filhos e
clientes, e clique em **Compilar mapa** quando quiser atualizar coordenadas e
geocodificação.

## Por que alguns itens não aparecem no mapa?

Itens sem coordenadas, sem endereço localizado ou com distância acima de 30 km
do site pai são exibidos na aba **Não plotados**, com o motivo.

## Onde configuro MapTiler?

Acesse **Sistema > Configurações > Mapa** e informe a chave MapTiler. Essa chave
é usada para satélite e geocodificação, quando MapTiler está selecionado.

## Como faço backup?

Acesse **Sistema > Configurações > Backup do sistema**. É possível configurar
backup automático ou clicar em **Executar backup agora**.

## Como exporto dados para Excel?

Use os botões de exportação disponíveis nas telas de cadastro e gerenciamento.
No gerenciamento de sites, a exportação segue o formato da planilha `Sites`.

## Por que não vejo valores financeiros?

Seu usuário pode não ter permissão para visualizar valores de clientes ou custos.
Solicite revisão das permissões a um usuário Master.

## Como copiar uma tabela?

Use o botão **Copiar tabela** quando disponível. Essa função depende da permissão
**Pode copiar tabelas**.

## Como altero as colunas exibidas em uma tabela?

Abra o expansor **Colunas exibidas**, marque ou desmarque as colunas desejadas
e, se necessário, use **Restaurar** para voltar a exibir todas.

## O que fazer quando um endereço está errado no mapa?

Edite o site em **Gerenciamento de Sites > Editar**, ajuste o endereço ou as
coordenadas e depois recompile o mapa.

## O que significa cliente sem vínculo?

É um cliente que aparece na base de clientes, mas não foi associado corretamente
a um site na estrutura SNMPc.

## Onde vejo inconsistências entre SNMPc e Sites?

Acesse **Análises e Conciliação**. As subabas mostram ausências, rankings,
sites sem clientes e clientes encontrados no SNMPc mas cancelados na base.
