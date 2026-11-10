import labunits

READINGS_CELSIUS = (21.2, 23.8, 22.5, 24.1, 23.9)


def main() -> None:
    kelvin = [labunits.celsius_to_kelvin(reading) for reading in READINGS_CELSIUS]
    print(f"mean: {sum(kelvin) / len(kelvin):.2f} K")


if __name__ == "__main__":
    main()
