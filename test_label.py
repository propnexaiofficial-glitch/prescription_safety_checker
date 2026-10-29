from label import get_label


def main():
    label = get_label("acetaminophen")
    if label is None:
        print("No label found (network or API problem).")
        return

    print(label["source"])
    for field, text in label["excerpts"].items():
        print("-", field, ":", text[:150])


if __name__ == "__main__":
    main()