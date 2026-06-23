from pyvis.network import Network

import networkx as nx


MAX_NODES = 300


def gerar_mapa_rede(raizes):

    grafo = nx.DiGraph()

    visitados = set()

    total_nos = 0

    def adicionar_site(site, nivel=0):

        nonlocal total_nos

        # Limitar profundidade
        if nivel > 4:
            return

        # Limitar quantidade
        if total_nos > MAX_NODES:
            return

        # Evitar loops
        if site.nome in visitados:
            return

        visitados.add(site.nome)

        total_nos += 1

        # Cor por tipo
        cor = "#97C2FC"

        if site.tipo == "POP":
            cor = "#ff4b4b"

        elif site.tipo == "BH":
            cor = "#f7b731"

        elif site.tipo == "REP":
            cor = "#26de81"

        receita = site.calcular_receita()

        titulo = (
            f"{site.nome}<br>"
            f"Tipo: {site.tipo}<br>"
            f"Receita: R$ {receita:,.2f}<br>"
            f"Clientes: {len(site.clientes)}"
        )

        tamanho = min(
            50,
            max(
                15,
                len(site.clientes) // 2 + 15
            )
        )

        # Adicionar nó
        grafo.add_node(
            site.nome,
            title=titulo,
            color=cor,
            size=tamanho
        )

        # Filhos
        for filho in site.filhos:

            grafo.add_edge(
                site.nome,
                filho.nome
            )

            adicionar_site(
                filho,
                nivel + 1
            )

    # Montar grafo
    for raiz in raizes:

        adicionar_site(raiz)

    # Criar visualização
    net = Network(
        height="850px",
        width="100%",
        directed=True,
        bgcolor="#111111",
        font_color="white"
    )

    net.from_nx(grafo)

    # Física leve
    net.barnes_hut(
        gravity=-3000,
        central_gravity=0.1,
        spring_length=120,
        spring_strength=0.02,
        damping=0.09
    )

    # Melhor navegação
    net.set_options("""
    {
      "interaction": {
        "hover": true,
        "navigationButtons": true,
        "keyboard": true
      },
      "physics": {
        "enabled": true
      }
    }
    """)

    caminho = "app/ui/rede.html"

    net.save_graph(caminho)

    return caminho
