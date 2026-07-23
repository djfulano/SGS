from pathlib import Path

from app.config import CLIENTES_FILE
from app.importers.excel_importer import importar_clientes
from app.importers.structure_importer import importar_estrutura_atual
from app.importers.structure_importer import caminho_estrutura_txt
from app.importers.structure_importer import versao_estrutura_txt
from app.importers.topos_importer import carregar_topos
from app.importers.topos_importer import caminho_sites_excel
from app.importers.topos_importer import indices_topos
from app.importers.topos_importer import localizar_topo_site
from app.services.database_service import sincronizar_banco


def arquivos_dados_obrigatorios():
    return [
        {
            "chave": "snmpc",
            "nome": "SNMPc TXT",
            "caminho": Path(caminho_estrutura_txt())
        },
        {
            "chave": "sites",
            "nome": "Sites Excel",
            "caminho": Path(caminho_sites_excel())
        },
        {
            "chave": "clientes",
            "nome": "Clientes Excel",
            "caminho": Path(CLIENTES_FILE)
        }
    ]


def status_inicializacao_dados():
    status = []

    for item in arquivos_dados_obrigatorios():
        caminho = item["caminho"]
        existe = caminho.exists()
        status.append({
            **item,
            "caminho": str(caminho),
            "existe": existe,
            "status": "OK" if existe else "Ausente"
        })

    return status


def sistema_precisa_inicializacao():
    return any(
        not item["existe"]
        for item in status_inicializacao_dados()
    )


def versao_topos():
    caminho = caminho_sites_excel()

    if not caminho.exists():
        return "sites:ausente"

    stat = caminho.stat()

    return f"{caminho.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def versao_clientes():
    caminho = Path(CLIENTES_FILE)

    if not caminho.exists():
        return "clientes:ausente"

    stat = caminho.stat()

    return f"{caminho.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"


def versao_cache_dados():
    return f"{versao_estrutura_txt()}|{versao_topos()}|{versao_clientes()}"


def aplicar_cadastro_topos(sites, df_topos):
    por_snmpc, por_codigo = indices_topos(df_topos)

    for site in sites.values():
        topo = localizar_topo_site(
            site.nome,
            por_snmpc,
            por_codigo
        )

        site.cadastro_topos = topo or {}

        if topo:
            tipo_cadastro = topo.get("Tipo Cadastro") or ""

            if tipo_cadastro:
                site.tipo = tipo_cadastro

            site.codigo_topos = topo.get("Codigo") or ""
            site.microsiga = topo.get("Microsiga") or ""
            site.codigo_condominio = topo.get("Codigo Condominio") or ""
            site.abreviacao = topo.get("Abreviacao") or ""
            site.custo = float(topo.get("Custo") or 0)
            site.status_cadastro = topo.get("Status Cadastro") or ""
            site.nome_cadastro = topo.get("Nome Cadastro") or ""
            site.relacionamento = topo.get("Relacionamento") or ""
            site.favorecido = topo.get("Favorecido") or ""
            site.contrato = topo.get("Contrato") or ""
            site.categoria = topo.get("Categoria") or ""
            site.perfil = topo.get("Perfil") or ""
            site.endereco = topo.get("Endereco") or ""
            site.numero = topo.get("Numero") or ""
            site.bairro = topo.get("Bairro") or ""
            site.cidade = topo.get("Cidade") or ""
            site.uf = topo.get("UF") or ""
            site.cep = topo.get("CEP") or ""
            site.latitude = float(topo.get("Latitude") or 0)
            site.longitude = float(topo.get("Longitude") or 0)
            site.altura = float(topo.get("Altura") or 0)
            site.restricao = topo.get("Restricao") or ""
            site.site_critico = str(
                topo.get("Site Critico") or ""
            ).strip().casefold() in {"sim", "s", "true", "1"}
            site.dia_vencimento = int(topo.get("Dia Vencimento") or 0)
            site.detalhe = topo.get("Detalhe") or ""
            site.observacao = topo.get("Observacao") or ""

        else:
            site.codigo_topos = ""
            site.microsiga = ""
            site.codigo_condominio = ""
            site.abreviacao = ""
            site.custo = 0.0
            site.status_cadastro = ""
            site.nome_cadastro = ""
            site.relacionamento = ""
            site.favorecido = ""
            site.contrato = ""
            site.categoria = ""
            site.perfil = ""
            site.endereco = ""
            site.numero = ""
            site.bairro = ""
            site.cidade = ""
            site.uf = ""
            site.cep = ""
            site.latitude = 0.0
            site.longitude = 0.0
            site.altura = 0.0
            site.restricao = ""
            site.site_critico = False
            site.dia_vencimento = 0
            site.detalhe = ""
            site.observacao = ""

    return sites


def carregar_dados_dashboard():
    sites, assinaturas, equipamentos, enlaces_sites = importar_estrutura_atual(
        retornar_enlaces=True
    )
    df_topos = carregar_topos()
    aplicar_cadastro_topos(
        sites,
        df_topos
    )

    clientes_sem_site, clientes_cancelados, clientes_snmpc_cancelados = importar_clientes(
        CLIENTES_FILE,
        assinaturas,
        retornar_cancelados=True
    )

    sincronizar_banco(sites)

    return {
        "sites": sites,
        "clientes_sem_site": clientes_sem_site,
        "clientes_cancelados": clientes_cancelados,
        "clientes_snmpc_cancelados": clientes_snmpc_cancelados,
        "equipamentos": equipamentos,
        "enlaces_sites": enlaces_sites,
        "totais": {
            "sites": len(sites),
            "sites_cadastro": len(df_topos),
            "assinaturas": len(assinaturas),
            "equipamentos": len(equipamentos),
            "enlaces_sites": len(enlaces_sites),
            "clientes_sem_site": len(clientes_sem_site),
            "clientes_cancelados": len(clientes_cancelados),
            "clientes_snmpc_cancelados": len(clientes_snmpc_cancelados)
        }
    }
