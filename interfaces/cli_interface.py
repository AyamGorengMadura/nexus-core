import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from core.router import route


def main():
    print("Nexus/Dozor — CLI Interface (Demo / Debug)")
    print("Ketik 'exit' untuk keluar.\n")

    while True:
        try:
            user_input = input("You > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break

        if user_input.lower() in ("exit", "quit"):
            print("Bye.")
            break
        if not user_input:
            continue

        response = route(user_input)
        text = response.get("text", "") if isinstance(response, dict) else response
        expression = response.get("expression", "-") if isinstance(response, dict) else "-"
        print(f"Nexus > {text}")
        print(f"       [expression={expression} motion={response.get('motion') if isinstance(response, dict) else None}]\n")


if __name__ == "__main__":
    main()
