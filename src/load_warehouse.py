import json
import os

from warehouse.models import insert_city

RAW_DIR = "raw"


def main():

    files = [f for f in os.listdir(RAW_DIR)
             if f.endswith(".json")]

    print(f"{len(files)} fichiers trouvés")

    for file in files:

        path = os.path.join(RAW_DIR, file)

        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        city = {
            "ville": data["_meta"]["ville"],
            "pays": data["_meta"]["pays"],
            "lat": data["_meta"]["lat"],
            "lon": data["_meta"]["lon"]
        }

        insert_city(city)

        print("Ville ajoutée :", city["ville"])


if __name__ == "__main__":
    main()