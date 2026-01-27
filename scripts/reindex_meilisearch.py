#!/usr/bin/env python3
import init_data


def main():
    ok = init_data.init_meilisearch()
    if not ok:
        raise SystemExit("Meilisearch indexing failed")


if __name__ == "__main__":
    main()

