from warehouse.db import get_connection


def insert_city(city):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO dim_city(city_name,country,latitude,longitude)
        VALUES (%s,%s,%s,%s)
        ON CONFLICT(city_name)
        DO NOTHING
    """, (
        city["ville"],
        city["pays"],
        city["lat"],
        city["lon"]
    ))

    conn.commit()
    cur.close()
    conn.close()