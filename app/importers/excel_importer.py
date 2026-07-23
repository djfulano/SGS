import pandas as pd

from app.logs import registrar_log_sistema
from app.models.cliente import Cliente


def normalizar_assinatura(valor):

    if pd.isna(valor):

        return None

    if isinstance(valor, float) and valor.is_integer():

        return str(int(valor))

    assinatura = str(valor).strip()

    if assinatura.endswith(".0"):

        assinatura = assinatura[:-2]

    assinatura = "".join(
        caractere
        for caractere in assinatura
        if caractere.isdigit()
    )

    return assinatura or None


def valor_texto(linha, coluna):

    valor = linha.get(coluna, "")

    if pd.isna(valor):

        return ""

    texto = str(valor).strip()

    if texto.lower() == "nan":

        return ""

    return texto


def valor_primeira_coluna(linha, colunas):

    for coluna in colunas:

        if coluna in linha.index:

            valor = valor_texto(
                linha,
                coluna
            )

            if valor:

                return valor

    return ""


def ler_clientes_base(caminho_arquivo):

    df = pd.read_excel(
        caminho_arquivo,
        header=7
    )

    colunas_obrigatorias = {
        "NOME CLIENTE",
        "MENSALIDADE",
        "NUM ASSINATURA"
    }

    colunas_faltando = colunas_obrigatorias - set(df.columns)

    if colunas_faltando:

        raise ValueError(
            "Colunas obrigatorias ausentes: "
            f"{', '.join(sorted(colunas_faltando))}"
        )

    clientes_base = {}

    for indice, linha in df.iterrows():

        try:

            nome = str(
                linha["NOME CLIENTE"]
            ).strip()

            receita = linha["MENSALIDADE"]

            num_assinatura = normalizar_assinatura(
                linha["NUM ASSINATURA"]
            )

            if nome == "nan" or not num_assinatura:
                continue

            cep = valor_texto(
                linha,
                "CEP"
            ).replace(".0", "")

            if cep and cep.isdigit():

                cep = cep.zfill(8)

            clientes_base[num_assinatura] = {
                "Cliente": nome,
                "Assinatura": num_assinatura,
                "Receita": receita,
                "Produto": valor_texto(
                    linha,
                    "PRODUTO"
                ),
                "Gerente Contas": valor_primeira_coluna(
                    linha,
                    [
                        "Gerente Contas",
                        "GERENTE CONTAS"
                    ]
                ),
                "CEP": cep,
                "Endereco": valor_texto(
                    linha,
                    "ENDERECO COMPLETO"
                ),
                "Complemento": valor_texto(
                    linha,
                    "COMPL"
                ),
                "Bairro": valor_texto(
                    linha,
                    "BAIRRO"
                ),
                "Cidade": valor_texto(
                    linha,
                    "CIDADE"
                )
            }

        except Exception as erro:

            registrar_log_sistema(
                "ler_cliente_base",
                status="erro",
                detalhes={
                    "linha": int(indice) + 1,
                    "erro": str(erro)
                }
            )

    return clientes_base


def assinaturas_snmpc_sem_cliente(assinaturas, assinaturas_base_clientes):

    registros = []

    for num_assinatura, vinculo in assinaturas.items():

        if num_assinatura in assinaturas_base_clientes:

            continue

        if isinstance(vinculo, dict):

            site = vinculo["site"]
            setorial = vinculo.get("setorial")
            origem = vinculo.get("origem")
            predio = vinculo.get("predio")

        else:

            site = vinculo
            setorial = None
            origem = None
            predio = None

        registros.append(
            {
                "Cliente": origem or "",
                "Assinatura": num_assinatura,
                "Site": site.nome,
                "Setorial": setorial or "Direto",
                "Predio": predio or ""
            }
        )

    return registros


def importar_clientes(
    caminho_arquivo,
    assinaturas,
    retornar_cancelados=False
):

    clientes_base = ler_clientes_base(
        caminho_arquivo
    )

    clientes_importados = 0

    clientes_sem_site = []

    for num_assinatura, cliente_data in clientes_base.items():

        try:

            cliente = Cliente(
                cliente_data["Cliente"],
                cliente_data["Receita"],
                num_assinatura
            )

            cliente.cep = cliente_data.get("CEP", "")
            cliente.endereco_completo = cliente_data.get("Endereco", "")
            cliente.complemento = cliente_data.get("Complemento", "")
            cliente.bairro = cliente_data.get("Bairro", "")
            cliente.cidade = cliente_data.get("Cidade", "")
            cliente.produto = cliente_data.get("Produto", "")
            cliente.gerente_contas = cliente_data.get("Gerente Contas", "")

            # Procurar assinatura
            if num_assinatura in assinaturas:

                vinculo = assinaturas[num_assinatura]

                if isinstance(vinculo, dict):
                    vinculos = vinculo.get("vinculos") or [vinculo]

                else:
                    vinculos = [{
                        "site": vinculo,
                        "setorial": None,
                        "tipo": "Principal"
                    }]

                vinculo_principal = next(
                    (
                        item
                        for item in vinculos
                        if item.get("tipo") == "Principal"
                    ),
                    vinculos[0]
                )
                site_principal = vinculo_principal["site"]
                setorial_principal = vinculo_principal.get("setorial")
                cliente.predio_estrutura = vinculo_principal.get("predio")
                cliente.origem_estrutura = vinculo_principal.get("origem")
                site_principal.adicionar_cliente(
                    cliente,
                    setorial=setorial_principal
                )

                for vinculo_adicional in vinculos:
                    if vinculo_adicional is vinculo_principal:
                        continue

                    vinculo_adicional["site"].adicionar_cliente_adicional(
                        cliente,
                        setorial=vinculo_adicional.get("setorial"),
                        origem=vinculo_adicional.get("origem") or "",
                        predio=vinculo_adicional.get("predio")
                    )

                clientes_importados += 1

            else:

                clientes_sem_site.append(
                    {
                        "Cliente": cliente.nome,
                        "Assinatura": num_assinatura,
                        "Gerente de Contas": cliente.gerente_contas,
                        "Produto": cliente.produto,
                        "Mensalidade": cliente.receita
                    }
                )

        except Exception as erro:

            registrar_log_sistema(
                "importar_cliente",
                status="erro",
                detalhes={
                    "assinatura": num_assinatura,
                    "erro": str(erro)
                }
            )

    ausentes_base = assinaturas_snmpc_sem_cliente(
        assinaturas,
        set(clientes_base.keys())
    )

    registrar_log_sistema(
        "importar_clientes_resumo",
        status="sucesso",
        detalhes={
            "clientes_importados": clientes_importados,
            "clientes_sem_site": len(clientes_sem_site),
            "assinaturas_snmpc_sem_cliente": len(ausentes_base)
        }
    )

    if retornar_cancelados:

        return clientes_sem_site, [], ausentes_base

    return clientes_sem_site
