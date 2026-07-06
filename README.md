# SGS

Dashboard Streamlit para importar a estrutura SNMPc, cruzar com bases Excel e
visualizar sites, clientes, equipamentos, conciliacoes e logs.

## Execucao local

```bash
python -m pip install -r requirements.txt
streamlit run app/ui/dashboard.py
```

## Docker

```bash
docker compose up --build
```

O compose monta `imports/`, `config/`, `cache/` e `rede.db` como dados
persistentes.

## Configuracao

Os caminhos podem ser sobrescritos por variaveis de ambiente:

- `SNMPC_IMPORTS_DIR`
- `SNMPC_CONFIG_DIR`
- `SNMPC_CACHE_DIR`
- `SNMPC_CLIENTES_FILE`
- `SNMPC_FILE`
- `DATABASE_URL`

## Versão

A versão atual fica em `VERSION` e aparece no cabeçalho do dashboard.
Registre cada mudança em `CHANGELOG.md`.

Para sobrescrever a versão em runtime:

```bash
SNMPC_APP_VERSION=2026.06.03-0933 docker compose up -d
```

## Documentacao de uso

O manual de uso e o FAQ para usuários do dashboard estão em:

```text
docs/USO.md
docs/FAQ.md
docs/PERFIL_NOC.md
docs/PERFIL_SUPORTE.md
```

## Testes

Os testes devem ser executados dentro do mesmo ambiente Docker da aplicação.
Isso evita divergência de dependências entre o host e o container.

```bash
sh scripts/test_in_container.sh
```

O script constrói a imagem do serviço `snmpc-dashboard` e executa a suíte em um
container temporário, usando as mesmas dependências e variáveis do app.
