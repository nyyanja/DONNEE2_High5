from warehouse.db import get_connection


def insert_city(city):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO dim_city(
            city_name,
            country,
            latitude,
            longitude
        )
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



def get_city_id(city_name):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT city_id
        FROM dim_city
        WHERE city_name=%s
    """, (
        city_name,
    ))

    result = cur.fetchone()

    cur.close()
    conn.close()

    return result[0]



def insert_time(time):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO dim_time(
            timestamp_hour,
            date_value,
            year,
            month,
            day,
            hour,
            day_of_week,
            is_weekend
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)

        ON CONFLICT(timestamp_hour)
        DO NOTHING

        RETURNING time_id
    """, (
        time["timestamp"],
        time["date"],
        time["year"],
        time["month"],
        time["day"],
        time["hour"],
        time["day_of_week"],
        time["is_weekend"]
    ))


    result = cur.fetchone()


    if result:

        time_id = result[0]

    else:

        cur.execute("""
            SELECT time_id
            FROM dim_time
            WHERE timestamp_hour=%s
        """, (
            time["timestamp"],
        ))

        time_id = cur.fetchone()[0]


    conn.commit()

    cur.close()
    conn.close()

    return time_id



def insert_fact(fact):

    conn = get_connection()
    cur = conn.cursor()


    cur.execute("""
        INSERT INTO fact_air_quality(
            city_id,
            time_id,
            aqi,
            co,
            no,
            no2,
            o3,
            so2,
            pm2_5,
            pm10,
            nh3
        )

        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)

        ON CONFLICT(city_id,time_id)
        DO NOTHING

    """, (
        fact["city_id"],
        fact["time_id"],
        fact["aqi"],
        fact["co"],
        fact["no"],
        fact["no2"],
        fact["o3"],
        fact["so2"],
        fact["pm2_5"],
        fact["pm10"],
        fact["nh3"]
    ))


    conn.commit()

    cur.close()
    conn.close()