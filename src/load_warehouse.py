import csv
from datetime import datetime

from warehouse.models import (
    insert_city,
    get_city_id,
    insert_time,
    insert_fact
)


CSV_FILE = "clean/air_quality_clean.csv"


def main():

    with open(CSV_FILE, encoding="utf-8") as file:

        reader = csv.DictReader(file)

        rows = list(reader)

        print(f"{len(rows)} lignes trouvées")


        for row in rows:

            city = {
                "ville": row["ville"],
                "pays": row["pays"],
                "lat": float(row["latitude"]),
                "lon": float(row["longitude"])
            }

            insert_city(city)

            city_id = get_city_id(row["ville"])


            timestamp = datetime.strptime(
                row["timestamp_utc"],
                "%Y-%m-%dT%H:%M:%SZ"
            )


            time = {
                "timestamp": timestamp,
                "date": row["date"],
                "year": timestamp.year,
                "month": timestamp.month,
                "day": timestamp.day,
                "hour": int(row["heure"]),
                "day_of_week": row["jour_semaine"],
                "is_weekend": row["is_weekend"] == "True"
            }


            time_id = insert_time(time)


            fact = {
                "city_id": city_id,
                "time_id": time_id,
                "aqi": int(row["aqi"]),
                "co": float(row["co"]),
                "no": float(row["no"]),
                "no2": float(row["no2"]),
                "o3": float(row["o3"]),
                "so2": float(row["so2"]),
                "pm2_5": float(row["pm2_5"]),
                "pm10": float(row["pm10"]),
                "nh3": float(row["nh3"])
            }


            insert_fact(fact)


            print(
                "Chargé :",
                row["ville"],
                row["timestamp_utc"]
            )


if __name__ == "__main__":
    main()