class Site:

    def __init__(self, nome, tipo="SITE", predio=None):

        self.nome = nome

        self.tipo = tipo

        self.predio = predio

        self.codigo_topos = ""

        self.microsiga = ""

        self.codigo_condominio = ""

        self.abreviacao = ""

        self.custo = 0.0

        self.status_cadastro = ""

        self.nome_cadastro = ""

        self.relacionamento = ""

        self.favorecido = ""

        self.contrato = ""

        self.categoria = ""

        self.perfil = ""

        self.endereco = ""

        self.numero = ""

        self.bairro = ""

        self.cidade = ""

        self.uf = ""

        self.cep = ""

        self.latitude = 0.0

        self.longitude = 0.0

        self.altura = 0.0

        self.restricao = ""

        self.site_critico = False

        self.dia_vencimento = 0

        self.detalhe = ""

        self.observacao = ""

        self.cadastro_topos = {}

        # Relação hierárquica
        self.pai = None

        self.filhos = []

        # Clientes vinculados
        self.clientes = []

        self.clientes_adicionais = []

        self.setoriais = {}

        self.sites_por_setorial = {}

        self.clientes_estrutura = []

        self.equipamentos = []

        self.enlaces_sites = []

        # Assinaturas relacionadas
        self.assinaturas = []

        # Cache de receita
        self.receita_cache = None

    def adicionar_filho(self, filho):

        if filho is self or self._tem_ancestral(filho):

            return False

        if filho in self.filhos:

            return False

        if filho.pai and filho in filho.pai.filhos:

            filho.pai.filhos.remove(filho)

        filho.pai = self

        self.filhos.append(filho)

        self.limpar_receita_cache()

        return True

    def _tem_ancestral(self, site):

        atual = self

        visitados = set()

        while atual:

            if atual is site:

                return True

            if id(atual) in visitados:

                return True

            visitados.add(id(atual))

            atual = atual.pai

        return False

    def adicionar_cliente(self, cliente, setorial=None):

        cliente.setorial = setorial

        self.clientes.append(cliente)

        if setorial:

            self.setoriais.setdefault(
                setorial,
                []
            ).append(cliente)

        cliente.adicionar_vinculo_atendimento(
            self,
            setorial=setorial,
            tipo="Principal",
            origem=getattr(cliente, "origem_estrutura", ""),
            predio=getattr(cliente, "predio_estrutura", None)
        )

        self.limpar_receita_cache()

    def adicionar_cliente_adicional(
        self,
        cliente,
        setorial=None,
        origem="",
        predio=None
    ):
        assinatura = str(
            getattr(cliente, "num_assinatura", "") or ""
        ).strip()
        chave = (
            assinatura,
            str(setorial or "Direto")
        )

        for vinculo in self.clientes_adicionais:
            cliente_existente = vinculo.get("cliente")
            chave_existente = (
                str(
                    getattr(
                        cliente_existente,
                        "num_assinatura",
                        ""
                    ) or ""
                ).strip(),
                str(vinculo.get("setorial") or "Direto")
            )

            if chave_existente == chave:
                return False

        self.clientes_adicionais.append({
            "cliente": cliente,
            "setorial": setorial,
            "origem": origem or "",
            "predio": predio
        })
        cliente.adicionar_vinculo_atendimento(
            self,
            setorial=setorial,
            tipo="Adicional",
            origem=origem,
            predio=predio
        )

        return True

    def listar_vinculos_clientes(self, incluir_adicionais=True):
        vinculos = [
            {
                "cliente": cliente,
                "setorial": getattr(cliente, "setorial", None),
                "tipo": "Principal",
                "origem": getattr(cliente, "origem_estrutura", ""),
                "predio": getattr(cliente, "predio_estrutura", None)
            }
            for cliente in self.clientes
        ]

        if incluir_adicionais:
            vinculos.extend({
                **vinculo,
                "tipo": "Adicional"
            } for vinculo in self.clientes_adicionais)

        return vinculos

    def adicionar_site_setorial(self, setorial, site):

        if not setorial:

            return

        sites = self.sites_por_setorial.setdefault(
            setorial,
            []
        )

        if site not in sites:

            sites.append(site)

    def adicionar_cliente_estrutura(
        self,
        nome,
        assinatura,
        predio=None,
        setorial=None,
        tipo_vinculo="Principal"
    ):

        chave = (
            str(assinatura or "").strip(),
            str(setorial or "Direto"),
            str(tipo_vinculo or "Principal")
        )

        for vinculo in self.clientes_estrutura:
            chave_existente = (
                str(vinculo.get("assinatura") or "").strip(),
                str(vinculo.get("setorial") or "Direto"),
                str(vinculo.get("tipo_vinculo") or "Principal")
            )

            if chave_existente == chave:
                return False

        self.clientes_estrutura.append({
            "nome": nome,
            "assinatura": assinatura,
            "predio": predio,
            "setorial": setorial,
            "tipo_vinculo": tipo_vinculo
        })

        return True

    def adicionar_equipamento(self, equipamento):

        self.equipamentos.append(equipamento)

    def limpar_receita_cache(self, visitados=None):

        if visitados is None:

            visitados = set()

        if id(self) in visitados:

            return

        visitados.add(id(self))

        self.receita_cache = None

        if self.pai:

            self.pai.limpar_receita_cache(visitados)

    def calcular_receita(self):

        # Usar cache
        if self.receita_cache is not None:

            return self.receita_cache

        total = sum(
            cliente.receita
            for cliente in self.clientes
        )

        for filho in self.filhos:

            total += filho.calcular_receita()

        # Salvar cache
        self.receita_cache = total

        return total

    def exibir_arvore(self, nivel=0):

        espaco = "  " * nivel

        print(
            f"{espaco}- "
            f"{self.nome} "
            f"({self.tipo}) "
            f"Receita: "
            f"R$ {self.calcular_receita():,.2f}"
        )

        # Mostrar clientes
        for cliente in self.clientes[:10]:

            print(
                f"{espaco}    "
                f"Cliente: {cliente.nome} "
                f"- R$ {cliente.receita:,.2f}"
            )

        # Mostrar filhos
        for filho in self.filhos:

            filho.exibir_arvore(nivel + 1)
