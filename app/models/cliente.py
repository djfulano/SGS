class Cliente:

    def __init__(
        self,
        nome,
        receita,
        num_assinatura,
        setorial=None
    ):

        self.nome = nome

        self.receita = float(receita)

        self.num_assinatura = str(num_assinatura)

        self.setorial = setorial

        self.cep = ""

        self.endereco_completo = ""

        self.complemento = ""

        self.bairro = ""

        self.cidade = ""

        self.produto = ""

        self.gerente_contas = ""

        self.latitude = 0.0

        self.longitude = 0.0

        self.altitude = 0.0

        self.altura = 0.0

        self.vinculos_atendimento = []

    def adicionar_vinculo_atendimento(
        self,
        site,
        setorial=None,
        tipo="Principal",
        origem="",
        predio=None
    ):
        chave = (
            getattr(site, "nome", ""),
            str(setorial or "Direto"),
            str(tipo or "Principal")
        )

        for vinculo in self.vinculos_atendimento:
            chave_existente = (
                getattr(vinculo.get("site"), "nome", ""),
                str(vinculo.get("setorial") or "Direto"),
                str(vinculo.get("tipo") or "Principal")
            )

            if chave_existente == chave:
                return False

        self.vinculos_atendimento.append({
            "site": site,
            "setorial": setorial,
            "tipo": tipo,
            "origem": origem or "",
            "predio": predio
        })

        return True
