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
