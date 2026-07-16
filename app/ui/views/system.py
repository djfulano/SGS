import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from app.auth import MODULES
from app.auth import UsersFileError
from app.auth import all_permissions
from app.auth import can_manage_users
from app.auth import create_user
from app.auth import effective_permissions
from app.auth import has_permission
from app.auth import load_profiles
from app.auth import load_users
from app.auth import save_profiles
from app.auth import save_users
from app.config import ARCHIVE_DIR
from app.config import BACKUP_DIR
from app.config import CLIENTES_FILE
from app.config import TMP_IMPORTS_DIR
from app.data_history import load_history
from app.data_history import update_history
from app.importers.excel_importer import ler_clientes_base
from app.importers.structure_importer import caminho_estrutura_txt
from app.logs import carregar_logs_sistema
from app.logs import carregar_logs_usuario
from app.logs import registrar_log_sistema
from app.logs import registrar_log_usuario
from app.services.backup_service import FREQUENCIAS_BACKUP
from app.services.backup_service import calcular_fontes_backup
from app.services.backup_service import criar_backup
from app.services.backup_service import inspecionar_backup
from app.services.backup_service import listar_backups
from app.services.backup_service import load_backup_config
from app.services.backup_service import read_backup_file
from app.services.backup_service import restaurar_backup
from app.services.backup_service import save_backup_config
from app.services.database_service import sincronizar_banco
from app.services.contract_service import CONTRACTS_DIR
from app.services.contract_service import index_contract_folders
from app.services.contract_service import migrar_pastas_documentos_para_codigo_aquiles
from app.services.data_export_service import arquivo_para_download
from app.services.data_export_service import caminho_exportacao_clientes
from app.services.data_export_service import caminho_exportacao_sites
from app.services.data_export_service import caminho_exportacao_snmpc
from app.services.data_export_service import exportar_contatos_sites_excel
from app.services.data_export_service import exportar_equipamentos_excel
from app.services.data_export_service import exportar_indice_documentos_excel
from app.services.data_export_service import exportar_logs_excel
from app.services.data_export_service import exportar_mapa
from app.services.data_export_service import exportar_produtos_excel
from app.services.map_settings import PROVEDORES_GEOCODING
from app.services.map_settings import PROVEDORES_SATELITE
from app.services.map_settings import load_map_config
from app.services.map_settings import save_map_config
from app.ui.navigation import mostrar_subnavegacao
from app.ui.components.tables import primeira_linha_selecionada


def mostrar_usuarios(
    usuario_atual,
    mostrar_grid,
    rotulos_modulos
):
    st.header("Usuários e acessos")

    if not can_manage_users(usuario_atual):
        st.warning(
            "Seu perfil não possui permissão para administrar usuários."
        )
        return

    try:
        users = load_users()
        profiles = load_profiles()
    except UsersFileError as erro:
        st.error(str(erro))
        return

    if users:
        dados_usuarios = []

        for usuario, dados in users.items():
            perfil = dados.get("profile") or ""
            permissoes_efetivas = effective_permissions(dados)
            dados_usuarios.append({
                "Usuario": usuario,
                "Perfil": perfil or "Sem perfil",
                "Permissões efetivas": ", ".join(
                    rotulos_modulos.get(
                        permissao,
                        permissao
                    )
                    for permissao in permissoes_efetivas
                ),
                "Visualiza Valores": (
                    "Sim"
                    if "visualizar_valores_clientes" in permissoes_efetivas
                    else "Não"
                )
            })

        mostrar_grid(
            pd.DataFrame(dados_usuarios),
            height=240
        )

    st.subheader("Criar ou atualizar usuário")

    usuarios_existentes = [
        "Novo usuário"
    ] + sorted(users.keys())

    usuario_edicao = st.selectbox(
        "Editar usuário existente",
        usuarios_existentes
    )

    dados_edicao = users.get(
        usuario_edicao,
        {}
    )

    nomes_perfis = sorted(profiles.keys())
    perfil_atual = dados_edicao.get("profile") or ""

    if perfil_atual and perfil_atual not in nomes_perfis:
        nomes_perfis.append(perfil_atual)

    perfil = st.selectbox(
        "Perfil",
        nomes_perfis,
        index=(
            nomes_perfis.index(perfil_atual)
            if perfil_atual in nomes_perfis
            else 0
        ),
        key=f"usuario_perfil_{usuario_edicao}"
    )

    perfil_obj = profiles.get(perfil, {})
    permissoes_perfil = perfil_obj.get("permissions", [])
    st.caption(
        f"Permissões herdadas: {len(permissoes_perfil)} permissões."
    )

    with st.expander(
        "Ver permissões herdadas",
        expanded=False
    ):
        df_permissoes_herdadas = montar_grade_permissoes_perfil(
            permissoes_perfil,
            rotulos_modulos
        )
        df_permissoes_herdadas = df_permissoes_herdadas[
            df_permissoes_herdadas["Selecionar"]
        ][[
            "Módulo",
            "Permissão"
        ]]

        if df_permissoes_herdadas.empty:
            st.info("Nenhuma permissão associada a este perfil.")
        else:
            st.dataframe(
                df_permissoes_herdadas,
                hide_index=True,
                use_container_width=True,
                height=min(
                    360,
                    42 + len(df_permissoes_herdadas) * 35
                )
            )

    with st.form("form_usuario"):
        username = st.text_input(
            "Usuário",
            value="" if usuario_edicao == "Novo usuário" else usuario_edicao,
            disabled=usuario_edicao != "Novo usuário"
        )
        password = st.text_input(
            "Senha nova",
            type="password"
        )
        salvar = st.form_submit_button("Salvar usuário")

    if salvar:
        if not username:
            st.error("Informe o usuário.")
            return

        if usuario_edicao == "Novo usuário" and not password:
            st.error("Informe a senha do novo usuário.")
            return

        if usuario_edicao != "Novo usuário" and not password:
            usuario_atualizado = dict(
                users[username]
            )
            usuario_atualizado["profile"] = perfil
            usuario_atualizado.pop("role", None)
            usuario_atualizado.pop("permissions", None)
            usuario_atualizado.pop("can_view_values", None)
            usuario_atualizado.pop("can_view_cost_values", None)
            usuario_atualizado.pop("can_copy_tables", None)
            usuario_atualizado.setdefault(
                "must_change_password",
                False
            )

            users[username] = usuario_atualizado
            evento_usuario = "usuario_atualizado"
            senha_alterada_admin = False
        else:
            users[username] = create_user(
                username,
                password,
                perfil,
                must_change_password=True,
            )
            evento_usuario = (
                "usuario_criado"
                if usuario_edicao == "Novo usuário"
                else "usuario_atualizado"
            )
            senha_alterada_admin = usuario_edicao != "Novo usuário"

        save_users(users)
        registrar_log_usuario(
            evento_usuario,
            usuario=username,
            status="sucesso",
            detalhes={
                "alterado_por": usuario_atual["username"],
                "perfil": perfil,
                "permissoes_efetivas": effective_permissions(users[username])
            }
        )

        if senha_alterada_admin:
            registrar_log_usuario(
                "senha_alterada",
                usuario=username,
                status="sucesso",
                detalhes={
                    "origem": "administracao",
                    "alterado_por": usuario_atual["username"]
                }
            )

        st.success("Usuário salvo.")
        st.rerun()

    st.subheader("Remover usuário")

    usuarios_removiveis = [
        usuario
        for usuario in users.keys()
        if usuario != usuario_atual["username"]
    ]

    if usuarios_removiveis:
        usuario_remover = st.selectbox(
            "Usuário para remover",
            usuarios_removiveis
        )

        if st.button("Remover usuário"):
            users.pop(
                usuario_remover,
                None
            )

            save_users(users)
            registrar_log_usuario(
                "usuario_removido",
                usuario=usuario_remover,
                status="sucesso",
                detalhes={
                    "alterado_por": usuario_atual["username"]
                }
            )

            st.success("Usuário removido.")
            st.rerun()


def grupo_permissao_perfil(
    chave,
    rotulo
):
    grupos_especiais = {
        "resumo_superior": "Resumo",
        "editar_sites": "Gerenciamento de Sites",
        "incluir_contatos_sites": "Gerenciamento de Sites",
        "editar_contatos_sites": "Gerenciamento de Sites",
        "gerenciar_contatos_arquivados_sites": "Gerenciamento de Sites",
        "editar_contratos_sites": "Gerenciamento de Sites",
    }

    if chave in grupos_especiais:
        return grupos_especiais[chave]

    if " > " in rotulo:
        return rotulo.split(" > ", 1)[0]

    return rotulo


ORDEM_GRUPOS_PERMISSAO = {
    "Resumo": 10,
    "Topologia": 20,
    "Gerenciamento de Sites": 30,
    "Clientes": 40,
    "Insights": 50,
    "Análises e Conciliação": 60,
    "Equipamentos": 70,
    "Suporte": 80,
    "Viabilidade": 85,
    "Gestão de Viabilidades": 87,
    "Financeiro": 89,
    "Mapa": 90,
    "Produtos": 100,
    "Histórico": 110,
    "Sistema": 120,
    "Valores": 130,
    "Tabelas": 140,
    "Ação": 150
}


def montar_grade_permissoes_perfil(
    permissoes_atuais,
    rotulos_modulos
):
    permissoes_atuais = set(permissoes_atuais or [])
    linhas = []

    for ordem, (chave, rotulo_padrao) in enumerate(MODULES):
        rotulo = rotulos_modulos.get(
            chave,
            rotulo_padrao
        )
        grupo = grupo_permissao_perfil(
            chave,
            rotulo
        )
        linhas.append({
            "Chave": chave,
            "Módulo": grupo,
            "Permissão": rotulo,
            "_ordem_modulo": ORDEM_GRUPOS_PERMISSAO.get(
                grupo,
                999
            ),
            "_ordem_permissao": ordem,
            "Selecionar": chave in permissoes_atuais
        })

    return pd.DataFrame(linhas).sort_values(
        by=[
            "_ordem_modulo",
            "_ordem_permissao"
        ],
        kind="stable"
    ).reset_index(drop=True)


def extrair_permissoes_grade_perfil(df_permissoes):
    if df_permissoes is None or df_permissoes.empty:
        return []

    permissoes = []

    for _indice, linha in df_permissoes.iterrows():
        selecionado = linha.get("Selecionar", False)

        if selecionado is True or str(selecionado).strip().lower() in {
            "true",
            "1",
            "sim"
        }:
            permissoes.append(str(linha.get("Chave") or ""))

    return [
        permissao
        for permissao in permissoes
        if permissao
    ]


def mostrar_perfis(
    usuario_atual,
    mostrar_grid,
    rotulos_modulos
):
    st.header("Perfis de acesso")

    if not has_permission(
        usuario_atual,
        "gerenciar_perfis"
    ):
        st.warning("Seu perfil não possui permissão para gerenciar perfis.")
        return

    profiles = load_profiles()
    users = load_users()

    dados_perfis = []
    for nome, perfil in profiles.items():
        usuarios = [
            usuario
            for usuario, dados in users.items()
            if dados.get("profile") == nome
        ]
        dados_perfis.append({
            "Perfil": nome,
            "Usuários": ", ".join(usuarios),
            "Qtd. permissões": len(perfil.get("permissions", [])),
            "Sistema": "Sim" if perfil.get("system") else "Não"
        })

    if dados_perfis:
        mostrar_grid(
            pd.DataFrame(dados_perfis),
            height=220,
            key="perfis_acesso_lista"
        )

    st.subheader("Criar ou editar perfil")

    opcoes = [
        "Novo perfil"
    ] + sorted(profiles.keys())
    perfil_edicao = st.selectbox(
        "Perfil",
        opcoes,
        key="perfil_acesso_edicao"
    )
    dados_edicao = profiles.get(
        perfil_edicao,
        {}
    )
    permissoes_atuais = set(
        dados_edicao.get("permissions", [])
    )
    perfil_master = perfil_edicao == "Master"

    if perfil_master:
        permissoes_atuais = set(all_permissions())

    with st.form("form_perfil_acesso"):
        nome = st.text_input(
            "Nome do perfil",
            value="" if perfil_edicao == "Novo perfil" else perfil_edicao,
            disabled=perfil_edicao != "Novo perfil"
        )

        st.caption(
            "Marque as permissões que este perfil deve possuir. "
            "As permissões estão organizadas por módulo."
        )

        df_permissoes = montar_grade_permissoes_perfil(
            permissoes_atuais,
            rotulos_modulos
        )
        permissoes_editadas = st.data_editor(
            df_permissoes,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            height=min(
                620,
                42 + len(df_permissoes) * 35
            ),
            column_order=[
                "Módulo",
                "Permissão",
                "Selecionar"
            ],
            disabled=(
                True
                if perfil_master
                else [
                    "Chave",
                    "Módulo",
                    "Permissão",
                    "_ordem_modulo",
                    "_ordem_permissao"
                ]
            ),
            column_config={
                "Chave": None,
                "_ordem_modulo": None,
                "_ordem_permissao": None,
                "Módulo": st.column_config.TextColumn(
                    "Módulo"
                ),
                "Permissão": st.column_config.TextColumn(
                    "Permissão"
                ),
                "Selecionar": st.column_config.CheckboxColumn(
                    "Selecionar"
                ),
            },
            key=f"perfil_permissoes_grade_{perfil_edicao}"
        )

        if perfil_master:
            st.caption("O perfil Master sempre possui todas as permissões.")

        salvar = st.form_submit_button("Salvar perfil")

    if salvar:
        nome = str(nome or "").strip()

        if not nome:
            st.error("Informe o nome do perfil.")
            return

        permissoes = extrair_permissoes_grade_perfil(
            permissoes_editadas
        )

        if nome == "Master":
            permissoes = all_permissions()

        profiles[nome] = {
            "name": nome,
            "permissions": sorted(set(permissoes)),
            "system": nome == "Master" or bool(dados_edicao.get("system"))
        }
        save_profiles(profiles)
        registrar_log_usuario(
            "perfil_acesso_salvo",
            usuario=nome,
            status="sucesso",
            detalhes={
                "alterado_por": usuario_atual["username"],
                "permissoes": profiles[nome]["permissions"]
            }
        )
        st.success("Perfil salvo.")
        st.rerun()

    st.subheader("Remover perfil")

    perfis_removiveis = [
        nome
        for nome, perfil in profiles.items()
        if not perfil.get("system")
    ]

    if not perfis_removiveis:
        st.caption("Nenhum perfil removível.")
        return

    perfil_remover = st.selectbox(
        "Perfil para remover",
        perfis_removiveis,
        key="perfil_acesso_remover"
    )
    em_uso = [
        usuario
        for usuario, dados in users.items()
        if dados.get("profile") == perfil_remover
    ]

    if em_uso:
        st.info(
            "Este perfil está em uso por: "
            + ", ".join(em_uso)
        )

    if st.button(
        "Remover perfil",
        disabled=bool(em_uso),
        key="perfil_acesso_remover_botao"
    ):
        profiles.pop(
            perfil_remover,
            None
        )
        save_profiles(profiles)
        registrar_log_usuario(
            "perfil_acesso_removido",
            usuario=perfil_remover,
            status="sucesso",
            detalhes={
                "alterado_por": usuario_atual["username"]
            }
        )
        st.success("Perfil removido.")
        st.rerun()


def preparar_logs_para_tabela(registros):
    dados = []

    for registro in registros:
        detalhes = registro.get("detalhes") or {}

        dados.append({
            "Data/Hora": registro.get("data_hora", ""),
            "Evento": registro.get("evento", ""),
            "Usuario": registro.get("usuario", ""),
            "Status": registro.get("status", ""),
            "Detalhes": json.dumps(
                detalhes,
                ensure_ascii=False
            ) if detalhes else ""
        })

    return pd.DataFrame(dados)


def mostrar_logs(mostrar_grid):
    st.header("LOG")

    if "limite_logs" not in st.session_state:
        st.session_state["limite_logs"] = 10

    limite = st.session_state["limite_logs"]

    col_info, col_acao = st.columns(
        [5, 1]
    )

    with col_info:
        st.caption(
            f"Mostrando as últimas {limite} ocorrências de cada log."
        )

    with col_acao:
        if st.button("Carregar +100", key="carregar_mais_logs"):
            st.session_state["limite_logs"] = min(
                limite + 100,
                5000
            )
            st.rerun()

    logs_usuario = preparar_logs_para_tabela(
        carregar_logs_usuario(
            limite=limite
        )
    )
    logs_sistema = preparar_logs_para_tabela(
        carregar_logs_sistema(
            limite=limite
        )
    )

    def mostrar_logs_usuarios():
        if logs_usuario.empty:
            st.info("Nenhum log de usuários registrado.")
        else:
            mostrar_grid(
                logs_usuario.sort_values(
                    by="Data/Hora",
                    ascending=False
                ),
                height=520,
                key="logs_usuarios"
            )

    def mostrar_logs_sistema_importacao():
        if logs_sistema.empty:
            st.info("Nenhum log de sistema registrado.")
        else:
            mostrar_grid(
                logs_sistema.sort_values(
                    by="Data/Hora",
                    ascending=False
                ),
                height=520,
                key="logs_sistema"
            )

    funcao = mostrar_subnavegacao(
        [
            (
                "usuarios",
                "Usuários",
                mostrar_logs_usuarios
            ),
            (
                "sistema_importacao",
                "Sistema e importação",
                mostrar_logs_sistema_importacao
            )
        ],
        key="logs_subaba"
    )

    if funcao:
        funcao()


def salvar_upload(uploaded_file, destino):
    with open(destino, "wb") as arquivo:
        arquivo.write(
            uploaded_file.getbuffer()
        )


def arquivar_arquivo(caminho, sufixo):
    origem = Path(caminho)

    if not origem.exists():
        return None

    pasta = ARCHIVE_DIR
    pasta.mkdir(
        parents=True,
        exist_ok=True
    )

    destino = pasta / f"{origem.stem}_{sufixo}{origem.suffix}"

    shutil.copy2(
        origem,
        destino
    )

    return destino


def substituir_arquivos_importacao(arquivos, sufixo):
    substituidos = []

    try:
        for origem_nova, destino_atual in arquivos:
            backup = arquivar_arquivo(
                destino_atual,
                sufixo
            )

            os.replace(
                origem_nova,
                destino_atual
            )

            substituidos.append(
                (destino_atual, backup)
            )
    except Exception:
        for destino_atual, backup in reversed(substituidos):
            if backup and Path(backup).exists():
                shutil.copy2(
                    backup,
                    destino_atual
                )

        raise


def mostrar_importacao(
    usuario_atual,
    carregar_dados,
    carregar_dados_de_arquivos
):
    st.header("Importação de dados")

    if not has_permission(
        usuario_atual,
        "importar_dados"
    ):
        st.warning(
            "Seu perfil não possui permissão para importar dados."
        )
        return

    history = load_history()

    st.caption(
        f"Última importação registrada: {history.get('last_import') or 'sem registro'}"
    )

    estrutura_upload = st.file_uploader(
        "Novo SNMPc TXT",
        type=["txt"]
    )

    clientes_upload = st.file_uploader(
        "Nova base de clientes Excel",
        type=["xlsx", "xls"]
    )

    data_importacao = st.date_input(
        "Data da importação"
    )

    st.info(
        "Envie apenas o arquivo que deseja atualizar. O arquivo não enviado será mantido."
    )

    if not st.button("Validar e importar dados"):
        return

    usuario_atual_nome = usuario_atual["username"]

    if not estrutura_upload and not clientes_upload:
        st.error(
            "Envie ao menos um arquivo para importar."
        )
        return

    temp_dir = TMP_IMPORTS_DIR
    temp_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    estrutura_path = Path(
        caminho_estrutura_txt()
    )
    clientes_path = CLIENTES_FILE

    nova_estrutura = temp_dir / "snmpc_novo.txt"
    novos_clientes = temp_dir / "clientes_novo.xlsx"

    if estrutura_upload:
        salvar_upload(
            estrutura_upload,
            nova_estrutura
        )
    else:
        nova_estrutura = estrutura_path

    if clientes_upload:
        salvar_upload(
            clientes_upload,
            novos_clientes
        )
    else:
        novos_clientes = clientes_path

    try:
        sites_novos, _assinaturas_novas, _equipamentos_novos = carregar_dados_de_arquivos(
            nova_estrutura,
            novos_clientes
        )
        clientes_base_importacao = ler_clientes_base(
            novos_clientes
        )
    except Exception as erro:
        registrar_log_sistema(
            "validar_importacao",
            usuario=usuario_atual_nome,
            status="erro",
            detalhes={
                "snmpc_enviado": bool(estrutura_upload),
                "clientes_enviado": bool(clientes_upload),
                "erro": str(erro)
            }
        )
        st.error(
            f"Falha ao validar importação: {erro}"
        )
        return

    registrar_log_sistema(
        "validar_importacao",
        usuario=usuario_atual_nome,
        status="sucesso",
        detalhes={
            "snmpc_enviado": bool(estrutura_upload),
            "clientes_enviado": bool(clientes_upload),
            "sites": len(sites_novos),
            "assinaturas": len(_assinaturas_novas),
            "equipamentos": len(_equipamentos_novos)
        }
    )

    sufixo = datetime.now().strftime("%Y%m%d_%H%M%S")

    arquivos_para_substituir = []

    if estrutura_upload:
        arquivos_para_substituir.append(
            (
                nova_estrutura,
                estrutura_path
            )
        )

    if clientes_upload:
        arquivos_para_substituir.append(
            (
                novos_clientes,
                clientes_path
            )
        )

    try:
        substituir_arquivos_importacao(
            arquivos_para_substituir,
            sufixo
        )

        sincronizar_banco(sites_novos)
    except Exception as erro:
        registrar_log_sistema(
            "aplicar_importacao",
            usuario=usuario_atual_nome,
            status="erro",
            detalhes={
                "snmpc_enviado": bool(estrutura_upload),
                "clientes_enviado": bool(clientes_upload),
                "erro": str(erro)
            }
        )
        st.error(
            f"Falha ao aplicar importação: {erro}"
        )
        return

    update_history(
        sites_novos,
        import_date=data_importacao.strftime("%Y-%m-%d"),
        active_clients_base=clientes_base_importacao
    )

    if hasattr(carregar_dados, "clear"):
        carregar_dados.clear()

    registrar_log_sistema(
        "aplicar_importacao",
        usuario=usuario_atual_nome,
        status="sucesso",
        detalhes={
            "snmpc_enviado": bool(estrutura_upload),
            "clientes_enviado": bool(clientes_upload),
            "data_importacao": data_importacao.strftime("%Y-%m-%d"),
            "sites": len(sites_novos)
        }
    )

    st.success(
        "Importação concluída e histórico atualizado."
    )

    st.rerun()


def mostrar_resumo_migracao_documentos(
    resumo,
    mostrar_grid,
    *,
    key_prefix
):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric(
        "Pastas",
        resumo.get("pastas_migradas", 0)
    )
    col2.metric(
        "Arquivos",
        resumo.get("arquivos_movidos", 0)
    )
    col3.metric(
        "Índice",
        resumo.get("registros_atualizados", 0)
    )
    col4.metric(
        "Conflitos",
        len(resumo.get("conflitos", []))
    )
    col5.metric(
        "Não localizadas",
        len(resumo.get("pastas_nao_localizadas", []))
    )
    col6.metric(
        "Erros",
        len(resumo.get("erros", []))
    )

    if resumo.get("conflitos"):
        st.markdown("**Conflitos de nome**")
        mostrar_grid(
            pd.DataFrame(resumo.get("conflitos", [])),
            height=240,
            key=f"{key_prefix}_conflitos"
        )

    if resumo.get("sites_sem_codigo"):
        st.markdown("**Sites sem Código Aquiles**")
        mostrar_grid(
            pd.DataFrame({
                "Site SNMPc": resumo.get("sites_sem_codigo", [])
            }),
            height=240,
            key=f"{key_prefix}_sites_sem_codigo"
        )

    if resumo.get("pastas_nao_localizadas"):
        st.markdown("**Pastas sem correspondência**")
        mostrar_grid(
            pd.DataFrame({
                "Pasta": resumo.get("pastas_nao_localizadas", [])
            }),
            height=240,
            key=f"{key_prefix}_pastas_nao_localizadas"
        )

    if resumo.get("erros"):
        st.markdown("**Erros**")
        mostrar_grid(
            pd.DataFrame(resumo.get("erros", [])),
            height=240,
            key=f"{key_prefix}_erros"
        )

        erros_texto = " ".join(
            str(erro.get("erro", ""))
            for erro in resumo.get("erros", [])
        ).casefold()
        if "permiss" in erros_texto or "permission denied" in erros_texto:
            st.warning(
                "Foram encontrados arquivos sem permissão para leitura/movimentação. "
                "No servidor de produção, ajuste a pasta `contracts` para o usuário que executa o SGS e rode a simulação novamente."
            )
            st.code(
                "APP_USER=$(ps -eo user,args | awk '/streamlit run/ && !/awk/ {print $1; exit}')\n"
                "sudo chown -R \"$APP_USER\":\"$APP_USER\" contracts config/site_contracts.json\n"
                "sudo find contracts -type d -exec chmod u+rwx {} \\;\n"
                "sudo find contracts -type f -exec chmod u+rw {} \\;",
                language="bash"
            )


def mostrar_configuracoes(
    usuario_atual,
    mostrar_grid,
    sites=None
):
    st.header("Configurações")

    if not has_permission(
        usuario_atual,
        "editar_configuracoes"
    ):
        st.warning(
            "Seu perfil não possui permissão para alterar configurações."
        )
        return

    config_mapa = load_map_config()

    st.subheader("Mapa")
    st.caption(
        "Essas configurações controlam a visualização por satélite do mapa."
    )

    chaves_provedores = list(PROVEDORES_SATELITE.keys())
    chaves_geocoding = list(PROVEDORES_GEOCODING.keys())
    provedor_atual = (
        config_mapa.get("satellite_provider")
        if config_mapa.get("satellite_provider") in chaves_provedores
        else "maptiler"
    )
    geocoding_atual = (
        config_mapa.get("geocoding_provider")
        if config_mapa.get("geocoding_provider") in chaves_geocoding
        else "maptiler"
    )

    with st.form("form_config_mapa"):
        provedor_satelite = st.selectbox(
            "Provedor de satélite",
            chaves_provedores,
            index=chaves_provedores.index(provedor_atual),
            format_func=lambda chave: PROVEDORES_SATELITE.get(
                chave,
                chave
            )
        )
        provedor_geocoding = st.selectbox(
            "Provedor de geocodificação",
            chaves_geocoding,
            index=chaves_geocoding.index(geocoding_atual),
            format_func=lambda chave: PROVEDORES_GEOCODING.get(
                chave,
                chave
            ),
            help=(
                "Usado para transformar endereços em coordenadas durante a "
                "compilação do mapa."
            )
        )
        maptiler_api_key = st.text_input(
            "Chave MapTiler",
            value=str(config_mapa.get("maptiler_api_key") or ""),
            type="password"
        )
        maptiler_style_id = st.text_input(
            "Estilo MapTiler",
            value=str(config_mapa.get("maptiler_style_id") or "hybrid"),
            help="Exemplo: hybrid, satellite ou outro estilo publicado no MapTiler."
        )
        mapbox_api_key = st.text_input(
            "Chave Mapbox",
            value=str(config_mapa.get("mapbox_api_key") or ""),
            type="password",
            help="Opcional. Use apenas se o provedor de satélite for Mapbox."
        )
        col1, col2, col3 = st.columns(3)

        with col1:
            max_site_site_distance_km = st.number_input(
                "Distância máxima site x site (km)",
                min_value=1.0,
                value=float(config_mapa.get("max_site_site_distance_km") or 30),
                step=1.0
            )

        with col2:
            max_site_client_distance_km = st.number_input(
                "Distância máxima site x cliente (km)",
                min_value=1.0,
                value=float(config_mapa.get("max_site_client_distance_km") or 30),
                step=1.0
            )

        with col3:
            default_client_limit = st.number_input(
                "Limite padrão de clientes",
                min_value=1,
                max_value=5000,
                value=int(config_mapa.get("default_client_limit") or 100),
                step=100
            )

        st.markdown("**Viabilidade e elevação**")
        open_elevation_url = st.text_input(
            "URL Open-Elevation",
            value=str(
                config_mapa.get("open_elevation_url")
                or "https://api.open-elevation.com/api/v1/lookup"
            )
        )
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            line_of_sight_sample_distance_m = st.number_input(
                "Amostragem visada (m)",
                min_value=10.0,
                value=float(config_mapa.get("line_of_sight_sample_distance_m") or 100),
                step=10.0
            )

        with col2:
            line_of_sight_frequency_ghz = st.number_input(
                "Frequência padrão (GHz)",
                min_value=0.1,
                value=float(config_mapa.get("line_of_sight_frequency_ghz") or 5.8),
                step=0.1
            )

        with col3:
            line_of_sight_fresnel_clearance = st.number_input(
                "Fresnel mínimo livre (%)",
                min_value=1.0,
                max_value=100.0,
                value=float(config_mapa.get("line_of_sight_fresnel_clearance") or 0.60) * 100,
                step=5.0
            )

        with col4:
            elevation_timeout_seconds = st.number_input(
                "Timeout elevação (s)",
                min_value=1,
                max_value=60,
                value=int(config_mapa.get("elevation_timeout_seconds") or 8),
                step=1
            )

        salvar_mapa = st.form_submit_button(
            "Salvar configurações do mapa"
        )

    if salvar_mapa:
        config_mapa = save_map_config({
            "satellite_provider": provedor_satelite,
            "geocoding_provider": provedor_geocoding,
            "maptiler_api_key": maptiler_api_key,
            "maptiler_style_id": maptiler_style_id,
            "mapbox_api_key": mapbox_api_key,
            "max_site_site_distance_km": max_site_site_distance_km,
            "max_site_client_distance_km": max_site_client_distance_km,
            "default_client_limit": default_client_limit,
            "elevation_provider": "open_elevation",
            "open_elevation_url": open_elevation_url,
            "line_of_sight_sample_distance_m": line_of_sight_sample_distance_m,
            "line_of_sight_frequency_ghz": line_of_sight_frequency_ghz,
            "line_of_sight_fresnel_clearance": line_of_sight_fresnel_clearance / 100,
            "elevation_timeout_seconds": elevation_timeout_seconds
        })
        registrar_log_sistema(
            "mapa_configuracao_salva",
            usuario=usuario_atual["username"],
            status="sucesso",
            detalhes={
                "provedor_satelite": config_mapa.get("satellite_provider"),
                "provedor_geocoding": config_mapa.get("geocoding_provider"),
                "estilo_maptiler": config_mapa.get("maptiler_style_id"),
                "maptiler_configurado": bool(
                    config_mapa.get("maptiler_api_key")
                ),
                "mapbox_configurado": bool(
                    config_mapa.get("mapbox_api_key")
                ),
                "distancia_site_site_km": config_mapa.get("max_site_site_distance_km"),
                "distancia_site_cliente_km": config_mapa.get("max_site_client_distance_km"),
                "limite_padrao_clientes": config_mapa.get("default_client_limit"),
                "open_elevation_url": config_mapa.get("open_elevation_url")
            }
        )
        st.success("Configurações do mapa salvas.")
        st.rerun()

    st.divider()

    st.subheader("Documentos dos sites")
    st.caption(
        "Novos documentos usam o Código Aquiles como nome da subpasta. "
        "Pastas legadas com Nome SNMPc continuam reconhecidas para indexação e podem ser migradas."
    )
    st.text_input(
        "Pasta de documentos",
        value=str(CONTRACTS_DIR),
        disabled=True
    )

    st.markdown("**Migração para Código Aquiles**")
    st.caption(
        "Use a simulação antes de executar em produção. A migração move arquivos de "
        "`contracts/<Nome SNMPc>/` para `contracts/<Código Aquiles>/`, preservando Arquivados."
    )
    col_migrar_1, col_migrar_2 = st.columns(2)

    if col_migrar_1.button(
        "Simular migração para Código Aquiles",
        key="simular_migracao_contracts_codigo_aquiles"
    ):
        try:
            resumo = migrar_pastas_documentos_para_codigo_aquiles(
                sites or {},
                dry_run=True,
                usuario=usuario_atual["username"]
            )
            registrar_log_sistema(
                "documentos_migracao_codigo_aquiles",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes={
                    **resumo,
                    "simulacao": True
                }
            )
            st.info(
                "Simulação concluída. Nenhum arquivo foi movido."
            )
            mostrar_resumo_migracao_documentos(
                resumo,
                mostrar_grid,
                key_prefix="documentos_migracao_simulacao"
            )
        except Exception as erro:
            registrar_log_sistema(
                "documentos_migracao_codigo_aquiles",
                usuario=usuario_atual["username"],
                status="erro",
                detalhes={
                    "simulacao": True,
                    "erro": str(erro)
                }
            )
            st.error(f"Falha ao simular migração de documentos: {erro}")

    if col_migrar_2.button(
        "Executar migração para Código Aquiles",
        key="executar_migracao_contracts_codigo_aquiles",
        type="secondary"
    ):
        try:
            resumo = migrar_pastas_documentos_para_codigo_aquiles(
                sites or {},
                dry_run=False,
                usuario=usuario_atual["username"]
            )
            registrar_log_sistema(
                "documentos_migracao_codigo_aquiles",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes={
                    **resumo,
                    "simulacao": False
                }
            )
            st.success(
                "Migração concluída. Execute a indexação da pasta contracts para conferir o índice."
            )
            mostrar_resumo_migracao_documentos(
                resumo,
                mostrar_grid,
                key_prefix="documentos_migracao_execucao"
            )
        except Exception as erro:
            registrar_log_sistema(
                "documentos_migracao_codigo_aquiles",
                usuario=usuario_atual["username"],
                status="erro",
                detalhes={
                    "simulacao": False,
                    "erro": str(erro)
                }
            )
            st.error(f"Falha ao executar migração de documentos: {erro}")

    st.markdown("**Indexação**")

    if st.button(
        "Indexar pasta contracts",
        key="indexar_pasta_contracts"
    ):
        try:
            resumo = index_contract_folders(
                sites or {},
                uploaded_by=usuario_atual["username"]
            )
            registrar_log_sistema(
                "contratos_indexacao",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes=resumo
            )
            st.success(
                "Indexação concluída. "
                f"Novos arquivos indexados: {resumo.get('arquivos_indexados', 0)}. "
                f"Já estavam no índice: {len(resumo.get('arquivos_ja_indexados', []))}."
            )

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric(
                "Sites encontrados",
                resumo.get("sites_encontrados", 0)
            )
            col2.metric(
                "Não localizados",
                len(resumo.get("sites_nao_localizados", []))
            )
            col3.metric(
                "Novos indexados",
                resumo.get("arquivos_indexados", 0)
            )
            col4.metric(
                "Já indexados",
                len(resumo.get("arquivos_ja_indexados", []))
            )
            col5.metric(
                "Ignorados",
                len(resumo.get("arquivos_ignorados", []))
            )

            if resumo.get("sites_nao_localizados"):
                st.markdown("**Sites não localizados**")
                mostrar_grid(
                    pd.DataFrame({
                        "Site SNMPc": resumo.get("sites_nao_localizados", [])
                    }),
                    height=240,
                    key="contratos_sites_nao_localizados"
                )

            if resumo.get("erros"):
                st.markdown("**Erros**")
                mostrar_grid(
                    pd.DataFrame(resumo.get("erros", [])),
                    height=240,
                    key="contratos_erros_indexacao"
                )
        except Exception as erro:
            registrar_log_sistema(
                "contratos_indexacao",
                usuario=usuario_atual["username"],
                status="erro",
                detalhes={
                    "erro": str(erro)
                }
            )
            st.error(f"Falha ao indexar documentos: {erro}")



def mostrar_backup(
    usuario_atual,
    mostrar_grid
):
    st.header("Backup")

    if not has_permission(
        usuario_atual,
        "editar_configuracoes"
    ):
        st.warning(
            "Seu perfil não possui permissão para gerenciar backups."
        )
        return

    config = load_backup_config()
    retention_config = min(
        365,
        max(
            1,
            int(config.get("retention") or 10)
        )
    )

    st.subheader("Backup do sistema")
    st.caption(
        "O backup gera um arquivo ZIP com os dados selecionados do SGS."
    )

    with st.form("form_config_backup"):
        enabled = st.checkbox(
            "Ativar backup automático",
            value=bool(config.get("enabled"))
        )
        frequency = st.selectbox(
            "Frequência",
            list(FREQUENCIAS_BACKUP.keys()),
            index=list(FREQUENCIAS_BACKUP.keys()).index(
                config.get("frequency")
                if config.get("frequency") in FREQUENCIAS_BACKUP
                else "Diário"
            )
        )
        st.text_input(
            "Pasta no container",
            value=str(BACKUP_DIR),
            disabled=True
        )
        st.text_input(
            "Pasta no servidor",
            value="./backups",
            disabled=True
        )
        st.caption(
            "Os backups são salvos em `/app/backups`, mapeado para "
            "`./backups` no servidor."
        )
        retention = st.number_input(
            "Quantidade de backups para manter",
            min_value=1,
            max_value=365,
            value=retention_config,
            step=1
        )

        st.markdown("**Conteúdo do backup**")
        include_imports = st.checkbox(
            "Arquivos importados",
            value=bool(config.get("include_imports"))
        )
        include_config = st.checkbox(
            "Configurações, usuários, índice de documentos e logs",
            value=bool(config.get("include_config"))
        )
        include_cache = st.checkbox(
            "Cache",
            value=bool(config.get("include_cache"))
        )
        include_contracts = st.checkbox(
            "Incluir documentos dos sites",
            value=bool(config.get("include_contracts")),
            help="Inclui a pasta contracts. Pode gerar um arquivo grande."
        )
        include_database = st.checkbox(
            "Banco SQLite",
            value=bool(config.get("include_database"))
        )
        include_system_files = st.checkbox(
            "Arquivos de versão e documentação",
            value=bool(config.get("include_system_files"))
        )

        salvar = st.form_submit_button(
            "Salvar configurações"
        )

    if salvar:
        config = save_backup_config({
            **config,
            "enabled": enabled,
            "frequency": frequency,
            "backup_dir": str(BACKUP_DIR),
            "retention": int(retention),
            "include_imports": include_imports,
            "include_config": include_config,
            "include_cache": include_cache,
            "include_contracts": include_contracts,
            "include_database": include_database,
            "include_system_files": include_system_files
        })
        registrar_log_sistema(
            "backup_configuracao_salva",
            usuario=usuario_atual["username"],
            status="sucesso",
            detalhes={
                "backup_automatico": bool(config.get("enabled")),
                "frequencia": config.get("frequency"),
                "pasta": str(BACKUP_DIR),
                "retencao": config.get("retention")
            }
        )
        st.success("Configurações de backup salvas.")
        st.rerun()

    col1, col2 = st.columns(2)
    col1.metric(
        "Último backup",
        config.get("last_backup_at") or "sem registro"
    )
    col2.metric(
        "Retenção",
        f"{retention_config} arquivos"
    )

    if config.get("last_backup_file"):
        st.caption(
            f"Último arquivo: {config.get('last_backup_file')}"
        )

    st.markdown("**Prévia do conteúdo selecionado**")
    fontes_backup = calcular_fontes_backup(
        config
    )
    mostrar_grid(
        pd.DataFrame(fontes_backup),
        height=220,
        key="backup_previa_conteudo"
    )

    if not config.get("include_contracts"):
        st.warning(
            "Os documentos dos sites não estão incluídos no backup do sistema. "
            "Use o backup de documentos quando precisar copiar a pasta contracts."
        )

    if st.button(
        "Executar backup do sistema agora",
        type="primary",
        key="executar_backup_agora"
    ):
        try:
            resultado = criar_backup(
                config,
                usuario=usuario_atual["username"],
                motivo="manual"
            )
            registrar_log_sistema(
                "backup_manual",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes=resultado
            )
            st.success(
                f"Backup criado: {resultado['file']} ({resultado['size_mb']} MB)."
            )
            st.rerun()
        except Exception as erro:
            registrar_log_sistema(
                "backup_manual",
                usuario=usuario_atual["username"],
                status="erro",
                detalhes={
                    "erro": str(erro)
                }
            )
            st.error(
                f"Falha ao criar backup: {erro}"
            )

    if st.button(
        "Executar backup de documentos agora",
        key="executar_backup_documentos_agora"
    ):
        try:
            config_documentos = {
                **config,
                "include_imports": False,
                "include_config": False,
                "include_cache": False,
                "include_contracts": True,
                "include_database": False,
                "include_system_files": False
            }
            resultado = criar_backup(
                config_documentos,
                usuario=usuario_atual["username"],
                motivo="documentos"
            )
            registrar_log_sistema(
                "backup_documentos",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes=resultado
            )
            st.success(
                f"Backup de documentos criado: {resultado['file']} ({resultado['size_mb']} MB)."
            )
            st.rerun()
        except Exception as erro:
            registrar_log_sistema(
                "backup_documentos",
                usuario=usuario_atual["username"],
                status="erro",
                detalhes={
                    "erro": str(erro)
                }
            )
            st.error(
                f"Falha ao criar backup de documentos: {erro}"
            )

    backups = listar_backups()

    if backups:
        st.subheader("Backups disponíveis")
        resposta_backups = mostrar_grid(
            pd.DataFrame(backups),
            height=260,
            key="backups_disponiveis",
            habilitar_selecao=True,
            mostrar_abrir_site=False
        )
        backup_selecionado = primeira_linha_selecionada(
            resposta_backups
        )
        arquivo_download = str(
            (backup_selecionado or {}).get("Arquivo") or ""
        ).strip()

        if arquivo_download:

            try:
                st.download_button(
                    "Baixar backup selecionado",
                    data=read_backup_file(arquivo_download),
                    file_name=arquivo_download,
                    mime="application/zip",
                    key="backup_download_selecionado"
                )
            except Exception as erro:
                st.warning(
                    f"Não foi possível preparar o download deste backup: {erro}"
                )

        else:
            st.download_button(
                "Baixar backup selecionado",
                data=b"",
                file_name="backup.zip",
                mime="application/zip",
                key="backup_download_selecionado_desabilitado",
                disabled=True
            )
            st.caption(
                "Selecione um backup na tabela para habilitar o download."
            )
    else:
        st.info("Nenhum backup encontrado em /app/backups.")

    st.divider()
    st.subheader("Restaurar backup")
    st.warning(
        "A restauração substitui os dados atuais pelo conteúdo do backup. "
        "Antes de restaurar, o SGS cria automaticamente um backup do estado atual."
    )

    origem_restore = st.radio(
        "Origem do backup",
        [
            "Backup disponível",
            "Enviar arquivo ZIP"
        ],
        horizontal=True,
        key="backup_restore_origem"
    )

    caminho_restore = None
    upload_temporario = None

    if origem_restore == "Backup disponível":
        opcoes_backups = {
            backup["Arquivo"]: backup["Caminho"]
            for backup in backups
        }
        if opcoes_backups:
            arquivo_selecionado = st.selectbox(
                "Backup para restaurar",
                list(opcoes_backups.keys()),
                key="backup_restore_arquivo"
            )
            caminho_restore = opcoes_backups.get(
                arquivo_selecionado
            )
        else:
            st.info("Nenhum backup disponível para restauração.")
    else:
        arquivo_upload = st.file_uploader(
            "Enviar backup ZIP",
            type=["zip"],
            key="backup_restore_upload"
        )

        if arquivo_upload:
            upload_temporario = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".zip"
            )
            upload_temporario.write(
                arquivo_upload.getbuffer()
            )
            upload_temporario.close()
            caminho_restore = upload_temporario.name

    info_restore = None

    if caminho_restore:
        try:
            info_restore = inspecionar_backup(
                caminho_restore
            )
            col_a, col_b, col_c = st.columns(3)
            col_a.metric(
                "Tipo",
                info_restore.get("tipo") or "desconhecido"
            )
            col_b.metric(
                "Versão",
                info_restore.get("versao") or "não informada"
            )
            col_c.metric(
                "Criado em",
                info_restore.get("criado_em") or "não informado"
            )

            if info_restore.get("entradas_invalidas"):
                st.error(
                    "Este backup contém caminhos inseguros e não pode ser restaurado."
                )
                mostrar_grid(
                    pd.DataFrame({
                        "Entrada inválida": info_restore["entradas_invalidas"]
                    }),
                    height=180,
                    key="backup_restore_invalidos"
                )
            elif info_restore.get("fontes"):
                st.markdown("**Fontes encontradas no backup**")
                mostrar_grid(
                    pd.DataFrame(info_restore["fontes"]),
                    height=220,
                    key="backup_restore_fontes"
                )
            else:
                st.error(
                    "Este ZIP não contém fontes restauráveis do SGS."
                )
        except Exception as erro:
            st.error(f"Falha ao ler backup: {erro}")

    if info_restore and info_restore.get("restauravel"):
        fontes_restore = set(
            info_restore.get("fontes_chaves", [])
        )
        restaurar_contracts = st.checkbox(
            "Restaurar documentos dos sites",
            value=False,
            disabled="contracts" not in fontes_restore,
            help="Substitui a pasta contracts somente se marcado."
        )
        incluir_cache_restore = st.checkbox(
            "Restaurar cache",
            value=False,
            disabled="cache" not in fontes_restore,
            help="Normalmente não é necessário. O cache pode estar em uso e é recriado automaticamente."
        )
        confirmacao_restore = st.text_input(
            "Digite RESTAURAR para confirmar",
            value="",
            key="backup_restore_confirmacao"
        )

        if st.button(
            "Restaurar backup selecionado",
            type="primary",
            key="backup_restore_executar",
            disabled=confirmacao_restore.strip().upper() != "RESTAURAR"
        ):
            try:
                resultado_restore = restaurar_backup(
                    caminho_restore,
                    usuario=usuario_atual["username"],
                    restaurar_contracts=restaurar_contracts,
                    incluir_cache=incluir_cache_restore
                )
                registrar_log_sistema(
                    "backup_restaurado",
                    usuario=usuario_atual["username"],
                    status="sucesso",
                    detalhes=resultado_restore
                )
                st.success("Backup restaurado com sucesso.")
                for aviso in resultado_restore.get("avisos", []):
                    st.warning(aviso)
                st.warning(
                    "Reinicie o container para recarregar banco, configurações e sessão: "
                    "sudo docker compose restart snmpc-dashboard"
                )
            except Exception as erro:
                registrar_log_sistema(
                    "backup_restaurado",
                    usuario=usuario_atual["username"],
                    status="erro",
                    detalhes={
                        "erro": str(erro)
                    }
                )
                st.error(f"Falha ao restaurar backup: {erro}")


def registrar_download_exportacao(usuario_atual, item):
    registrar_log_sistema(
        "exportacao_dados",
        usuario=usuario_atual["username"],
        status="sucesso",
        detalhes={
            "item": item
        }
    )


def mostrar_download_arquivo_exportacao(
    usuario_atual,
    titulo,
    descricao,
    path,
    mime,
    key
):
    st.markdown(f"**{titulo}**")
    st.caption(descricao)
    arquivo = arquivo_para_download(path)

    if not arquivo:
        st.warning(f"Arquivo não encontrado: {path}")
        return

    st.download_button(
        f"Baixar {titulo}",
        data=arquivo["data"],
        file_name=arquivo["file_name"],
        mime=mime,
        key=key,
        on_click=registrar_download_exportacao,
        args=(usuario_atual, titulo)
    )


def mostrar_download_excel_exportacao(
    usuario_atual,
    titulo,
    descricao,
    gerador,
    file_name,
    key
):
    st.markdown(f"**{titulo}**")
    st.caption(descricao)

    try:
        conteudo = gerador()
    except Exception as erro:
        st.warning(f"Não foi possível gerar {titulo}: {erro}")
        return

    st.download_button(
        f"Baixar {titulo}",
        data=conteudo,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
        on_click=registrar_download_exportacao,
        args=(usuario_atual, titulo)
    )


def mostrar_exportacoes(usuario_atual):
    st.header("Exportações")

    if not has_permission(
        usuario_atual,
        "exportacoes"
    ):
        st.warning(
            "Seu perfil não possui permissão para exportar dados."
        )
        return

    st.caption(
        "Baixe arquivos e bases operacionais do SGS. Para restauração completa, use a aba Backup."
    )

    st.subheader("Arquivos principais")
    col1, col2, col3 = st.columns(3)

    with col1:
        mostrar_download_arquivo_exportacao(
            usuario_atual,
            "Clientes",
            "Arquivo Excel atual da base de clientes.",
            caminho_exportacao_clientes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "exportar_clientes"
        )

    with col2:
        mostrar_download_arquivo_exportacao(
            usuario_atual,
            "SNMPc",
            "Arquivo TXT atual da topologia SNMPc.",
            caminho_exportacao_snmpc(),
            "text/plain",
            "exportar_snmpc"
        )

    with col3:
        mostrar_download_arquivo_exportacao(
            usuario_atual,
            "Sites",
            "Planilha atual de sites.",
            caminho_exportacao_sites(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "exportar_sites"
        )

    st.divider()
    st.subheader("Bases tratadas")
    col1, col2, col3 = st.columns(3)

    with col1:
        mostrar_download_excel_exportacao(
            usuario_atual,
            "Equipamentos",
            "Base de equipamentos com Modelo, Fabricante e Software.",
            exportar_equipamentos_excel,
            "sgs_equipamentos.xlsx",
            "exportar_equipamentos"
        )

    with col2:
        mostrar_download_excel_exportacao(
            usuario_atual,
            "Produtos",
            "Base de produtos classificada.",
            exportar_produtos_excel,
            "sgs_produtos.xlsx",
            "exportar_produtos"
        )

    with col3:
        mostrar_download_excel_exportacao(
            usuario_atual,
            "Contatos dos Sites",
            "Contatos dos sites para conferência ou carga.",
            exportar_contatos_sites_excel,
            "sgs_contatos_sites.xlsx",
            "exportar_contatos_sites"
        )

    st.divider()
    st.subheader("Mapa")
    formato_mapa = st.radio(
        "Formato do mapa",
        [
            "KMZ",
            "KML"
        ],
        horizontal=True,
        key="exportacoes_mapa_formato"
    )

    conteudo_mapa = exportar_mapa(formato_mapa)

    if not conteudo_mapa:
        st.info(
            "Nenhum mapa compilado encontrado. Acesse Mapa e compile o mapa antes de exportar."
        )
    else:
        extensao = formato_mapa.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        st.download_button(
            f"Baixar Mapa {formato_mapa}",
            data=conteudo_mapa,
            file_name=f"sgs_mapa_{timestamp}.{extensao}",
            mime=(
                "application/vnd.google-earth.kml+xml"
                if formato_mapa == "KML"
                else "application/vnd.google-earth.kmz"
            ),
            key="exportar_mapa",
            on_click=registrar_download_exportacao,
            args=(usuario_atual, f"Mapa {formato_mapa}")
        )

    st.divider()
    st.subheader("Auditoria e documentos")
    col1, col2 = st.columns(2)

    with col1:
        mostrar_download_excel_exportacao(
            usuario_atual,
            "Índice de documentos",
            "Lista os documentos cadastrados, sem incluir os arquivos físicos.",
            exportar_indice_documentos_excel,
            "sgs_indice_documentos.xlsx",
            "exportar_indice_documentos"
        )

    with col2:
        mostrar_download_excel_exportacao(
            usuario_atual,
            "LOG do sistema",
            "Logs de sistema e usuários para auditoria.",
            exportar_logs_excel,
            "sgs_logs.xlsx",
            "exportar_logs"
        )


def mostrar_sistema(
    usuario_atual,
    carregar_dados,
    carregar_dados_de_arquivos,
    mostrar_grid,
    rotulos_modulos,
    sites=None
):
    itens_sistema = [
        (
            "importacao",
            "Importação",
            lambda: mostrar_importacao(
                usuario_atual,
                carregar_dados,
                carregar_dados_de_arquivos
            )
        ),
        (
            "logs",
            "LOG",
            lambda: mostrar_logs(mostrar_grid)
        ),
        (
            "configuracoes",
            "Configurações",
            lambda: mostrar_configuracoes(
                usuario_atual,
                mostrar_grid,
                sites=sites
            )
        ),
        (
            "backup",
            "Backup",
            lambda: mostrar_backup(
                usuario_atual,
                mostrar_grid
            )
        ),
        (
            "exportacoes",
            "Exportações",
            lambda: mostrar_exportacoes(
                usuario_atual
            )
        )
    ]

    if can_manage_users(
        usuario_atual
    ):
        itens_sistema.append(
            (
                "usuarios",
                "Usuários",
                lambda: mostrar_usuarios(
                    usuario_atual,
                    mostrar_grid,
                    rotulos_modulos
                )
            )
        )

    if has_permission(
        usuario_atual,
        "gerenciar_perfis"
    ):
        itens_sistema.append(
            (
                "perfis",
                "Perfis",
                lambda: mostrar_perfis(
                    usuario_atual,
                    mostrar_grid,
                    rotulos_modulos
                )
            )
        )

    itens_permitidos = [
        item
        for item in itens_sistema
        if (
            item[0] == "usuarios"
            and can_manage_users(
                usuario_atual
            )
        )
        or (
            item[0] == "perfis"
            and has_permission(
                usuario_atual,
                "gerenciar_perfis"
            )
        )
        or (
            item[0] == "importacao"
            and has_permission(
                usuario_atual,
                "importar_dados"
            )
        )
        or (
            item[0] == "configuracoes"
            and has_permission(
                usuario_atual,
                "editar_configuracoes"
            )
        )
        or (
            item[0] == "backup"
            and has_permission(
                usuario_atual,
                "editar_configuracoes"
            )
        )
        or has_permission(
            usuario_atual,
            item[0]
        )
    ]

    if not itens_permitidos:
        st.warning(
            "Seu usuário não possui permissões para os itens de sistema."
        )
        return

    funcao = mostrar_subnavegacao(
        itens_permitidos,
        key="sistema_subaba"
    )

    if funcao:
        funcao()
