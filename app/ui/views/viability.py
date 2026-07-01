import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.auth import has_permission
from app.services.client_viability import dados_cliente_viabilidade
from app.services.client_viability import salvar_dados_cliente_viabilidade
from app.services.elevation_service import carregar_cache_elevacao
from app.services.elevation_service import elevacoes_pontos
from app.services.line_of_sight import analisar_visada
from app.services.line_of_sight import coordenada_valida
from app.services.line_of_sight import distancia_km
from app.services.line_of_sight import pontos_intermediarios
from app.services.line_of_sight import valor_float
from app.services.map_service import carregar_cache_geocoding
from app.services.map_service import endereco_cliente
from app.services.map_service import geocodificar_endereco
from app.services.map_service import salvar_cache_geocoding
from app.services.map_settings import load_map_config
from app.ui.navigation import mostrar_subnavegacao


_usuario_logado = None
_mostrar_grid = None


def configurar_viabilidade(usuario_logado, mostrar_grid=None):
    global _usuario_logado
    global _mostrar_grid

    _usuario_logado = usuario_logado
    _mostrar_grid = mostrar_grid


def usuario_atual():
    return _usuario_logado() if _usuario_logado else {}


def ponto_site(site):
    return {
        "Tipo": "Site",
        "Nome": getattr(site, "nome", ""),
        "Latitude": valor_float(getattr(site, "latitude", 0)),
        "Longitude": valor_float(getattr(site, "longitude", 0)),
        "Altitude": 0.0,
        "Altura": valor_float(getattr(site, "altura", 0))
    }


def cliente_por_assinatura(sites, assinatura):
    assinatura = str(assinatura or "").strip()

    for site in (sites or {}).values():
        for cliente in getattr(site, "clientes", []):
            if str(getattr(cliente, "num_assinatura", "")).strip() == assinatura:
                return site, cliente

    return None, None


def opcoes_clientes(sites):
    opcoes = []

    for site in (sites or {}).values():
        for cliente in getattr(site, "clientes", []):
            assinatura = str(getattr(cliente, "num_assinatura", "") or "").strip()

            if assinatura:
                opcoes.append((
                    assinatura,
                    f"{cliente.nome} - {assinatura} / {site.nome}"
                ))

    return sorted(
        opcoes,
        key=lambda item: item[1].casefold()
    )


def geocodificar_texto(endereco):
    cache = carregar_cache_geocoding()
    ponto = geocodificar_endereco(
        endereco,
        cache
    )
    salvar_cache_geocoding(cache)
    return ponto


def ponto_cliente(site, cliente):
    assinatura = str(getattr(cliente, "num_assinatura", "") or "").strip()
    dados = dados_cliente_viabilidade(assinatura)
    latitude = valor_float(dados.get("latitude", 0))
    longitude = valor_float(dados.get("longitude", 0))

    if not coordenada_valida(latitude, longitude):
        endereco = endereco_cliente(cliente)
        if endereco:
            try:
                ponto = geocodificar_texto(endereco)
                if ponto:
                    latitude = ponto["lat"]
                    longitude = ponto["lon"]
            except Exception:
                pass

    return {
        "Tipo": "Cliente",
        "Nome": getattr(cliente, "nome", ""),
        "Assinatura": assinatura,
        "Site Atual": getattr(site, "nome", ""),
        "Latitude": latitude,
        "Longitude": longitude,
        "Altitude": valor_float(dados.get("altitude", 0)),
        "Altura": valor_float(dados.get("altura", 0)),
        "Endereco": endereco_cliente(cliente)
    }


def sites_candidatos(sites, ponto_origem, raio_km):
    candidatos = []

    for site in (sites or {}).values():
        ponto = ponto_site(site)

        if not coordenada_valida(ponto["Latitude"], ponto["Longitude"]):
            continue

        distancia = distancia_km(
            ponto_origem["Latitude"],
            ponto_origem["Longitude"],
            ponto["Latitude"],
            ponto["Longitude"]
        )

        if distancia <= raio_km:
            candidatos.append((
                site,
                ponto,
                distancia
            ))

    return sorted(
        candidatos,
        key=lambda item: item[2]
    )


def analisar_ponto_para_site(ponto_origem, ponto_destino, config):
    pontos = pontos_intermediarios(
        ponto_origem,
        ponto_destino,
        distancia_amostra_m=config.get("line_of_sight_sample_distance_m", 100)
    )
    elevacoes, estimado = elevacoes_pontos(
        pontos,
        config=config,
        cache=carregar_cache_elevacao()
    )

    if elevacoes:
        ponto_origem = {
            **ponto_origem,
            "Altitude": ponto_origem.get("Altitude") or elevacoes[0]
        }
        ponto_destino = {
            **ponto_destino,
            "Altitude": ponto_destino.get("Altitude") or elevacoes[-1]
        }

    return analisar_visada(
        ponto_origem,
        ponto_destino,
        elevacoes=elevacoes,
        estimado=estimado,
        frequencia_ghz=config.get("line_of_sight_frequency_ghz", 5.8),
        fresnel_minimo=config.get("line_of_sight_fresnel_clearance", 0.60),
        distancia_amostra_m=config.get("line_of_sight_sample_distance_m", 100)
    )


def montar_resultados_viabilidade(sites, ponto_origem, raio_km, limite_sites=10):
    if not coordenada_valida(ponto_origem.get("Latitude"), ponto_origem.get("Longitude")):
        return pd.DataFrame(), {}

    config = load_map_config()
    registros = []
    perfis = {}

    for site, ponto_destino, distancia in sites_candidatos(
        sites,
        ponto_origem,
        raio_km
    )[:int(limite_sites)]:
        analise = analisar_ponto_para_site(
            ponto_origem,
            ponto_destino,
            config
        )
        chave = getattr(site, "nome", "")
        perfis[chave] = analise.get("Perfil", pd.DataFrame())
        ponto_critico = analise.get("Ponto crítico", {})
        registros.append({
            "Site": chave,
            "Tipo": getattr(site, "tipo", ""),
            "Nome": getattr(site, "nome_cadastro", ""),
            "Distância km": distancia,
            "Status": analise.get("Status"),
            "Menor margem m": analise.get("Menor margem m"),
            "Ponto crítico km": ponto_critico.get("Distância km", 0),
            "Estimado": "Sim" if analise.get("Estimado") else "Não",
            "Latitude Site": ponto_destino["Latitude"],
            "Longitude Site": ponto_destino["Longitude"],
            "Altura Site": ponto_destino["Altura"]
        })

    return pd.DataFrame(registros), perfis


def chave_estado_resultados_visada(key):
    return f"{key}_resultados_visada"


def salvar_resultados_visada_estado(key, df_resultados, perfis):
    st.session_state[chave_estado_resultados_visada(key)] = {
        "df_resultados": df_resultados,
        "perfis": perfis
    }


def carregar_resultados_visada_estado(key):
    dados = st.session_state.get(chave_estado_resultados_visada(key), {})
    df_resultados = dados.get("df_resultados")
    perfis = dados.get("perfis")

    if df_resultados is None or perfis is None:
        return None, None

    return df_resultados, perfis


def preparar_dados_grafico_visada(perfil):
    if perfil is None or perfil.empty:
        return pd.DataFrame()

    dados = perfil.copy()
    dados["Terreno Ajustado m"] = (
        dados["Altitude Terreno m"].astype(float)
        + dados["Curvatura Terra m"].astype(float)
    )
    dados["Fresnel Inferior m"] = (
        dados["Linha Visada m"].astype(float)
        - dados["Fresnel Exigido m"].astype(float)
    )
    dados["Fresnel Superior m"] = (
        dados["Linha Visada m"].astype(float)
        + dados["Fresnel Exigido m"].astype(float)
    )
    dados["Terreno Suavizado m"] = suavizar_serie_terreno(
        dados["Terreno Ajustado m"]
    )

    return dados


def suavizar_serie_terreno(serie):
    serie = pd.Series(serie).astype(float)

    if len(serie) < 3:
        return serie

    janela = min(15, max(3, int(len(serie) * 0.08)))
    if janela % 2 == 0:
        janela += 1

    return serie.rolling(
        window=janela,
        min_periods=1,
        center=True
    ).mean()


def escala_y_grafico_visada(dados):
    if dados is None or dados.empty:
        return 0.0, 1.0, 0.0

    colunas_minimas = [
        "Terreno Ajustado m",
        "Terreno Suavizado m",
        "Fresnel Inferior m"
    ]
    colunas_maximas = [
        "Terreno Ajustado m",
        "Terreno Suavizado m",
        "Linha Visada m",
        "Fresnel Superior m"
    ]
    y_min_base = min(
        float(dados[coluna].min())
        for coluna in colunas_minimas
        if coluna in dados
    )
    y_max_base = max(
        float(dados[coluna].max())
        for coluna in colunas_maximas
        if coluna in dados
    )
    amplitude = max(y_max_base - y_min_base, 20.0)
    margem = max(amplitude * 0.10, 10.0)
    y_min = y_min_base - margem
    y_max = y_max_base + margem
    if y_max - y_min < 40.0:
        centro = (y_min + y_max) / 2
        y_min = centro - 20.0
        y_max = centro + 20.0
    base_terreno = y_min

    return y_min, y_max, base_terreno


def montar_grafico_perfil_visada(perfil, site="", status=""):
    dados = preparar_dados_grafico_visada(perfil)
    fig = go.Figure()

    if dados.empty:
        fig.update_layout(
            title="Perfil de visada indisponível",
            height=360
        )
        return fig

    ponto_critico = dados.sort_values("Margem m").iloc[0]
    cor_critico = (
        "#ef4444"
        if float(ponto_critico["Margem m"]) < 0
        else "#f59e0b"
    )
    y_min, y_max, base_terreno = escala_y_grafico_visada(dados)

    fig.add_trace(go.Scatter(
        x=dados["Distância km"],
        y=[
            base_terreno
        ] * len(dados),
        mode="lines",
        name="Base visual",
        line={
            "color": "rgba(116, 105, 135, 0)",
            "width": 0
        },
        hoverinfo="skip",
        showlegend=False
    ))
    fig.add_trace(go.Scatter(
        x=dados["Distância km"],
        y=dados["Terreno Suavizado m"],
        mode="lines",
        name="Terreno + curvatura",
        fill="tonexty",
        line={
            "color": "rgba(116, 105, 135, 0.55)",
            "width": 1,
            "shape": "spline"
        },
        customdata=dados["Terreno Ajustado m"],
        hovertemplate=(
            "Distância: %{x:.2f} km<br>"
            "Terreno real: %{customdata:.1f} m<br>"
            "Terreno suavizado: %{y:.1f} m<extra></extra>"
        ),
        fillcolor="rgba(116, 105, 135, 0.35)"
    ))
    fig.add_trace(go.Scatter(
        x=dados["Distância km"],
        y=dados["Fresnel Superior m"],
        mode="lines",
        name="Fresnel superior",
        line={
            "color": "rgba(96, 165, 250, 0.45)",
            "width": 1,
            "dash": "dash",
            "shape": "spline"
        }
    ))
    fig.add_trace(go.Scatter(
        x=dados["Distância km"],
        y=dados["Fresnel Inferior m"],
        mode="lines",
        name="Fresnel exigido",
        fill="tonexty",
        line={
            "color": "rgba(96, 165, 250, 0.70)",
            "width": 1,
            "dash": "dash",
            "shape": "spline"
        },
        fillcolor="rgba(96, 165, 250, 0.18)"
    ))
    fig.add_trace(go.Scatter(
        x=dados["Distância km"],
        y=dados["Linha Visada m"],
        mode="lines",
        name="Linha de visada",
        line={
            "color": "#2563eb",
            "width": 3
        }
    ))
    ponta_origem = dados.iloc[0]
    ponta_destino = dados.iloc[-1]
    for nome_haste, ponta in [
        (
            "Haste origem",
            ponta_origem
        ),
        (
            "Haste destino",
            ponta_destino
        )
    ]:
        altura_aplicada = float(ponta.get("Altura Ponta m") or 0)
        fig.add_trace(go.Scatter(
            x=[
                ponta["Distância km"],
                ponta["Distância km"]
            ],
            y=[
                ponta["Terreno Ajustado m"],
                ponta["Linha Visada m"]
            ],
            mode="lines",
            name=nome_haste,
            line={
                "color": "rgba(29, 78, 216, 0.75)",
                "width": 2
            },
            customdata=[
                [
                    ponta["Terreno Ajustado m"],
                    altura_aplicada,
                    ponta["Linha Visada m"]
                ],
                [
                    ponta["Terreno Ajustado m"],
                    altura_aplicada,
                    ponta["Linha Visada m"]
                ]
            ],
            hovertemplate=(
                f"{nome_haste}<br>"
                "Solo: %{customdata[0]:.1f} m<br>"
                "Altura aplicada: %{customdata[1]:.1f} m<br>"
                "Altura final: %{customdata[2]:.1f} m<extra></extra>"
            ),
            showlegend=True
        ))
    fig.add_trace(go.Scatter(
        x=[
            ponta_origem["Distância km"],
            ponta_destino["Distância km"]
        ],
        y=[
            ponta_origem["Linha Visada m"],
            ponta_destino["Linha Visada m"]
        ],
        mode="markers+text",
        name="Pontas",
        text=[
            "Origem",
            site or "Destino"
        ],
        textposition=[
            "top center",
            "top center"
        ],
        marker={
            "color": "#1d4ed8",
            "size": 14,
            "line": {
                "color": "#eff6ff",
                "width": 2
            }
        },
        customdata=[
            [
                ponta_origem["Terreno Ajustado m"],
                float(ponta_origem.get("Altura Ponta m") or 0),
                ponta_origem["Linha Visada m"]
            ],
            [
                ponta_destino["Terreno Ajustado m"],
                float(ponta_destino.get("Altura Ponta m") or 0),
                ponta_destino["Linha Visada m"]
            ]
        ],
        hovertemplate=(
            "%{text}<br>"
            "Solo: %{customdata[0]:.1f} m<br>"
            "Altura aplicada: %{customdata[1]:.1f} m<br>"
            "Altura final: %{customdata[2]:.1f} m<extra></extra>"
        )
    ))
    fig.add_trace(go.Scatter(
        x=[
            ponto_critico["Distância km"]
        ],
        y=[
            ponto_critico["Terreno Ajustado m"]
        ],
        mode="markers+text",
        name="Ponto crítico",
        text=[
            f"Margem {float(ponto_critico['Margem m']):.1f} m"
        ],
        textposition="bottom center",
        marker={
            "color": cor_critico,
            "size": 13,
            "symbol": "diamond",
            "line": {
                "color": "#111827",
                "width": 1
            }
        }
    ))
    fig.update_layout(
        title=f"Perfil de visada - {site or 'Destino'} ({status or 'sem status'})",
        height=390,
        margin={
            "l": 12,
            "r": 12,
            "t": 48,
            "b": 12
        },
        xaxis_title="Distância (km)",
        yaxis_title="Elevação / altura (m)",
        yaxis={
            "range": [
                y_min,
                y_max
            ]
        },
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1
        },
        hovermode="x unified",
        template="plotly_white"
    )

    return fig


def mostrar_resultados(df_resultados, perfis, key):
    if df_resultados.empty:
        st.info("Nenhum site candidato encontrado para os critérios informados.")
        return

    st.markdown("**Sites candidatos**")
    if _mostrar_grid:
        _mostrar_grid(
            df_resultados,
            height=420,
            key=f"{key}_resultados"
        )
    else:
        st.dataframe(
            df_resultados,
            use_container_width=True,
            hide_index=True
        )

    site_perfil = st.selectbox(
        "Perfil de visada",
        df_resultados["Site"].tolist(),
        key=f"{key}_perfil_site"
    )
    perfil = perfis.get(site_perfil, pd.DataFrame())

    if perfil.empty:
        st.info("Perfil indisponível para o site selecionado.")
    else:
        linha_site = df_resultados[
            df_resultados["Site"].astype(str) == str(site_perfil)
        ].iloc[0]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Distância", f"{float(linha_site.get('Distância km') or 0):.2f} km")
        col2.metric("Menor margem", f"{float(linha_site.get('Menor margem m') or 0):.1f} m")
        col3.metric("Status", str(linha_site.get("Status") or ""))
        col4.metric("Ponto crítico", f"{float(linha_site.get('Ponto crítico km') or 0):.2f} km")

        st.plotly_chart(
            montar_grafico_perfil_visada(
                perfil,
                site=site_perfil,
                status=linha_site.get("Status")
            ),
            use_container_width=True
        )

        with st.expander("Dados técnicos do perfil"):
            st.dataframe(
                perfil,
                use_container_width=True,
                hide_index=True,
                height=360
            )


def mostrar_viabilidade_endereco(sites):
    st.header("Viabilidade")
    st.caption("Informe um endereço para avaliar quais sites próximos podem atender por rádio.")

    endereco = st.text_input(
        "Endereço",
        key="viabilidade_endereco"
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        raio_km = st.number_input(
            "Raio de busca (km)",
            min_value=1.0,
            value=10.0,
            step=1.0,
            key="viabilidade_raio_km"
        )
    with col2:
        altura = st.number_input(
            "Altura no endereço (m)",
            min_value=0.0,
            value=0.0,
            step=1.0,
            key="viabilidade_altura"
        )
    with col3:
        limite_sites = st.number_input(
            "Sites avaliados",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            key="viabilidade_limite_sites"
        )

    calcular = st.button("Calcular viabilidade", key="viabilidade_calcular")

    if not calcular:
        df_salvo, perfis_salvos = carregar_resultados_visada_estado("viabilidade_endereco")
        if df_salvo is not None:
            st.caption("Resultado da última análise calculada.")
            mostrar_resultados(
                df_salvo,
                perfis_salvos,
                key="viabilidade_endereco"
            )
        return

    if not endereco:
        st.warning("Informe um endereço para calcular a viabilidade.")
        return

    try:
        ponto_geo = geocodificar_texto(endereco)
    except Exception as erro:
        st.error(f"Falha ao geocodificar endereço: {erro}")
        return

    if not ponto_geo:
        st.warning("Endereço não localizado pelo provedor de geocodificação.")
        return

    ponto_origem = {
        "Tipo": "Endereço",
        "Nome": endereco,
        "Latitude": ponto_geo["lat"],
        "Longitude": ponto_geo["lon"],
        "Altitude": 0,
        "Altura": altura
    }
    df_resultados, perfis = montar_resultados_viabilidade(
        sites,
        ponto_origem,
        raio_km,
        limite_sites=limite_sites
    )
    salvar_resultados_visada_estado(
        "viabilidade_endereco",
        df_resultados,
        perfis
    )
    mostrar_resultados(
        df_resultados,
        perfis,
        key="viabilidade_endereco"
    )


def mostrar_migracao_cliente(sites):
    st.header("Migração")
    st.caption("Busque um cliente para avaliar possíveis sites de atendimento.")

    opcoes = opcoes_clientes(sites)

    if not opcoes:
        st.info("Nenhum cliente disponível na base atual.")
        return

    rotulos = {
        assinatura: rotulo
        for assinatura, rotulo in opcoes
    }
    assinatura = st.selectbox(
        "Cliente",
        [
            ""
        ] + [
            assinatura
            for assinatura, _rotulo in opcoes
        ],
        format_func=lambda valor: "Pesquisar cliente" if not valor else rotulos.get(valor, valor),
        key="viabilidade_migracao_cliente"
    )

    if not assinatura:
        return

    site_atual, cliente = cliente_por_assinatura(
        sites,
        assinatura
    )
    ponto = ponto_cliente(
        site_atual,
        cliente
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        latitude = st.number_input(
            "Latitude",
            value=float(ponto["Latitude"] or 0),
            format="%.6f",
            key="viabilidade_cliente_latitude"
        )
    with col2:
        longitude = st.number_input(
            "Longitude",
            value=float(ponto["Longitude"] or 0),
            format="%.6f",
            key="viabilidade_cliente_longitude"
        )
    with col3:
        altitude = st.number_input(
            "Altitude terreno (m)",
            value=float(ponto["Altitude"] or 0),
            step=1.0,
            key="viabilidade_cliente_altitude"
        )
    with col4:
        altura = st.number_input(
            "Altura instalação (m)",
            min_value=0.0,
            value=float(ponto["Altura"] or 0),
            step=1.0,
            key="viabilidade_cliente_altura"
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        raio_km = st.number_input(
            "Raio de busca (km)",
            min_value=1.0,
            value=10.0,
            step=1.0,
            key="viabilidade_migracao_raio"
        )
    with col2:
        limite_sites = st.number_input(
            "Sites avaliados",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            key="viabilidade_migracao_limite"
        )

    usuario = usuario_atual()
    if st.button("Salvar dados técnicos do cliente", key="viabilidade_salvar_cliente"):
        salvar_dados_cliente_viabilidade(
            assinatura,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            altura=altura,
            usuario=usuario.get("username", "")
        )
        st.success("Dados técnicos do cliente salvos.")

    calcular = st.button("Calcular migração", key="viabilidade_calcular_migracao")

    if not calcular:
        df_salvo, perfis_salvos = carregar_resultados_visada_estado("viabilidade_migracao")
        if df_salvo is not None:
            st.caption("Resultado da última análise calculada.")
            mostrar_resultados(
                df_salvo,
                perfis_salvos,
                key="viabilidade_migracao"
            )
        return

    ponto_origem = {
        **ponto,
        "Latitude": latitude,
        "Longitude": longitude,
        "Altitude": altitude,
        "Altura": altura
    }

    if not coordenada_valida(latitude, longitude):
        st.warning("Cliente sem coordenadas válidas. Ajuste latitude/longitude antes de calcular.")
        return

    df_resultados, perfis = montar_resultados_viabilidade(
        sites,
        ponto_origem,
        raio_km,
        limite_sites=limite_sites
    )
    if site_atual is not None and not df_resultados.empty:
        df_resultados = df_resultados[
            df_resultados["Site"] != getattr(site_atual, "nome", "")
        ].copy()

    salvar_resultados_visada_estado(
        "viabilidade_migracao",
        df_resultados,
        perfis
    )
    mostrar_resultados(
        df_resultados,
        perfis,
        key="viabilidade_migracao"
    )


def mostrar_estudos_engenharia():
    st.header("Estudos de Engenharia")
    st.info(
        "Este espaço será usado para estudos de concentração, otimização e redução de sites."
    )


def mostrar_viabilidade(sites, equipamentos=None):
    usuario = usuario_atual()
    subabas = [
        (
            "viabilidade_consulta",
            "Viabilidade",
            lambda: mostrar_viabilidade_endereco(sites)
        ),
        (
            "viabilidade_migracao",
            "Migração",
            lambda: mostrar_migracao_cliente(sites)
        ),
        (
            "viabilidade_estudos",
            "Estudos de Engenharia",
            mostrar_estudos_engenharia
        )
    ]
    permitidas = [
        subaba
        for subaba in subabas
        if has_permission(usuario, "viabilidade") or has_permission(usuario, subaba[0])
    ]

    if not permitidas:
        st.warning("Seu usuário não possui permissões para Viabilidade.")
        return

    funcao = mostrar_subnavegacao(
        permitidas,
        key="viabilidade_subaba"
    )

    if funcao:
        funcao()
