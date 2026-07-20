CREATE TABLE IF NOT EXISTS dim_city (
    city_id SERIAL PRIMARY KEY,
    city_name VARCHAR(100) UNIQUE,
    country VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS dim_time (
    time_id SERIAL PRIMARY KEY,
    timestamp_hour TIMESTAMP UNIQUE,
    date_value DATE,
    year INTEGER,
    month INTEGER,
    day INTEGER,
    hour INTEGER,
    day_of_week VARCHAR(20),
    is_weekend BOOLEAN
);

CREATE TABLE IF NOT EXISTS fact_air_quality (
    fact_id SERIAL PRIMARY KEY,

    city_id INTEGER REFERENCES dim_city(city_id),
    time_id INTEGER REFERENCES dim_time(time_id),

    aqi INTEGER,

    co DOUBLE PRECISION,
    no DOUBLE PRECISION,
    no2 DOUBLE PRECISION,
    o3 DOUBLE PRECISION,
    so2 DOUBLE PRECISION,
    pm2_5 DOUBLE PRECISION,
    pm10 DOUBLE PRECISION,
    nh3 DOUBLE PRECISION
);

ALTER TABLE fact_air_quality
ADD CONSTRAINT uq_fact UNIQUE(city_id,time_id);