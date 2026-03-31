from app.scripts.demo_seed import reset_demo_dataset


def main() -> None:
    summary = reset_demo_dataset()
    print("Removed synthetic demo data:")
    for key, value in summary.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
