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
