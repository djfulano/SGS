from datetime import datetime

from app.config import HISTORY_FILE
from app.storage import read_json
from app.storage import write_json_atomic


def hoje():

    return datetime.now().strftime("%Y-%m-%d")


def load_history():
    return read_json(
        HISTORY_FILE,
        {
            "active_sites": {},
            "active_clients": {},
            "removed_sites": {},
            "cancelled_clients": {},
            "last_import": None
        }
    )


def save_history(history):
    write_json_atomic(
        HISTORY_FILE,
        history
    )


def cliente_info(cliente, site):

    return {
        "Cliente": cliente.nome,
        "Assinatura": cliente.num_assinatura,
        "Gerente de Contas": getattr(cliente, "gerente_contas", ""),
        "Receita": cliente.receita,
        "Produto": getattr(cliente, "produto", ""),
        "Site": site.nome,
        "Setorial": getattr(cliente, "setorial", None) or "Direto",
        "Predio": getattr(cliente, "predio_estrutura", None) or "",
        "Endereco": getattr(cliente, "endereco_completo", ""),
        "Bairro": getattr(cliente, "bairro", ""),
        "Cidade": getattr(cliente, "cidade", "")
    }


def sites_descendentes(site):

    sites = [site]

    for filho in site.filhos:

        sites.extend(
            sites_descendentes(filho)
        )

    return sites


def clientes_site_com_filhos(site):

    clientes = []

    for site_atual in sites_descendentes(site):

        for cliente in site_atual.clientes:

            clientes.append(
                cliente_info(
                    cliente,
                    site_atual
                )
            )

    return clientes


def build_snapshot(sites, active_clients_base=None):

    active_sites = {}
    active_clients = dict(
        active_clients_base or {}
    )

    for site in sites.values():

        active_sites[site.nome] = {
            "Site": site.nome,
            "Tipo": site.tipo,
            "Predio": getattr(site, "predio", "") or "",
            "Pai": site.pai.nome if site.pai else "",
            "Clientes": clientes_site_com_filhos(site)
        }

        for cliente in site.clientes:

            info = active_clients.get(
                cliente.num_assinatura,
                {}
            )
            info.update(
                cliente_info(
                    cliente,
                    site
                )
            )
            active_clients[cliente.num_assinatura] = info

    return {
        "active_sites": active_sites,
        "active_clients": active_clients
    }


def predio_site(site_data):

    return str(
        site_data.get("Predio") or ""
    ).strip()


def indexar_sites_por_predio(sites_data):

    indice = {}

    for site_name, site_data in sites_data.items():

        predio = predio_site(site_data)

        if not predio:

            continue

        indice.setdefault(
            predio,
            set()
        ).add(site_name)

    return indice


def site_renomeado_por_predio(site_name, site_data, new_sites_by_predio):

    predio = predio_site(site_data)

    if not predio:

        return False

    sites_mesmo_predio = new_sites_by_predio.get(
        predio,
        set()
    )

    return bool(
        sites_mesmo_predio
        and site_name not in sites_mesmo_predio
    )


def ensure_history_initialized(sites, active_clients_base=None):

    history = load_history()

    active_clients_base = active_clients_base or {}

    if not history.get("active_clients") and active_clients_base:

        history["cancelled_clients"] = {}
        history.pop(
            "legacy_cancelled_clients",
            None
        )

    if history.get("active_sites") and history.get("active_clients"):

        return history

    snapshot = build_snapshot(
        sites,
        active_clients_base=active_clients_base
    )

    if not history.get("active_sites"):

        history["active_sites"] = snapshot["active_sites"]

    if not history.get("active_clients"):

        history["active_clients"] = snapshot["active_clients"]

    if not history.get("last_import"):

        history["last_import"] = hoje()

    save_history(history)

    return history


def update_history(sites, import_date=None, active_clients_base=None):

    if import_date is None:

        import_date = hoje()

    history = load_history()
    snapshot = build_snapshot(
        sites,
        active_clients_base=active_clients_base
    )

    old_sites = history.get("active_sites", {})
    old_clients = history.get("active_clients", {})
    new_sites = snapshot["active_sites"]
    new_clients = snapshot["active_clients"]
    new_sites_by_predio = indexar_sites_por_predio(
        new_sites
    )

    removed_sites = history.setdefault(
        "removed_sites",
        {}
    )

    for site_name, site_data in old_sites.items():

        if site_name in new_sites:

            continue

        if site_renomeado_por_predio(
            site_name,
            site_data,
            new_sites_by_predio
        ):

            continue

        site_data = dict(site_data)
        site_data["Data Remocao"] = removed_sites.get(
            site_name,
            {}
        ).get(
            "Data Remocao",
            import_date
        )
        removed_sites[site_name] = site_data

    for site_name in list(removed_sites.keys()):

        site_data = removed_sites.get(
            site_name,
            {}
        )

        if site_name in new_sites or site_renomeado_por_predio(
            site_name,
            site_data,
            new_sites_by_predio
        ):

            removed_sites.pop(site_name, None)

    cancelled_clients = history.setdefault(
        "cancelled_clients",
        {}
    )

    for assinatura, client_data in old_clients.items():

        if assinatura in new_clients:

            continue

        client_data = dict(client_data)
        client_data["Data Cancelamento"] = cancelled_clients.get(
            assinatura,
            {}
        ).get(
            "Data Cancelamento",
            import_date
        )
        cancelled_clients[assinatura] = client_data

    for assinatura in list(cancelled_clients.keys()):

        if assinatura in new_clients:

            cancelled_clients.pop(assinatura, None)

    history["active_sites"] = new_sites
    history["active_clients"] = new_clients
    history["last_import"] = import_date

    save_history(history)

    return history
