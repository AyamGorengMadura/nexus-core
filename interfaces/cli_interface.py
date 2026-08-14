import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from core.router import route



def main():
    print("Nexus/Dozor — CLI Interface (Demo)")
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
        print(f"Nexus > {response}\n")

if __name__ == "__main__":
    main()

