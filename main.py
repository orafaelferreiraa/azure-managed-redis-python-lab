import argparse
import json
import time
from statistics import mean

from cache_lab import (
    create_client,
    get_product_cache_aside,
    get_product_ttl,
    invalidate_product,
    read_cached_product,
)
from fake_database import PRODUCTS_FILE, get_product, list_products, reset_database, update_product


def print_section(title: str) -> None:
    print(f"\n== {title} ==")


def print_json(label: str, payload: object) -> None:
    print(f"{label}: {json.dumps(payload, ensure_ascii=True)}")


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    border = "+-" + "-+-".join("-" * width for width in widths) + "-+"
    header_line = "| " + " | ".join(headers[i].ljust(widths[i]) for i in range(len(headers))) + " |"

    print(border)
    print(header_line)
    print(border)
    for row in rows:
        line = "| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(row))) + " |"
        print(line)
    print(border)


def run_single_loop(loop_index: int, total_loops: int) -> dict[str, float | str]:
    product_id = 123

    print_section(f"Loop {loop_index}/{total_loops} - Preparando o laboratorio")
    reset_database()
    print(f"Banco fake resetado em: {PRODUCTS_FILE}")
    print_json("Produtos no banco fake", list_products())

    client = create_client()
    try:
        print_section("Conexao com Redis")
        print("PING:", client.ping())

        print_section("Etapa 1: limpa o cache")
        removed = invalidate_product(client, product_id)
        print("Chaves removidas:", removed)

        print_section("Etapa 2: primeira leitura (SEM CACHE -> banco)")
        started_at = time.perf_counter()
        first_product, first_status = get_product_cache_aside(client, product_id, get_product)
        first_ms = (time.perf_counter() - started_at) * 1000
        print(f"Status: {first_status} (SEM CACHE / BANCO) | tempo: {first_ms:.1f} ms")
        print_json("Produto retornado (fonte: banco)", first_product)
        print_json("Valor salvo no Redis (CACHE)", read_cached_product(client, product_id))
        print("TTL atual (s):", get_product_ttl(client, product_id))

        print_section("Etapa 3: segunda leitura (COM CACHE -> Redis)")
        started_at = time.perf_counter()
        second_product, second_status = get_product_cache_aside(client, product_id, get_product)
        second_ms = (time.perf_counter() - started_at) * 1000
        print(f"Status: {second_status} (COM CACHE / REDIS) | tempo: {second_ms:.1f} ms")
        print_json("Produto retornado (fonte: Redis cache)", second_product)

        print_section("Etapa 4: atualiza o banco fake")
        updated_product = update_product(product_id, price=219.9, stock=38)
        print_json("Produto no banco apos update", updated_product)
        print_json("Cache Redis antes de invalidar", read_cached_product(client, product_id))

        print_section("Etapa 5: invalida e recarrega o cache")
        removed = invalidate_product(client, product_id)
        print("Chaves removidas:", removed)
        refreshed_product, refreshed_status = get_product_cache_aside(client, product_id, get_product)
        print(f"Status: {refreshed_status}")
        print_json("Produto retornado apos recarga (fonte: banco)", refreshed_product)
        print_json("Cache Redis apos recarga", read_cached_product(client, product_id))
        print("TTL atual (s):", get_product_ttl(client, product_id))

        reduction_pct = (1 - (second_ms / first_ms)) * 100 if first_ms > 0 else 0.0
        return {
            "loop": float(loop_index),
            "miss_ms": first_ms,
            "hit_ms": second_ms,
            "reduction_pct": reduction_pct,
            "first_status": first_status,
            "second_status": second_status,
        }

    finally:
        client.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Azure Managed Redis cache lab")
    parser.add_argument(
        "--loops",
        type=int,
        default=1,
        help="Numero de repeticoes do laboratorio para calcular media (ex.: --loops 5)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.loops < 1:
        raise ValueError("--loops precisa ser maior ou igual a 1")

    results: list[dict[str, float | str]] = []
    for loop_index in range(1, args.loops + 1):
        results.append(run_single_loop(loop_index, args.loops))

    rows: list[list[str]] = []
    for result in results:
        rows.append(
            [
                str(int(result["loop"])),
                f"{float(result['miss_ms']):.1f}",
                f"{float(result['hit_ms']):.1f}",
                f"{float(result['reduction_pct']):.1f}%",
                str(result["first_status"]),
                str(result["second_status"]),
            ]
        )

    avg_miss = mean(float(item["miss_ms"]) for item in results)
    avg_hit = mean(float(item["hit_ms"]) for item in results)
    avg_reduction = (1 - (avg_hit / avg_miss)) * 100 if avg_miss > 0 else 0.0
    speedup = (avg_miss / avg_hit) if avg_hit > 0 else 0.0

    print_section("Metricas finais")
    print_table(
        headers=["Loop", "Sem cache (ms)", "Com cache (ms)", "Reducao", "Leitura 1", "Leitura 2"],
        rows=rows,
    )
    print(f"Media miss: {avg_miss:.1f} ms")
    print(f"Media hit: {avg_hit:.1f} ms")
    print(f"Reducao media: {avg_reduction:.1f}%")
    print(f"Aceleracao media: {speedup:.1f}x")


if __name__ == "__main__":
    main()
