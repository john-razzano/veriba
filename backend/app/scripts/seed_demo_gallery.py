from __future__ import annotations

import argparse

from app.scripts.demo_seed import seed_demo_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed polished demo gallery data for local development.")
    parser.add_argument(
        "--reset-first",
        action="store_true",
        help="Delete existing synthetic demo and smoke-test data before seeding.",
    )
    args = parser.parse_args()

    summary = seed_demo_dataset(reset_first=args.reset_first)
    print("Seeded demo gallery data:")
    print(f"- practices: {summary['practices']}")
    print(f"- sessions: {summary['sessions']}")
    print(f"- credits: {summary['credits']}")
    print(f"- shared password: {summary['demo_password']}")
    print("- accounts:")
    for item in summary["accounts"]:
        print(f"  - {item['practice']}: {item['email']} ({item['slug']})")


if __name__ == "__main__":
    main()
