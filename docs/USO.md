# Manual de uso - SGS

Este documento orienta o uso do SGS, Sistema de gerenciamento de Sites, para
consulta de sites, clientes, equipamentos, detalhes financeiros, contratos,
importação de dados e gestão do cadastro de sites.

## Acesso

1. Acesse o dashboard pelo navegador:

   ```text
   http://localhost:8501
   ```

2. Informe usuário e senha.
3. Após o login, confira a versão exibida no cabeçalho. Ela deve ser a última
   versão registrada em `VERSION` e `CHANGELOG.md`.

Na primeira execução, se não existir usuário cadastrado, o sistema solicita a
criação do primeiro usuário Master.

## Perfis e permissões

O sistema trabalha com três perfis:

- `Master`: acesso completo, incluindo gestão de usuários.
- `Adm`: acesso administrativo aos módulos operacionais.
- `Usuário`: acesso conforme permissões liberadas pelo Master.

Permissões de visualização e acesso a módulos são configuradas na aba
**Usuários**. Valores financeiros podem ser ocultados para usuários sem permissão
de visualizar valores.

Documento complementar:

- `docs/PERFIL_NOC.md`: resumo das principais funções recomendadas para o
  perfil NOC.

## Navegação geral

As abas disponíveis dependem das permissões do usuário. As principais são:

- **Topologia**: consulta de sites, receitas e clientes vinculados.
- **Gerenciamento de Sites**: resumo financeiro, detalhes, contratos, contatos e edição cadastral.
- **Análises e Conciliação**: conciliação, ranking, custos x receita, clientes sem vínculo e demais inconsistências.
- **Ferramentas**: enlaces, equipamentos e prédios.
- **Mapa**: visualização geográfica de clientes.
- **Produtos** e **SVA**: visões operacionais.
- **Sistema**: importação, logs, configurações e usuários.
- **LOG**: auditoria de eventos do sistema.

## Aba Sites

Use esta aba para selecionar um ou mais sites e analisar receita/clientes.

1. Escolha os tipos de site desejados.
2. Selecione um ou mais sites.
3. Marque ou desmarque **Incluir sites filhos**.
4. Consulte os indicadores e tabelas exibidas.

Quando **Incluir sites filhos** está marcado, o resumo considera também os sites
descendentes da seleção.

## Detalhes financeiros

Esta aba mostra os dados financeiros por site.

Filtros disponíveis:

- **Sites**: seleção múltipla de sites.
- **Incluir sites filhos**: inclui descendentes dos sites selecionados.
- **Tipos**: filtra POP, BH, REP, DC etc.
- **Status**: por padrão abre com `Ativo` selecionado, quando esse status existir.
- **Somente sites no SNMPc**: limita a sites encontrados na estrutura SNMPc.

Os indicadores exibem sites, receita, custo, resultado, margem e contagens de
sites negativos, sem custo ou fora do SNMPc.

## Detalhes contratuais

Use esta aba para consultar dados cadastrais de um site.

O seletor de site permite buscar por SNMPc, nome, código e nome de cadastro.
São exibidos:

- identificação;
- contrato;
- localização;
- dados operacionais;
- observações;
- contatos.

## Gerenciar Sites

Este módulo gerencia os sites que possuem contrato.

Usuários com permissão ao módulo podem consultar e exportar. Apenas `Master` e
`Adm` podem incluir ou editar registros.

### Incluir um site

1. Abra **Gerenciar Sites**.
2. Em **Registro**, escolha `Novo site`.
3. Preencha os campos obrigatórios de identificação.
4. Preencha contrato, perfil, localização, dados operacionais e contatos.
5. Clique em **Salvar site**.

### Editar um site

1. Abra **Gerenciar Sites**.
2. Em **Registro**, selecione o site desejado.
3. Altere os campos necessários.
4. Clique em **Salvar site**.

Antes de salvar, o sistema cria backup automático da planilha anterior em:

```text
imports/archive
```

### Cancelar um site

Para cancelar um site, edite o registro e altere o campo **Status** para
`Cancelado`. Em seguida clique em **Salvar site**.

### CEP e endereço

Ao digitar um CEP com 8 dígitos, o sistema consulta automaticamente o ViaCEP e
preenche:

- `Endereço`
- `Bairro`
- `Cidade`
- `UF`

O campo `Número` deve ser preenchido separadamente.

A ordem dos campos de localização é:

```text
CEP, Endereço, Número, Bairro, Cidade, UF, Latitude, Longitude
```

### Campos com opções cadastradas

Os campos abaixo usam as opções já existentes na planilha:

- `Contrato`
- `Categoria`
- `Perfil`
- `Restrição`
- `Status`

O campo `Favorecido` armazena o nome usado pelo sistema de pagamentos da empresa.

### Exportar Sites para Excel

Na seção **Consultar e exportar sites**, clique em **Exportar Sites Excel**.

O arquivo exportado segue o formato usado pela planilha `Sites`, incluindo os
campos de contato e o campo `NUMERO` separado de `ENDEREÇO`.

## Importação de dados

A aba **Importação** permite atualizar:

- estrutura SNMPc TXT;
- base de clientes Excel.

Procedimento:

1. Envie o arquivo desejado.
2. Informe a data da importação.
3. Clique em **Validar e importar dados**.
4. Aguarde a conclusão e confira a mensagem de sucesso.

Quando um arquivo existente é substituído, o sistema arquiva uma cópia em
`imports/archive`.

## Backup do sistema

A rotina de backup fica em **Sistema > Configurações**.

Usuários Master ou Adm podem configurar:

- ativação do backup automático;
- frequência: diário, semanal ou mensal;
- pasta de destino;
- quantidade de backups mantidos;
- conteúdo do backup: arquivos importados, configurações, cache, banco SQLite,
  versão e documentação.

O botão **Executar backup agora** cria um ZIP imediatamente. Por padrão, no
Docker, os backups ficam em:

```text
backups
```

O backup automático é verificado durante o uso do sistema. Quando a frequência
configurada é atingida, o SGS cria um novo ZIP e registra o evento no **LOG**.

## Arquivos principais

Os dados principais ficam em:

- `imports/snmpc.txt` ou `imports/SNMPc.txt`: estrutura SNMPc.
- `imports/clientes.xlsx`: base de clientes.
- `imports/sites.xlsx`: cadastro de sites/contratos.
- `config/users.json`: usuários.
- `config/import_history.json`: histórico de importação.
- `config/logs`: logs de usuários e sistema.
- `config/backup_config.json`: configurações da rotina de backup.
- `backups`: arquivos ZIP gerados pela rotina de backup.
- `rede.db`: banco SQLite sincronizado.

## Logs e auditoria

A aba **LOG** mostra eventos de usuário e sistema, incluindo:

- logins;
- alterações de senha;
- importações;
- erros de processamento;
- alterações no cadastro de sites.

Use **Carregar +100** para visualizar mais registros.

## Versão do sistema

A versão atual aparece no cabeçalho do dashboard.

Também pode ser conferida no arquivo:

```text
VERSION
```

O histórico de alterações fica em:

```text
CHANGELOG.md
```

## Boas práticas

- Confira a versão no cabeçalho antes de iniciar alterações.
- Antes de importar dados, confirme que o arquivo está no formato esperado.
- Para cancelar sites, altere apenas o campo `Status`.
- Use o botão de exportação antes de grandes alterações cadastrais, se quiser uma cópia extra.
- Verifique a aba **LOG** após operações importantes.
- Em celulares, prefira começar pelos resumos e use a paginação das tabelas para navegar por listas grandes.
