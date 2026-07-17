#!/usr/bin/env python3
import argparse

from app.services.feasibility_history import load_records
from app.services.feasibility_opportunities import STATUS_ERROR
from app.services.feasibility_opportunities import STATUS_NOT_FOUND
from app.services.feasibility_opportunities import geocoding_coverage
from app.services.feasibility_opportunities import load_geocoding
from app.services.feasibility_opportunities import process_geocoding_batch
from app.services.feasibility_opportunities import reset_geocoding_statuses
from app.services.feasibility_opportunities import synchronize_addresses


def main():
    parser = argparse.ArgumentParser(
        description="Geocodifica o histórico de viabilidades em lotes retomáveis."
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--all", action="store_true", help="Processa todos os pendentes.")
    parser.add_argument("--retry-not-found", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    args = parser.parse_args()

    records = load_records()
    synchronize_addresses(records)
    retries = set()
    if args.retry_not_found:
        retries.add(STATUS_NOT_FOUND)
    if args.retry_errors:
        retries.add(STATUS_ERROR)
    if args.all and retries:
        reset_geocoding_statuses(retries)
        retries.clear()

    while True:
        coverage = geocoding_coverage(records, load_geocoding())
        print(
            f"Cobertura {coverage['Cobertura %']:.1f}% | "
            f"localizados={coverage['Localizado']} pendentes={coverage['Pendente']} "
            f"não_localizados={coverage['Não localizado']} erros={coverage['Erro']}",
            flush=True,
        )
        has_pending = coverage["Pendente"] > 0
        has_retry = (
            args.retry_not_found and coverage["Não localizado"] > 0
        ) or (args.retry_errors and coverage["Erro"] > 0)
        if not has_pending and not has_retry:
            break
        result = process_geocoding_batch(
            records,
            limit=max(1, args.batch_size),
            retry_statuses=retries,
        )
        print(result, flush=True)
        if not args.all or result["Processados"] == 0:
            break


if __name__ == "__main__":
    main()
