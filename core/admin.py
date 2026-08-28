from core.contextual_module import list_all_persons, set_trust_tier, delete_person, bulk_delete_unknown

VALID_TIERS = {"owner", "family", "guest", "unknown", "blocked"}


def main():
    print("=== Nexus Admin Tool — Kelola Trust Tier ===")
    while True:
        print("\n1. Lihat semua orang")
        print("2. Set trust tier")
        print("3. Hapus orang (by ID)")
        print("4. Bulk hapus semua 'unknown'")
        print("5. Keluar")
        choice = input("Pilih: ").strip()

        if choice == "1":
            people = list_all_persons()
            if not people:
                print("  (belum ada siapa-siapa di database)")
            for p in people:
                print(f"  [{p['id']}] {p['name']:10} | tier: {p['trust_tier']:8} | embedding: {p['embedding_id']}")

        elif choice == "2":
            try:
                pid = int(input("ID orang (lihat dari menu 1): "))
            except ValueError:
                print("ID harus angka.")
                continue

            tier = input(f"Trust tier baru ({'/'.join(VALID_TIERS)}): ").strip().lower()
            if tier not in VALID_TIERS:
                print(f"Tier tidak valid. Pilih dari: {', '.join(VALID_TIERS)}")
                continue

            try:
                result = set_trust_tier(pid, tier, requested_by="owner")
                print(f"✅ Updated: {result['name']} sekarang tier '{result['trust_tier']}'")
            except Exception as e:
                print(f"❌ Gagal: {e}")

        elif choice == "3":
            try:
                pid = int(input("ID orang yang mau dihapus: "))
            except ValueError:
                print("ID harus angka.")
                continue

            confirm = input(f"Yakin mau hapus ID {pid}? Ini permanen. (y/n): ").strip().lower()
            if confirm != "y":
                print("Dibatalkan.")
                continue

            try:
                result = delete_person(pid, requested_by="owner")
                if result:
                    print(f"✅ Terhapus: {result['name']} (ID {pid})")
                else:
                    print(f"❌ ID {pid} tidak ditemukan.")
            except Exception as e:
                print(f"❌ Gagal: {e}")

        elif choice == "4":
            confirm = input("Yakin mau hapus SEMUA orang dengan tier 'unknown'? Permanen. (y/n): ").strip().lower()
            if confirm != "y":
                print("Dibatalkan.")
                continue

            try:
                count = bulk_delete_unknown(requested_by="owner")
                print(f"✅ {count} record 'unknown' terhapus.")
            except Exception as e:
                print(f"❌ Gagal: {e}")

        elif choice == "5":
            print("Bye.")
            break

        else:
            print("Pilihan tidak dikenali.")


if __name__ == "__main__":
    main()