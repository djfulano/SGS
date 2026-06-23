from streamlit_agraph import Node
from streamlit_agraph import Edge
from streamlit_agraph import Config


def gerar_grafo(raizes, max_nodes=500):

    nodes = []

    edges = []

    visitados = set()

    def adicionar_site(site, nivel=0):

        if len(nodes) >= max_nodes:

            return

        # Evitar loops
        if site.nome in visitados:
            return False

        # Limitar profundidade
        if nivel > 5:
            return False

        visitados.add(site.nome)

        # Cor por tipo
        cor = "#3b82f6"

        if site.tipo == "POP":
            cor = "#ef4444"

        elif site.tipo == "BH":
            cor = "#f59e0b"

        elif site.tipo == "REP":
            cor = "#22c55e"

        receita = site.calcular_receita()

        titulo = (
            f"{site.nome}\n"
            f"{site.tipo}\n"
            f"R$ {receita:,.0f}"
        )

        tamanho = min(
            50,
            max(
                20,
                len(site.clientes) // 2 + 20
            )
        )

        # Nó
        nodes.append(
            Node(
                id=site.nome,
                label=site.nome,
                size=tamanho,
                color=cor,
                title=titulo
            )
        )

        # Filhos
        for filho in site.filhos:

            if len(nodes) >= max_nodes:

                break

            if filho.nome in visitados:

                continue

            if nivel + 1 > 5:

                continue

            edges.append(
                Edge(
                    source=site.nome,
                    target=filho.nome
                )
            )

            adicionar_site(
                filho,
                nivel + 1
            )

        return True

    # Processar raízes
    for raiz in raizes:

        adicionar_site(raiz)

    config = Config(
        width="100%",
        height=900,
        directed=True,
        physics=True,
        hierarchical=False,
        nodeHighlightBehavior=True,
        highlightColor="#F7A7A6",
        collapsible=True
    )

    return nodes, edges, config
