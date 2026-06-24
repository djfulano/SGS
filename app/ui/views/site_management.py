import pandas as pd
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium

from app.auth import has_permission
from app.logs import registrar_log_sistema
from app.services.map_service import carregar_cache_geocoding
from app.services.map_service import geocodificar_endereco
from app.services.map_service import maptiler_api_key
from app.services.map_service import maptiler_satellite_style_id
from app.services.map_service import salvar_cache_geocoding
from app.services.site_metrics import clientes_indiretos_site
from app.services.site_metrics import clientes_totais_site
from app.services.site_metrics import receita_indireta_site
from app.services.site_metrics import receita_site
from app.services.site_metrics import receita_total_site
from app.services.site_metrics import sites_descendentes
from app.services.contract_service import add_site_contract
from app.services.contract_service import archive_contract_file
from app.services.contract_service import delete_archived_contract_file
from app.services.contract_service import list_site_documents
from app.services.contract_service import read_contract_file
from app.services.contract_service import restore_archived_contract_file
from app.services.site_registry_service import SITE_CODE_COLUMN
from app.services.site_registry_service import load_site_contacts
from app.services.site_registry_service import load_site_registry
from app.services.site_registry_service import normalize_code
from app.services.site_registry_service import normalize_site_contacts
from app.services.site_registry_service import save_site_contacts
from app.services.site_registry_service import upsert_site
from app.ui.navigation import mostrar_subnavegacao


_mostrar_grid = None
_formatar_moeda = None
_usuario_logado = None
_carregar_dados = None


def configurar_gerenciamento_sites(
    mostrar_grid,
    formatar_moeda,
    usuario_logado,
    carregar_dados=None
):
    global _mostrar_grid
    global _formatar_moeda
    global _usuario_logado
    global _carregar_dados

    _mostrar_grid = mostrar_grid
    _formatar_moeda = formatar_moeda
    _usuario_logado = usuario_logado
    _carregar_dados = carregar_dados


def valor_exibicao_site(valor):
    if pd.isna(valor):
        return ""

    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))

    return str(valor)


def chave_campo_site(sufixo, campo):
    return f"gerenciar_site_{sufixo}_{campo}"


def valor_registro_site(registro, coluna, default=""):
    if not registro:
        return default

    valor = registro.get(coluna, default)

    if pd.isna(valor):
        return default

    return valor


def texto_registro_site(registro, coluna, default=""):
    valor = valor_registro_site(
        registro,
        coluna,
        default
    )

    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))

    return str(valor or "")


def numero_registro_site(registro, coluna, default=0.0):
    valor = valor_registro_site(
        registro,
        coluna,
        default
    )

    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return float(default)


def apenas_digitos(valor):
    return "".join(
        caractere
        for caractere in str(valor or "")
        if caractere.isdigit()
    )


def montar_endereco_localizacao(endereco, numero, bairro, cidade, uf, cep):
    endereco = str(endereco or "").strip()
    numero = str(numero or "").strip()

    if numero:
        endereco = f"{endereco}, {numero}" if endereco else numero

    partes = [
        endereco,
        bairro,
        cidade,
        uf,
        cep,
        "Brasil"
    ]

    return ", ".join(
        str(parte).strip()
        for parte in partes
        if str(parte or "").strip()
    )


def coordenada_float_formulario(valor):
    try:
        return float(
            str(valor or "").replace(",", ".")
        )
    except (TypeError, ValueError):
        return 0.0


def coordenada_valida_formulario(latitude, longitude):
    latitude = coordenada_float_formulario(latitude)
    longitude = coordenada_float_formulario(longitude)

    return (
        latitude != 0
        and longitude != 0
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    )


@st.cache_data(ttl=86400, show_spinner=False)
def buscar_endereco_por_cep(cep):
    cep = apenas_digitos(cep)

    if len(cep) != 8:
        return None

    try:
        resposta = requests.get(
            f"https://viacep.com.br/ws/{cep}/json/",
            timeout=8
        )
        resposta.raise_for_status()
        dados = resposta.json()
    except Exception:
        return None

    if dados.get("erro"):
        return None

    return {
        "endereco": dados.get("logradouro", ""),
        "bairro": dados.get("bairro", ""),
        "cidade": dados.get("localidade", ""),
        "uf": dados.get("uf", ""),
        "cep": cep
    }


def aplicar_endereco_cep(sufixo, cep):
    endereco = buscar_endereco_por_cep(cep)

    if not endereco:
        return

    marcador_key = chave_campo_site(
        sufixo,
        "cep_aplicado"
    )

    if st.session_state.get(marcador_key) == endereco["cep"]:
        return

    mapeamento = {
        "endereco": endereco["endereco"],
        "bairro": endereco["bairro"],
        "cidade": endereco["cidade"],
        "uf": endereco["uf"],
        "cep_aplicado": endereco["cep"]
    }

    for campo, valor in mapeamento.items():
        if not valor:
            continue

        st.session_state[
            chave_campo_site(
                sufixo,
                campo
            )
        ] = valor


def carregar_coordenadas_endereco_site(sufixo, endereco_completo):
    if not endereco_completo:
        st.warning("Preencha o endereço antes de carregar no mapa.")
        return

    cache = carregar_cache_geocoding()

    try:
        ponto = geocodificar_endereco(
            endereco_completo,
            cache
        )
        salvar_cache_geocoding(cache)
    except requests.RequestException as erro:
        st.error(f"Falha ao buscar coordenadas: {erro}")
        return

    if not ponto:
        st.warning("Não foi possível localizar este endereço no mapa.")
        return

    st.session_state[
        chave_campo_site(
            sufixo,
            "latitude"
        )
    ] = str(ponto["lat"])
    st.session_state[
        chave_campo_site(
            sufixo,
            "longitude"
        )
    ] = str(ponto["lon"])
    st.session_state[
        chave_campo_site(
            sufixo,
            "endereco_geocodificado"
        )
    ] = endereco_completo
    st.success("Coordenadas carregadas a partir do endereço.")


def mostrar_mapa_interativo_coordenadas(
    sufixo,
    latitude,
    longitude
):
    lat_key = chave_campo_site(
        sufixo,
        "latitude"
    )
    lon_key = chave_campo_site(
        sufixo,
        "longitude"
    )
    pendente_key = chave_campo_site(
        sufixo,
        "coordenada_pendente_mapa"
    )
    clique_ignorado_key = chave_campo_site(
        sufixo,
        "coordenada_clique_ignorado"
    )

    if not coordenada_valida_formulario(
        latitude,
        longitude
    ):
        st.caption(
            "Carregue o endereço no mapa ou informe Latitude e Longitude para ajustar o ponto."
        )
        return

    st.caption(
        "Clique no mapa para ajustar a localização. A alteração será aplicada somente após confirmação."
    )

    token_maptiler = maptiler_api_key()
    mapa = folium.Map(
        location=[
            latitude,
            longitude
        ],
        zoom_start=16,
        tiles=None
    )

    if token_maptiler:
        estilo = maptiler_satellite_style_id()
        folium.TileLayer(
            tiles=(
                "https://api.maptiler.com/maps/"
                f"{estilo}/256/{{z}}/{{x}}/{{y}}.jpg?key={token_maptiler}"
            ),
            attr="MapTiler",
            name="Satélite",
            overlay=False,
            control=False
        ).add_to(mapa)
    else:
        folium.TileLayer(
            tiles="OpenStreetMap",
            name="Ruas",
            overlay=False,
            control=False
        ).add_to(mapa)
        st.caption(
            "Satélite indisponível: configure a chave MapTiler em Sistema > Configurações."
        )

    folium.Marker(
        [
            latitude,
            longitude
        ],
        tooltip="Localização atual do site",
        icon=folium.Icon(
            color="blue",
            icon="tower-broadcast",
            prefix="fa"
        )
    ).add_to(mapa)

    resultado = st_folium(
        mapa,
        key=chave_campo_site(
            sufixo,
            "mapa_interativo"
        ),
        height=380,
        use_container_width=True
    )
    clique = (
        resultado or {}
    ).get("last_clicked")

    if not clique:
        return

    nova_latitude = clique.get("lat")
    nova_longitude = clique.get("lng")

    if not coordenada_valida_formulario(
        nova_latitude,
        nova_longitude
    ):
        return

    assinatura_clique = (
        f"{float(nova_latitude):.6f},"
        f"{float(nova_longitude):.6f}"
    )

    if st.session_state.get(clique_ignorado_key) == assinatura_clique:
        return

    if (
        round(float(nova_latitude), 6) == round(float(latitude), 6)
        and round(float(nova_longitude), 6) == round(float(longitude), 6)
    ):
        return

    st.session_state[pendente_key] = {
        "latitude": float(nova_latitude),
        "longitude": float(nova_longitude),
        "assinatura": assinatura_clique
    }

    @st.dialog("Confirmar alteração de coordenadas")
    def confirmar_coordenadas_mapa():
        coordenada_pendente = st.session_state.get(
            pendente_key
        )

        if not coordenada_pendente:
            st.info("Nenhuma coordenada pendente para confirmar.")
            return

        st.write(
            "Confirme se deseja alterar as coordenadas do site para o ponto selecionado no mapa."
        )
        st.caption(
            f"Atual: {latitude:.6f}, {longitude:.6f}"
        )
        st.caption(
            "Nova: "
            f"{coordenada_pendente['latitude']:.6f}, "
            f"{coordenada_pendente['longitude']:.6f}"
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "Confirmar alteração",
                type="primary",
                key=chave_campo_site(
                    sufixo,
                    "confirmar_coordenada_mapa"
                )
            ):
                st.session_state[lat_key] = (
                    f"{coordenada_pendente['latitude']:.6f}"
                )
                st.session_state[lon_key] = (
                    f"{coordenada_pendente['longitude']:.6f}"
                )
                st.session_state.pop(
                    pendente_key,
                    None
                )
                st.session_state.pop(
                    clique_ignorado_key,
                    None
                )
                st.rerun()

        with col2:
            if st.button(
                "Cancelar",
                key=chave_campo_site(
                    sufixo,
                    "cancelar_coordenada_mapa"
                )
            ):
                st.session_state.pop(
                    pendente_key,
                    None
                )
                st.session_state[clique_ignorado_key] = coordenada_pendente[
                    "assinatura"
                ]
                st.rerun()

    confirmar_coordenadas_mapa()


def opcoes_cadastradas_site(df_cadastro, coluna, valor_atual="", extras=None):
    opcoes = [""]

    if extras:
        opcoes.extend(extras)

    if coluna in df_cadastro.columns:
        opcoes.extend(
            str(valor).strip()
            for valor in df_cadastro[coluna].dropna().unique()
            if str(valor).strip()
        )

    if valor_atual and str(valor_atual).strip():
        opcoes.append(str(valor_atual).strip())

    opcoes_unicas = {
        str(valor).strip()
        for valor in opcoes
    }

    return [""] + sorted(
        {
            valor
            for valor in opcoes_unicas
            if valor
        },
        key=lambda valor: valor.lower()
    )


def selectbox_cadastro(rotulo, opcoes, valor_atual, key=None):
    valor_atual = str(valor_atual or "").strip()
    opcoes = list(opcoes)

    if valor_atual and valor_atual not in opcoes:
        opcoes.append(valor_atual)

    if not opcoes:
        opcoes = [valor_atual] if valor_atual else [""]

    index = opcoes.index(valor_atual) if valor_atual in opcoes else 0

    return st.selectbox(
        rotulo,
        opcoes,
        index=index,
        key=key
    )


def montar_registro_site_formulario(registro, df_cadastro, sufixo):
    contrato_atual = texto_registro_site(registro, "CONTRATO")
    categoria_atual = texto_registro_site(registro, "CATEGORIA")
    perfil_atual = texto_registro_site(registro, "PERFIL")
    restricao_atual = texto_registro_site(registro, "RESTRIÇÃO")
    status_atual = texto_registro_site(registro, "Status")
    relacionamento_atual = texto_registro_site(registro, "Relacionamento")
    favorecido_atual = texto_registro_site(registro, "Favorecido")

    opcoes_contrato = opcoes_cadastradas_site(df_cadastro, "CONTRATO", contrato_atual)
    opcoes_categoria = opcoes_cadastradas_site(df_cadastro, "CATEGORIA", categoria_atual)
    opcoes_perfil = opcoes_cadastradas_site(df_cadastro, "PERFIL", perfil_atual)
    opcoes_restricao = opcoes_cadastradas_site(
        df_cadastro,
        "RESTRIÇÃO",
        restricao_atual,
        extras=[
            "NÃO",
            "SIM"
        ]
    )
    opcoes_status = opcoes_cadastradas_site(
        df_cadastro,
        "Status",
        status_atual,
        extras=[
            "Ativo",
            "Cancelado"
        ]
    )
    opcoes_relacionamento = opcoes_cadastradas_site(
        df_cadastro,
        "Relacionamento",
        relacionamento_atual,
        extras=[
            "Sem histórico"
        ]
    )
    opcoes_tipo = opcoes_cadastradas_site(
        df_cadastro,
        "TIPO",
        texto_registro_site(registro, "TIPO"),
        extras=[
            "Cliente",
            "POP",
            "BH",
            "REP",
            "DC",
            "SITE"
        ]
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        codigo = st.text_input(
            "Código Aquiles",
            value=texto_registro_site(registro, "CÓDIGO AQUILES"),
            key=chave_campo_site(sufixo, "codigo")
        )
        microsiga = st.text_input(
            "Código Microsiga",
            value=texto_registro_site(registro, "CÓDIGO MICROSIGA"),
            key=chave_campo_site(sufixo, "microsiga")
        )

    with col2:
        snmpc = st.text_input(
            "SNMPc",
            value=texto_registro_site(registro, "SMNPC"),
            key=chave_campo_site(sufixo, "snmpc")
        )
        codigo_condominio = st.text_input(
            "Código Condomínio",
            value=texto_registro_site(registro, "CÓDIGO CONDOMINIO"),
            key=chave_campo_site(sufixo, "codigo_condominio")
        )

    col1, col2, col3, col4 = st.columns(4)

    tipo_atual = texto_registro_site(
        registro,
        "TIPO"
    )

    with col1:
        tipo = selectbox_cadastro(
            "Tipo",
            opcoes_tipo,
            tipo_atual,
            key=chave_campo_site(sufixo, "tipo")
        )

    with col2:
        nome = st.text_input(
            "Nome",
            value=texto_registro_site(registro, "NOME"),
            key=chave_campo_site(sufixo, "nome")
        )

    with col3:
        abreviacao = st.text_input(
            "Abreviação",
            value=texto_registro_site(registro, "ABREVIAÇÃO"),
            key=chave_campo_site(sufixo, "abreviacao")
        )

    with col4:
        status = selectbox_cadastro(
            "Status",
            opcoes_status,
            status_atual,
            key=chave_campo_site(sufixo, "status")
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        contrato = selectbox_cadastro(
            "Contrato",
            opcoes_contrato,
            contrato_atual,
            key=chave_campo_site(sufixo, "contrato")
        )

    with col2:
        relacionamento = selectbox_cadastro(
            "Relacionamento",
            opcoes_relacionamento,
            relacionamento_atual,
            key=chave_campo_site(sufixo, "relacionamento")
        )

    with col3:
        favorecido = st.text_input(
            "Favorecido",
            value=favorecido_atual,
            key=chave_campo_site(sufixo, "favorecido")
        )

    with col4:
        custo = st.text_input(
            "Custo",
            value=texto_registro_site(registro, "CUSTO"),
            key=chave_campo_site(sufixo, "custo")
        )

    st.markdown("**Contrato e perfil**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        qtdo = st.number_input(
            "Quantidade",
            min_value=0.0,
            value=numero_registro_site(registro, "QTDO"),
            step=1.0,
            key=chave_campo_site(sufixo, "qtdo")
        )

    with col2:
        categoria = selectbox_cadastro(
            "Categoria",
            opcoes_categoria,
            categoria_atual,
            key=chave_campo_site(sufixo, "categoria")
        )

    with col3:
        perfil = selectbox_cadastro(
            "Perfil",
            opcoes_perfil,
            perfil_atual,
            key=chave_campo_site(sufixo, "perfil")
        )

    with col4:
        ativacao = st.text_input(
            "Ativação",
            value=texto_registro_site(registro, "ATIVAÇÃO"),
            key=chave_campo_site(sufixo, "ativacao")
        )

    st.markdown("**Localização**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cep = st.text_input(
            "CEP",
            value=texto_registro_site(registro, "CEP"),
            key=chave_campo_site(sufixo, "cep")
        )
        aplicar_endereco_cep(
            sufixo,
            cep
        )

    with col2:
        endereco = st.text_input(
            "Endereço",
            value=texto_registro_site(registro, "ENDEREÇO"),
            key=chave_campo_site(sufixo, "endereco")
        )

    with col3:
        numero = st.text_input(
            "Número",
            value=texto_registro_site(registro, "NUMERO"),
            key=chave_campo_site(sufixo, "numero")
        )

    with col4:
        bairro = st.text_input(
            "Bairro",
            value=texto_registro_site(registro, "BAIRRO"),
            key=chave_campo_site(sufixo, "bairro")
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cidade = st.text_input(
            "Cidade",
            value=texto_registro_site(registro, "CIDADE"),
            key=chave_campo_site(sufixo, "cidade")
        )

    with col2:
        uf = st.text_input(
            "UF",
            value=texto_registro_site(registro, "UF", "SP"),
            key=chave_campo_site(sufixo, "uf")
        )

    endereco_completo_mapa = montar_endereco_localizacao(
        endereco,
        numero,
        bairro,
        cidade,
        uf,
        cep
    )

    col1, col2 = st.columns([1, 3])

    with col1:
        carregar_mapa = st.button(
            "Carregar endereço no mapa",
            key=chave_campo_site(
                sufixo,
                "carregar_endereco_mapa"
            )
        )

    with col2:
        st.caption(
            endereco_completo_mapa
            or "Preencha o endereço para buscar as coordenadas."
        )

    if carregar_mapa:
        carregar_coordenadas_endereco_site(
            sufixo,
            endereco_completo_mapa
        )

    latitude_key = chave_campo_site(
        sufixo,
        "latitude"
    )
    longitude_key = chave_campo_site(
        sufixo,
        "longitude"
    )

    if latitude_key not in st.session_state:
        st.session_state[latitude_key] = texto_registro_site(
            registro,
            "LATITUDE"
        )

    if longitude_key not in st.session_state:
        st.session_state[longitude_key] = texto_registro_site(
            registro,
            "LONGITUDE"
        )

    latitude_mapa = coordenada_float_formulario(
        st.session_state.get(
            latitude_key,
            ""
        )
    )
    longitude_mapa = coordenada_float_formulario(
        st.session_state.get(
            longitude_key,
            ""
        )
    )

    mostrar_mapa_interativo_coordenadas(
        sufixo,
        latitude_mapa,
        longitude_mapa
    )

    col1, col2 = st.columns(2)

    with col1:
        latitude = st.text_input(
            "Latitude",
            key=latitude_key
        )

    with col2:
        longitude = st.text_input(
            "Longitude",
            key=longitude_key
        )

    st.markdown("**Operacional**")
    col1, col2, col3 = st.columns(3)

    with col1:
        altura = st.number_input(
            "Altura",
            min_value=0.0,
            value=numero_registro_site(registro, "ALTURA"),
            step=1.0,
            key=chave_campo_site(sufixo, "altura")
        )

    with col2:
        restricao = selectbox_cadastro(
            "Restrição",
            opcoes_restricao,
            restricao_atual,
            key=chave_campo_site(sufixo, "restricao")
        )

    with col3:
        detalhe = st.text_input(
            "Detalhe",
            value=texto_registro_site(registro, "Detalhe"),
            key=chave_campo_site(sufixo, "detalhe")
        )

    observacao = st.text_area(
        "Observação",
        value=texto_registro_site(registro, "OBSERVAÇÃO:"),
        key=chave_campo_site(sufixo, "observacao")
    )

    return {
        "CÓDIGO AQUILES": normalize_code(codigo),
        "CÓDIGO MICROSIGA": normalize_code(microsiga),
        "CÓDIGO CONDOMINIO": normalize_code(codigo_condominio),
        "ABREVIAÇÃO": abreviacao.strip(),
        "SMNPC": snmpc.strip(),
        "TIPO": tipo,
        "NOME": nome.strip(),
        "Relacionamento": relacionamento.strip(),
        "Favorecido": favorecido.strip(),
        "CONTRATO": contrato.strip(),
        "QTDO": qtdo,
        "CATEGORIA": categoria.strip(),
        "PERFIL": perfil.strip(),
        "CUSTO": custo.strip(),
        "ENDEREÇO": endereco.strip(),
        "NUMERO": numero.strip(),
        "BAIRRO": bairro.strip(),
        "CIDADE": cidade.strip(),
        "UF": uf.strip().upper(),
        "CEP": normalize_code(cep),
        "ATIVAÇÃO": ativacao.strip(),
        "LATITUDE": latitude.strip(),
        "LONGITUDE": longitude.strip(),
        "ALTURA": altura,
        "RESTRIÇÃO": restricao.strip(),
        "Status": status,
        "Detalhe": detalhe.strip(),
        "OBSERVAÇÃO:": observacao.strip()
    }


def mostrar_item_contratual(rotulo, valor):
    texto = valor_exibicao_site(valor)

    st.caption(rotulo)
    st.markdown(
        f"**{texto or '-'}**"
    )


def valor_custo_site(valor):
    try:
        return _formatar_moeda(float(valor or 0))
    except (TypeError, ValueError):
        return valor_exibicao_site(valor) or "-"


def dados_cliente_financeiro(cliente, site_cliente, vinculo):
    return {
        "Vínculo": vinculo,
        "Site": site_cliente.nome,
        "Setorial": getattr(cliente, "setorial", None) or "Direto",
        "Cliente": cliente.nome,
        "Assinatura": cliente.num_assinatura,
        "Produto": getattr(cliente, "produto", ""),
        "Mensalidade": cliente.receita,
        "Predio": getattr(cliente, "predio_estrutura", None) or "",
        "CEP": getattr(cliente, "cep", ""),
        "Endereco": getattr(cliente, "endereco_completo", ""),
        "Bairro": getattr(cliente, "bairro", ""),
        "Cidade": getattr(cliente, "cidade", "")
    }


def clientes_diretos_financeiro(site_modelo):
    return [
        dados_cliente_financeiro(
            cliente,
            site_modelo,
            "Direto"
        )
        for cliente in site_modelo.clientes
    ]


def clientes_indiretos_financeiro(site_modelo):
    dados = []

    for site_filho in sites_descendentes(site_modelo)[1:]:
        for cliente in site_filho.clientes:
            dados.append(
                dados_cliente_financeiro(
                    cliente,
                    site_filho,
                    "Indireto"
                )
            )

    return dados


def sites_filhos_financeiro(site_modelo):
    return [
        {
            "Site": site_filho.nome,
            "Tipo": site_filho.tipo,
            "Status Cadastro": getattr(site_filho, "status_cadastro", ""),
            "Codigo": getattr(site_filho, "codigo_topos", ""),
            "Microsiga": getattr(site_filho, "microsiga", ""),
            "Nome Cadastro": getattr(site_filho, "nome_cadastro", ""),
            "Clientes Diretos": len(site_filho.clientes),
            "Clientes Indiretos": clientes_indiretos_site(site_filho),
            "Clientes Total": clientes_totais_site(site_filho),
            "Receita Direta": receita_site(site_filho),
            "Receita Indireta": receita_indireta_site(site_filho),
            "Receita Total": receita_total_site(site_filho),
            "Custo": getattr(site_filho, "custo", 0)
        }
        for site_filho in site_modelo.filhos
    ]


def localizar_site_modelo(sites, site):
    candidatos = [
        site.get("Site SNMPc"),
        site.get("SNMPc")
    ]

    for candidato in candidatos:
        nome = valor_exibicao_site(candidato)

        if nome and nome in sites:
            return sites[nome]

    codigo = valor_exibicao_site(
        site.get("Codigo")
    )

    if codigo:
        for site_modelo in sites.values():
            if valor_exibicao_site(
                getattr(site_modelo, "codigo_topos", "")
            ) == codigo:
                return site_modelo

    return None


def mostrar_contratos_site(site):
    st.markdown("**Documentos do site**")

    codigo = valor_exibicao_site(
        site.get("Codigo")
    )
    nome_site = valor_exibicao_site(
        site.get("Site SNMPc")
    ) or valor_exibicao_site(
        site.get("Nome Cadastro")
    )
    usuario_atual = _usuario_logado()
    pode_editar = has_permission(
        usuario_atual,
        "editar_contratos_sites"
    )

    if not codigo:
        st.info("Informe o Código Aquiles do site para vincular documentos.")
        return

    documentos = list_site_documents(
        codigo
    )
    arquivados = list_site_documents(
        codigo,
        archived=True
    )

    if pode_editar:
        with st.expander("Adicionar documento", expanded=False):
            observacao = st.text_input(
                "Observação",
                key=f"documento_observacao_{codigo}"
            )

            arquivos = st.file_uploader(
                "Arquivos",
                type=[
                    "pdf",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "png",
                    "jpg",
                    "jpeg",
                    "msg"
                ],
                accept_multiple_files=True,
                key=f"contrato_upload_{codigo}"
            )

            if st.button(
                "Salvar documentos",
                type="primary",
                key=f"contrato_salvar_{codigo}"
            ):
                if not arquivos:
                    st.error("Selecione um ou mais arquivos para salvar.")
                else:
                    salvos = []
                    erros = []

                    for arquivo in arquivos:
                        try:
                            registro = add_site_contract(
                                codigo,
                                nome_site,
                                arquivo.name,
                                bytes(arquivo.getbuffer()),
                                content_type=getattr(arquivo, "type", ""),
                                uploaded_by=usuario_atual["username"],
                                notes=observacao
                            )
                            salvos.append(
                                registro.get("original_filename")
                            )
                        except Exception as erro:
                            erros.append({
                                "arquivo": getattr(arquivo, "name", ""),
                                "erro": str(erro)
                            })

                    if salvos:
                        registrar_log_sistema(
                            "site_documento_upload",
                            usuario=usuario_atual["username"],
                            status="sucesso" if not erros else "parcial",
                            detalhes={
                                "codigo": codigo,
                                "site": nome_site,
                                "quantidade": len(salvos),
                                "arquivos": salvos,
                                "erros": erros
                            }
                        )

                    for erro in erros:
                        registrar_log_sistema(
                            "site_documento_upload",
                            usuario=usuario_atual["username"],
                            status="erro",
                            detalhes={
                                "codigo": codigo,
                                **erro
                            }
                        )

                    if erros and salvos:
                        st.warning(
                            f"{len(salvos)} documento(s) salvo(s), "
                            f"mas {len(erros)} arquivo(s) falharam."
                        )
                    elif erros:
                        st.error("Nenhum documento foi salvo.")
                    else:
                        st.success(
                            f"{len(salvos)} documento(s) salvo(s)."
                        )

                    if erros:
                        st.dataframe(
                            pd.DataFrame(erros),
                            use_container_width=True,
                            hide_index=True
                        )

                    if salvos:
                        st.rerun()

    def mostrar_lista_documentos(lista, sufixo, permitir_arquivar=False):
        if not lista:
            st.caption("Nenhum documento encontrado.")
            return

        dados = []

        for documento in sorted(
            lista,
            key=lambda item: item.get("uploaded_at") or "",
            reverse=True
        ):
            dados.append({
                "Arquivo": documento.get("original_filename"),
                "Tamanho KB": round((documento.get("size") or 0) / 1024, 1),
                "Enviado por": documento.get("uploaded_by"),
                "Enviado em": documento.get("uploaded_at"),
                "Arquivado por": documento.get("archived_by"),
                "Arquivado em": documento.get("archived_at"),
                "Observacao": documento.get("notes")
            })

        altura_grid = min(
            260,
            max(
                90,
                42 + len(dados) * 36
            )
        )

        _mostrar_grid(
            pd.DataFrame(dados),
            height=altura_grid,
            key=f"documentos_site_{codigo}_{sufixo}"
        )

        st.markdown("**Downloads**")

        for documento in sorted(
            lista,
            key=lambda item: item.get("uploaded_at") or "",
            reverse=True
        ):
            conteudo = read_contract_file(
                documento
            )

            if conteudo is None:
                st.warning(
                    f"Arquivo ausente no disco: {documento.get('original_filename')}"
                )
                continue

            col_download, col_arquivar = st.columns([3, 1])

            with col_download:
                st.download_button(
                    f"Baixar {documento.get('original_filename')}",
                    data=conteudo,
                    file_name=documento.get("original_filename") or "documento",
                    mime=documento.get("content_type") or "application/octet-stream",
                    key=f"documento_download_{documento.get('id')}_{sufixo}"
                )

            if permitir_arquivar and pode_editar:
                with col_arquivar:
                    confirmar_arquivamento = st.checkbox(
                        "Confirmar arquivamento",
                        help=(
                            "Arquivar move o documento para a seção Arquivados. "
                            "O arquivo não será excluído."
                        ),
                        key=f"documento_confirmar_arquivar_{documento.get('id')}"
                    )

                    if st.button(
                        "Arquivar",
                        key=f"documento_arquivar_{documento.get('id')}",
                        disabled=not confirmar_arquivamento
                    ):
                        try:
                            archive_contract_file(
                                documento.get("id"),
                                archived_by=usuario_atual["username"]
                            )
                            registrar_log_sistema(
                                "site_documento_arquivado",
                                usuario=usuario_atual["username"],
                                status="sucesso",
                                detalhes={
                                    "codigo": codigo,
                                    "arquivo": documento.get("original_filename")
                                }
                            )
                            st.success("Documento arquivado.")
                            st.rerun()
                        except Exception as erro:
                            registrar_log_sistema(
                                "site_documento_arquivado",
                                usuario=usuario_atual["username"],
                                status="erro",
                                detalhes={
                                    "codigo": codigo,
                                    "erro": str(erro)
                                }
                            )
                            st.error(f"Falha ao arquivar documento: {erro}")

    def mostrar_documentos_arquivados(lista):
        if not lista:
            st.caption("Nenhum documento arquivado.")
            return

        lista_ordenada = sorted(
            lista,
            key=lambda item: item.get("archived_at")
            or item.get("uploaded_at")
            or "",
            reverse=True
        )
        dados = [
            {
                "Arquivo": documento.get("original_filename"),
                "Tamanho KB": round((documento.get("size") or 0) / 1024, 1),
                "Enviado por": documento.get("uploaded_by"),
                "Enviado em": documento.get("uploaded_at"),
                "Arquivado por": documento.get("archived_by"),
                "Arquivado em": documento.get("archived_at"),
                "Observação": documento.get("notes")
            }
            for documento in lista_ordenada
        ]
        altura = min(
            240,
            max(
                110,
                38 + len(dados) * 36
            )
        )

        st.dataframe(
            pd.DataFrame(dados),
            use_container_width=True,
            hide_index=True,
            height=altura
        )

        st.markdown("**Downloads e ações**")

        for documento in lista_ordenada:
            documento_id = documento.get("id")
            nome_arquivo = documento.get("original_filename") or "documento"
            conteudo = read_contract_file(
                documento
            )

            with st.container(border=True):
                st.markdown(f"**{nome_arquivo}**")

                if conteudo is None:
                    st.warning(
                        f"Arquivo ausente no disco: {nome_arquivo}"
                    )
                else:
                    st.download_button(
                        f"Baixar {nome_arquivo}",
                        data=conteudo,
                        file_name=nome_arquivo,
                        mime=documento.get("content_type") or "application/octet-stream",
                        key=f"documento_download_{documento_id}_arquivado"
                    )

                if not pode_editar:
                    continue

                col_retornar, col_excluir = st.columns(2)

                with col_retornar:
                    confirmar_retorno = st.checkbox(
                        "Confirmar retorno",
                        key=f"documento_confirmar_retorno_{documento_id}"
                    )

                    if st.button(
                        "Retornar",
                        key=f"documento_retornar_{documento_id}",
                        disabled=not confirmar_retorno
                    ):
                        try:
                            restore_archived_contract_file(
                                documento_id,
                                restored_by=usuario_atual["username"]
                            )
                            registrar_log_sistema(
                                "site_documento_restaurado",
                                usuario=usuario_atual["username"],
                                status="sucesso",
                                detalhes={
                                    "codigo": codigo,
                                    "arquivo": nome_arquivo
                                }
                            )
                            st.success("Documento retornado.")
                            st.rerun()
                        except Exception as erro:
                            registrar_log_sistema(
                                "site_documento_restaurado",
                                usuario=usuario_atual["username"],
                                status="erro",
                                detalhes={
                                    "codigo": codigo,
                                    "arquivo": nome_arquivo,
                                    "erro": str(erro)
                                }
                            )
                            st.error(f"Falha ao retornar documento: {erro}")

                with col_excluir:
                    confirmar_exclusao = st.text_input(
                        "Digite EXCLUIR para remover",
                        key=f"documento_confirmar_excluir_{documento_id}"
                    )

                    if st.button(
                        "Excluir definitivamente",
                        key=f"documento_excluir_{documento_id}",
                        disabled=confirmar_exclusao.strip().upper() != "EXCLUIR"
                    ):
                        try:
                            delete_archived_contract_file(
                                documento_id
                            )
                            registrar_log_sistema(
                                "site_documento_excluido_definitivo",
                                usuario=usuario_atual["username"],
                                status="sucesso",
                                detalhes={
                                    "codigo": codigo,
                                    "arquivo": nome_arquivo
                                }
                            )
                            st.success("Documento excluído definitivamente.")
                            st.rerun()
                        except Exception as erro:
                            registrar_log_sistema(
                                "site_documento_excluido_definitivo",
                                usuario=usuario_atual["username"],
                                status="erro",
                                detalhes={
                                    "codigo": codigo,
                                    "arquivo": nome_arquivo,
                                    "erro": str(erro)
                                }
                            )
                            st.error(f"Falha ao excluir documento: {erro}")

    mostrar_lista_documentos(
        documentos,
        "ativos",
        permitir_arquivar=True
    )

    with st.expander("Arquivados", expanded=False):
        mostrar_documentos_arquivados(
            arquivados
        )


def mostrar_financeiro_site_selecionado(site, site_modelo=None):
    st.subheader("Detalhes financeiros")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Receita direta",
        _formatar_moeda(float(site.get("Receita Direta") or 0))
    )
    col2.metric(
        "Receita com filhos",
        _formatar_moeda(float(site.get("Receita Com Filhos") or 0))
    )
    col3.metric(
        "Custo",
        valor_custo_site(site.get("Custo"))
    )
    col4.metric(
        "Resultado",
        _formatar_moeda(float(site.get("Resultado") or 0))
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Clientes diretos",
        int(site.get("Clientes Diretos") or 0)
    )
    col2.metric(
        "Clientes indiretos",
        int(site.get("Clientes Indiretos") or 0)
    )
    col3.metric(
        "Clientes total",
        int(site.get("Clientes Total") or 0)
    )
    col4.metric(
        "Margem",
        f"{float(site.get('Margem %') or 0):.1%}"
    )

    st.markdown("**Detalhamento financeiro**")

    if site_modelo is None:
        st.info("Não foi possível localizar o site na topologia carregada para listar clientes e filhos.")
        return

    opcoes_tabelas = [
        "Clientes diretos",
        "Clientes indiretos",
        "Clientes total",
        "Sites filhos"
    ]
    tabelas = st.multiselect(
        "Tabelas exibidas",
        opcoes_tabelas,
        default=opcoes_tabelas,
        key=f"gerenciamento_financeiro_tabelas_{valor_exibicao_site(site.get('Codigo')) or valor_exibicao_site(site.get('Site SNMPc'))}"
    )

    if "Clientes diretos" in tabelas:
        st.markdown("**Clientes diretos**")
        df_diretos = pd.DataFrame(
            clientes_diretos_financeiro(site_modelo)
        )

        if df_diretos.empty:
            st.info("Este site não possui clientes diretos.")
        else:
            _mostrar_grid(
                df_diretos.sort_values(
                    by=[
                        "Setorial",
                        "Cliente"
                    ]
                ),
                height=320,
                key="gerenciamento_financeiro_clientes_diretos"
            )

    if "Clientes indiretos" in tabelas:
        st.markdown("**Clientes indiretos**")
        df_indiretos = pd.DataFrame(
            clientes_indiretos_financeiro(site_modelo)
        )

        if df_indiretos.empty:
            st.info("Este site não possui clientes indiretos.")
        else:
            _mostrar_grid(
                df_indiretos.sort_values(
                    by=[
                        "Site",
                        "Setorial",
                        "Cliente"
                    ]
                ),
                height=360,
                key="gerenciamento_financeiro_clientes_indiretos"
            )

    if "Clientes total" in tabelas:
        st.markdown("**Clientes total**")
        df_total = pd.DataFrame(
            clientes_diretos_financeiro(site_modelo)
            + clientes_indiretos_financeiro(site_modelo)
        )

        if df_total.empty:
            st.info("Este site não possui clientes diretos ou indiretos.")
        else:
            _mostrar_grid(
                df_total.sort_values(
                    by=[
                        "Vínculo",
                        "Site",
                        "Setorial",
                        "Cliente"
                    ]
                ),
                height=420,
                key="gerenciamento_financeiro_clientes_total"
            )

    if "Sites filhos" in tabelas:
        st.markdown("**Sites filhos**")
        df_filhos = pd.DataFrame(
            sites_filhos_financeiro(site_modelo)
        )

        if df_filhos.empty:
            st.info("Este site não possui sites filhos.")
        else:
            _mostrar_grid(
                df_filhos.sort_values(
                    by="Receita Total",
                    ascending=False
                ),
                height=320,
                key="gerenciamento_financeiro_sites_filhos"
            )


def mostrar_contratual_site_selecionado(site):
    st.subheader("Detalhes contratuais")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Tipo", valor_exibicao_site(site.get("Tipo")) or "-")

    with col2:
        st.metric("Status", valor_exibicao_site(site.get("Status Cadastro")) or "-")

    with col3:
        st.metric("No SNMPc", valor_exibicao_site(site.get("No SNMPc")) or "-")

    with col4:
        st.metric("Custo", valor_custo_site(site.get("Custo")))

    st.markdown("**Identificação**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        mostrar_item_contratual("Código Aquiles", site.get("Codigo"))
        mostrar_item_contratual("Código Microsiga", site.get("Microsiga"))
        mostrar_item_contratual("Código Condomínio", site.get("Codigo Condominio"))

    with col2:
        mostrar_item_contratual("SNMPc", site.get("SNMPc"))
        mostrar_item_contratual("Site SNMPc", site.get("Site SNMPc"))
        mostrar_item_contratual("Abreviação", site.get("Abreviacao"))

    with col3:
        mostrar_item_contratual("Nome cadastro", site.get("Nome Cadastro"))
        mostrar_item_contratual("Ativação", site.get("Ativacao"))
        mostrar_item_contratual("Relacionamento", site.get("Relacionamento"))

    with col4:
        mostrar_item_contratual("Favorecido", site.get("Favorecido"))

    st.markdown("**Contrato**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        mostrar_item_contratual("Contrato", site.get("Contrato"))

    with col2:
        mostrar_item_contratual("Quantidade", site.get("Qtdo"))

    with col3:
        mostrar_item_contratual("Categoria", site.get("Categoria"))

    with col4:
        mostrar_item_contratual("Perfil", site.get("Perfil"))

    st.markdown("**Localização**")
    col1, col2 = st.columns(2)

    with col1:
        mostrar_item_contratual("Endereço", site.get("Endereco"))
        mostrar_item_contratual("Número", site.get("Numero"))
        mostrar_item_contratual("Bairro", site.get("Bairro"))

    with col2:
        mostrar_item_contratual("Cidade", site.get("Cidade"))
        mostrar_item_contratual("UF", site.get("UF"))
        mostrar_item_contratual("CEP", site.get("CEP"))

    st.markdown("**Operacional**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        mostrar_item_contratual("Latitude", site.get("Latitude"))

    with col2:
        mostrar_item_contratual("Longitude", site.get("Longitude"))

    with col3:
        mostrar_item_contratual("Altura", site.get("Altura"))

    with col4:
        mostrar_item_contratual("Restrição", site.get("Restricao"))

    st.markdown("**Observações**")
    col1, col2 = st.columns(2)

    with col1:
        mostrar_item_contratual("Detalhe", site.get("Detalhe"))

    with col2:
        mostrar_item_contratual("Observação", site.get("Observacao"))


def contatos_do_site(df_contatos, codigo, snmpc=""):
    codigo = normalize_code(codigo)

    if df_contatos.empty:
        return df_contatos.copy()

    return df_contatos[
        df_contatos["CÓDIGO AQUILES"].apply(normalize_code) == codigo
    ].copy()


def importar_contatos_upload(arquivo):
    nome = arquivo.name.lower()

    if nome.endswith(".csv"):
        return pd.read_csv(
            arquivo,
            dtype=object
        )

    xls = pd.ExcelFile(arquivo)
    aba = "CONTATOS" if "CONTATOS" in xls.sheet_names else xls.sheet_names[0]

    return pd.read_excel(
        arquivo,
        sheet_name=aba,
        dtype=object
    )


def mostrar_contatos_site(
    df_contatos,
    codigo,
    snmpc,
    pode_editar,
    sufixo
):
    st.subheader("Contatos do site")

    codigo = normalize_code(codigo)
    df_site = contatos_do_site(
        df_contatos,
        codigo,
        snmpc
    )

    if df_site.empty:
        st.info("Nenhum contato cadastrado para este site.")
    else:
        _mostrar_grid(
            df_site,
            height=220,
            key=chave_campo_site(
                sufixo,
                "contatos_lista"
            )
        )

    if not pode_editar:
        return

    col1, col2, col3, col4, col5 = st.columns([1.1, 1.2, 1, 1, 0.8])

    with col1:
        tipo_contato = st.text_input(
            "Tipo de contato",
            key=chave_campo_site(
                sufixo,
                "tipo_contato"
            )
        )

    with col2:
        nome_contato = st.text_input(
            "Nome",
            key=chave_campo_site(
                sufixo,
                "nome_contato_site"
            )
        )

    with col3:
        telefones = st.text_area(
            "Telefones",
            height=80,
            key=chave_campo_site(
                sufixo,
                "telefones_contato_site"
            )
        )

    with col4:
        emails = st.text_area(
            "Emails",
            height=80,
            key=chave_campo_site(
                sufixo,
                "emails_contato_site"
            )
        )

    with col5:
        adicionar = st.button(
            "Adicionar contato",
            key=chave_campo_site(
                sufixo,
                "adicionar_contato"
            )
        )

    if adicionar:
        if not codigo:
            st.error("Salve o site com Código Aquiles antes de adicionar contatos.")
        elif not any([
            tipo_contato.strip(),
            nome_contato.strip(),
            telefones.strip(),
            emails.strip()
        ]):
            st.error("Informe pelo menos um dado do contato.")
        else:
            novo_contato = pd.DataFrame([
                {
                    "CÓDIGO AQUILES": codigo,
                    "Tipo de contato": tipo_contato.strip(),
                    "Nome": nome_contato.strip(),
                    "Telefones": telefones.strip(),
                    "Emails": emails.strip()
                }
            ])
            df_atualizado = pd.concat(
                [
                    df_contatos,
                    novo_contato
                ],
                ignore_index=True
            )
            backup = save_site_contacts(
                df_atualizado
            )
            usuario_atual = _usuario_logado()
            registrar_log_sistema(
                "site_contato_adicionado",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes={
                    "codigo": codigo,
                    "backup": str(backup or "")
                }
            )
            st.success("Contato adicionado.")
            st.rerun()

    if not df_site.empty:
        opcoes_remocao = [
            f"{indice} - {linha['Tipo de contato']} - {linha.get('Nome', '')} - {linha.get('Telefones', '')} - {linha.get('Emails', '')}"
            for indice, linha in df_site.iterrows()
        ]
        remover = st.multiselect(
            "Remover contatos selecionados",
            opcoes_remocao,
            key=chave_campo_site(
                sufixo,
                "remover_contatos"
            )
        )

        if st.button(
            "Remover contatos",
            key=chave_campo_site(
                sufixo,
                "remover_contatos_botao"
            )
        ):
            indices = [
                int(opcao.split(" - ", 1)[0])
                for opcao in remover
            ]

            if not indices:
                st.warning("Selecione ao menos um contato para remover.")
            else:
                df_atualizado = df_contatos.drop(
                    index=indices
                ).reset_index(drop=True)
                backup = save_site_contacts(
                    df_atualizado
                )
                usuario_atual = _usuario_logado()
                registrar_log_sistema(
                    "site_contato_removido",
                    usuario=usuario_atual["username"],
                    status="sucesso",
                    detalhes={
                        "codigo": codigo,
                        "quantidade": len(indices),
                        "backup": str(backup or "")
                    }
                )
                st.success("Contatos removidos.")
                st.rerun()


def mostrar_importacao_contatos(df_contatos, pode_editar):
    st.subheader("Importar contatos")

    if not pode_editar:
        st.info("Seu perfil pode consultar contatos, mas não importar alterações.")
        return

    arquivo = st.file_uploader(
        "Arquivo de contatos",
        type=[
            "xlsx",
            "xls",
            "csv"
        ],
        key="gerenciar_sites_importar_contatos"
    )
    modo = st.radio(
        "Modo de importação",
        [
            "Adicionar aos contatos existentes",
            "Substituir tabela de contatos"
        ],
        horizontal=True,
        key="gerenciar_sites_modo_importar_contatos"
    )

    st.caption(
        "O arquivo deve conter as colunas: Código Aquiles, "
        "Tipo de contato, Nome, Telefones e E-mails. Em Excel, a aba CONTATOS será usada quando existir."
    )

    if not arquivo:
        return

    if st.button(
        "Importar contatos",
        key="gerenciar_sites_importar_contatos_botao"
    ):
        try:
            df_importado = normalize_site_contacts(
                importar_contatos_upload(arquivo)
            )

            if df_importado.empty:
                st.warning("Nenhum contato válido encontrado no arquivo.")
                return

            if modo == "Substituir tabela de contatos":
                df_atualizado = df_importado
            else:
                df_atualizado = pd.concat(
                    [
                        df_contatos,
                        df_importado
                    ],
                    ignore_index=True
                )

            backup = save_site_contacts(
                df_atualizado
            )
            usuario_atual = _usuario_logado()
            registrar_log_sistema(
                "site_contatos_importados",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes={
                    "quantidade": len(df_importado),
                    "modo": modo,
                    "backup": str(backup or "")
                }
            )
            st.success(f"{len(df_importado)} contatos importados.")
            st.rerun()
        except Exception as erro:
            usuario_atual = _usuario_logado()
            registrar_log_sistema(
                "site_contatos_importados",
                usuario=usuario_atual["username"],
                status="erro",
                detalhes={
                    "erro": str(erro)
                }
            )
            st.error(f"Falha ao importar contatos: {erro}")


def opcao_site_contato(linha):
    codigo = normalize_code(
        linha.get(SITE_CODE_COLUMN)
    )
    nome_snmpc = valor_exibicao_site(
        linha.get("SMNPC")
    )
    nome = valor_exibicao_site(
        linha.get("NOME")
    )
    microsiga = valor_exibicao_site(
        linha.get("CÓDIGO MICROSIGA")
    )

    return (
        f"{nome_snmpc or '-'} - {codigo or '-'} / "
        f"{nome or '-'} - {microsiga or '-'}"
    )


def mostrar_editor_contatos_site(codigo_site, nome_site, pode_editar, prefixo):
    df_contatos = load_site_contacts()
    codigo_site = normalize_code(
        codigo_site
    )
    df_site = contatos_do_site(
        df_contatos,
        codigo_site,
        ""
    )

    col1, col2 = st.columns(2)

    col1.metric(
        "Código Aquiles",
        codigo_site or "-"
    )
    col2.metric(
        "Contatos",
        len(df_site)
    )

    st.subheader("Lista de contatos")

    if df_site.empty:
        st.info("Nenhum contato cadastrado para este site.")
    else:
        _mostrar_grid(
            df_site,
            height=260,
            key=f"{prefixo}_contatos_sites_lista"
        )

    if not pode_editar:
        st.info("Seu perfil pode consultar contatos, mas não alterar o cadastro.")
        return

    st.subheader("Incluir ou editar contato")

    opcoes_contato = [
        "Novo contato"
    ] + [
        f"{indice} - {linha.get('Tipo de contato', '')} - {linha.get('Nome', '')} - {linha.get('Telefones', '')} - {linha.get('Emails', '')}"
        for indice, linha in df_site.iterrows()
    ]

    escolha_contato = st.selectbox(
        "Contato",
        opcoes_contato,
        key=f"{prefixo}_contatos_sites_contato"
    )

    indice_contato = None
    contato_atual = {}

    if escolha_contato != "Novo contato":
        indice_contato = int(
            escolha_contato.split(
                " - ",
                1
            )[0]
        )
        contato_atual = df_contatos.loc[indice_contato].to_dict()

    sufixo = f"{prefixo}_{codigo_site}_{indice_contato if indice_contato is not None else 'novo'}"
    col1, col2 = st.columns(2)

    with col1:
        tipo_contato = st.text_input(
            "Tipo de contato",
            value=str(contato_atual.get("Tipo de contato") or ""),
            key=chave_campo_site(sufixo, "aba_tipo_contato")
        )

    with col2:
        nome_contato = st.text_input(
            "Nome",
            value=str(contato_atual.get("Nome") or ""),
            key=chave_campo_site(sufixo, "aba_nome_contato")
        )

    col1, col2 = st.columns(2)

    with col1:
        telefones = st.text_area(
            "Telefones",
            value=str(contato_atual.get("Telefones") or ""),
            height=110,
            key=chave_campo_site(sufixo, "aba_telefones_contato")
        )

    with col2:
        emails = st.text_area(
            "Emails",
            value=str(contato_atual.get("Emails") or ""),
            height=110,
            key=chave_campo_site(sufixo, "aba_emails_contato")
        )

    col1, col2 = st.columns([1, 4])

    with col1:
        salvar = st.button(
            "Salvar contato",
            type="primary",
            key=chave_campo_site(sufixo, "aba_salvar_contato")
        )

    with col2:
        excluir = (
            st.button(
                "Excluir contato",
                key=chave_campo_site(sufixo, "aba_excluir_contato")
            )
            if indice_contato is not None
            else False
        )

    if salvar:
        if not any([
            tipo_contato.strip(),
            nome_contato.strip(),
            telefones.strip(),
            emails.strip()
        ]):
            st.error("Informe pelo menos um dado do contato.")
            return

        registro = {
            "CÓDIGO AQUILES": codigo_site,
            "Tipo de contato": tipo_contato.strip(),
            "Nome": nome_contato.strip(),
            "Telefones": telefones.strip(),
            "Emails": emails.strip()
        }

        if indice_contato is None:
            df_atualizado = pd.concat(
                [
                    df_contatos,
                    pd.DataFrame([registro])
                ],
                ignore_index=True
            )
            acao = "site_contato_adicionado"
        else:
            df_atualizado = df_contatos.copy()

            for coluna, valor in registro.items():
                df_atualizado.at[indice_contato, coluna] = valor

            acao = "site_contato_editado"

        backup = save_site_contacts(
            df_atualizado
        )
        usuario_atual = _usuario_logado()
        registrar_log_sistema(
            acao,
            usuario=usuario_atual["username"],
            status="sucesso",
            detalhes={
                "codigo": codigo_site,
                "site": nome_site,
                "backup": str(backup or "")
            }
        )
        st.success("Contato salvo.")
        st.rerun()

    if excluir:
        df_atualizado = df_contatos.drop(
            index=indice_contato
        ).reset_index(drop=True)
        backup = save_site_contacts(
            df_atualizado
        )
        usuario_atual = _usuario_logado()
        registrar_log_sistema(
            "site_contato_excluido",
            usuario=usuario_atual["username"],
            status="sucesso",
            detalhes={
                "codigo": codigo_site,
                "site": nome_site,
                "backup": str(backup or "")
            }
        )
        st.success("Contato excluído.")
        st.rerun()


def mostrar_gerenciar_contatos_sites():
    st.header("Contatos dos Sites")

    usuario_atual = _usuario_logado()
    pode_editar = has_permission(
        usuario_atual,
        "editar_contatos_sites"
    )

    df_cadastro = load_site_registry()

    if df_cadastro.empty:
        st.info("Nenhum site cadastrado na planilha Sites.")
        return

    opcoes_sites = [
        opcao_site_contato(linha)
        for _, linha in df_cadastro.sort_values(
            by=[
                "NOME",
                "SMNPC"
            ]
        ).iterrows()
    ]

    site_escolhido = st.selectbox(
        "Site",
        opcoes_sites,
        index=None,
        placeholder="Digite para pesquisar e selecione um site",
        key="contatos_sites_site"
    )

    if site_escolhido is None:
        st.info("Pesquise e selecione um site para gerenciar os contatos.")
        return

    codigo_site = normalize_code(
        site_escolhido.split(
            " - ",
            1
        )[0]
    )
    registro_site = df_cadastro[
        df_cadastro[SITE_CODE_COLUMN].apply(normalize_code) == codigo_site
    ]
    nome_site = ""

    if not registro_site.empty:
        linha_site = registro_site.iloc[0]
        nome_site = linha_site.get("NOME") or linha_site.get("SMNPC") or ""

    mostrar_editor_contatos_site(
        codigo_site,
        nome_site,
        pode_editar,
        "contatos_sites"
    )


def mostrar_cadastro_site_selecionado(site):
    usuario_atual = _usuario_logado()
    pode_editar = has_permission(
        usuario_atual,
        "editar_sites"
    )

    if not pode_editar:
        st.info("Seu perfil pode consultar o cadastro, mas não alterar os dados do site.")
        return

    df_cadastro = load_site_registry()
    codigo_original = normalize_code(
        site.get("Codigo")
    )
    registro = {}

    if codigo_original:
        codigos = df_cadastro[SITE_CODE_COLUMN].apply(normalize_code)
        registro_df = df_cadastro[
            codigos == codigo_original
        ]

        if not registro_df.empty:
            registro = registro_df.iloc[0].to_dict()

    if not registro:
        registro = {
            "CÓDIGO AQUILES": codigo_original,
            "CÓDIGO MICROSIGA": site.get("Microsiga") or "",
            "CÓDIGO CONDOMINIO": site.get("Codigo Condominio") or "",
            "ABREVIAÇÃO": site.get("Abreviacao") or "",
            "SMNPC": site.get("SNMPc") or site.get("Site SNMPc") or "",
            "TIPO": site.get("Tipo") or "",
            "NOME": site.get("Nome Cadastro") or "",
            "Relacionamento": site.get("Relacionamento") or "",
            "Favorecido": site.get("Favorecido") or "",
            "CONTRATO": site.get("Contrato") or "",
            "QTDO": site.get("Qtdo") or 0,
            "CATEGORIA": site.get("Categoria") or "",
            "PERFIL": site.get("Perfil") or "",
            "CUSTO": site.get("Custo") or "",
            "ENDEREÇO": site.get("Endereco") or "",
            "NUMERO": site.get("Numero") or "",
            "BAIRRO": site.get("Bairro") or "",
            "CIDADE": site.get("Cidade") or "",
            "UF": site.get("UF") or "",
            "CEP": site.get("CEP") or "",
            "ATIVAÇÃO": site.get("Ativacao") or "",
            "LATITUDE": site.get("Latitude") or "",
            "LONGITUDE": site.get("Longitude") or "",
            "ALTURA": site.get("Altura") or 0,
            "RESTRIÇÃO": site.get("Restricao") or "",
            "Status": site.get("Status Cadastro") or "",
            "Detalhe": site.get("Detalhe") or "",
            "OBSERVAÇÃO:": site.get("Observacao") or ""
        }

    st.subheader("Cadastro do site")

    sufixo_formulario = f"unificado_{codigo_original or site.get('Site SNMPc') or 'novo'}"
    registro_formulario = montar_registro_site_formulario(
        registro,
        df_cadastro,
        sufixo_formulario
    )

    if st.button(
        "Salvar cadastro do site",
        type="primary",
        key=chave_campo_site(
            sufixo_formulario,
            "salvar_unificado"
        )
    ):
        try:
            backup = upsert_site(
                registro_formulario,
                original_code=codigo_original
            )

            if _carregar_dados is not None and hasattr(_carregar_dados, "clear"):
                _carregar_dados.clear()

            registrar_log_sistema(
                "site_cadastro_salvo",
                usuario=usuario_atual["username"],
                status="sucesso",
                detalhes={
                    "codigo": registro_formulario[SITE_CODE_COLUMN],
                    "backup": str(backup or "")
                }
            )
            st.success("Site salvo. A lista foi atualizada.")
            st.rerun()
        except Exception as erro:
            registrar_log_sistema(
                "site_cadastro_salvo",
                usuario=usuario_atual["username"],
                status="erro",
                detalhes={
                    "codigo": registro_formulario.get(SITE_CODE_COLUMN),
                    "erro": str(erro)
                }
            )
            st.error(f"Falha ao salvar site: {erro}")


def mostrar_gerenciamento_sites_unificado(
    sites,
    detalhes_topos_cacheados,
    rotulo_site_gerenciamento,
):
    st.header("Gerenciamento de Sites")

    df_detalhes = detalhes_topos_cacheados(
        sites
    )

    if df_detalhes.empty:
        st.info("A planilha imports/Sites.xlsx não possui registros válidos.")
        return

    df_detalhes = df_detalhes.copy()
    df_detalhes["Busca"] = df_detalhes.apply(
        rotulo_site_gerenciamento,
        axis=1
    )

    abrir_site = str(
        st.session_state.pop(
            "abrir_site_gerenciamento",
            ""
        ) or ""
    ).strip()

    if abrir_site:

        chave_abrir = abrir_site.upper()

        for indice_busca, linha in df_detalhes.iterrows():

            candidatos = [
                linha.get("Busca"),
                linha.get("Site SNMPc"),
                linha.get("SNMPc"),
                linha.get("Codigo"),
                linha.get("Microsiga"),
                linha.get("Nome Cadastro")
            ]
            candidatos = [
                str(candidato or "").strip().upper()
                for candidato in candidatos
                if str(candidato or "").strip()
            ]

            if chave_abrir in candidatos:

                st.session_state["gerenciamento_sites_site"] = indice_busca
                break

    opcoes = (
        df_detalhes
        .sort_values(
            by=[
                "Tipo",
                "Busca"
            ]
        )
        .index
        .tolist()
    )

    indice = st.selectbox(
        "Site",
        opcoes,
        index=None,
        placeholder="Digite para pesquisar e selecione um site",
        format_func=lambda idx: df_detalhes.loc[idx, "Busca"],
        key="gerenciamento_sites_site"
    )

    if indice is None:
        st.info("Pesquise e selecione um site para abrir o gerenciamento.")
        return

    site = df_detalhes.loc[indice]
    site_modelo = localizar_site_modelo(
        sites,
        site
    )

    st.caption(
        f"Site selecionado: {valor_exibicao_site(site.get('Busca'))}"
    )

    usuario_atual = _usuario_logado()
    subabas = [
        (
            "gerenciar_sites_resumo_financeiro",
            "Resumo Financeiro",
            lambda: mostrar_financeiro_site_selecionado(
                site,
                site_modelo
            )
        ),
        (
            "gerenciar_sites_detalhes",
            "Detalhes",
            lambda: mostrar_contratual_site_selecionado(site)
        ),
        (
            "gerenciar_sites_arquivos",
            "Documentos",
            lambda: mostrar_contratos_site(site)
        ),
        (
            "gerenciar_sites_contatos",
            "Contatos",
            lambda: mostrar_editor_contatos_site(
                site.get("Codigo"),
                site.get("Nome Cadastro") or site.get("Site SNMPc"),
                has_permission(usuario_atual, "editar_contatos_sites"),
                "gerenciamento_sites"
            )
        ),
        (
            "gerenciar_sites_editar",
            "Editar",
            lambda: mostrar_cadastro_site_selecionado(site)
        )
    ]
    subabas_permitidas = [
        subaba
        for subaba in subabas
        if has_permission(
            usuario_atual,
            subaba[0]
        )
    ]

    if not subabas_permitidas:
        st.warning("Seu usuário não possui permissões para as subabas deste módulo.")
        return

    funcao = mostrar_subnavegacao(
        subabas_permitidas,
        key="gerenciamento_sites_subaba"
    )

    if funcao:
        funcao()
