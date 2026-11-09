import pandas as pd


def main():
    # Create a simple DataFrame (The "Hello World" of data)
    data = {"Greeting": ["Hello", "Hi", "Hey"], "Target": ["World", "Pandas", "Pip"]}
    df = pd.DataFrame(data)

    print("--- Pandas Hello World ---")
    print(df)
    print("\nDataFrame Summary:")
    print(df.info())


if __name__ == "__main__":
    main()
