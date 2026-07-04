import argparse

from app.scripts.demo_seed import reset_demo_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete synthetic demo data")
    parser.add_argument(
        "--slug",
        metavar="WIDGET_SLUG",
        help="Limit deletion to a single practice by widget slug (e.g. aster-demo)",
    )
    args = parser.parse_args()

    summary = reset_demo_dataset(slug=args.slug)
    label = f"slug={args.slug}" if args.slug else "all demo practices"
    print(f"Removed synthetic demo data ({label}):")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
