"""Pandas i GeoPandas — tutorial w stylu page2.py.

Plik umieść w views/page1.py. Dane odczytywane są z katalogu projektu data/.
"""
from pathlib import Path
from tempfile import TemporaryDirectory

import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from pyproj import Geod
from streamlit_folium import st_folium

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
METRIC_CRS = "EPSG:2180"
ESRI_TILES = (
    "https://server.arcgisonline.com/ArcGIS/rest/"
    "services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)

st.title("Pandas i GeoPandas — analiza danych przestrzennych")
st.write("Pomiary PM2.5, szkoły i dzielnice Opola.")

# Dane wejściowe oraz wspólne obiekty wykorzystywane w kolejnych zakładkach.
df = pd.read_csv(DATA_DIR / "pm25_sensors.csv")
for column in ["lat", "lon", "pm25"]:
    df[column] = pd.to_numeric(df[column], errors="coerce")
# Zapis tekstowy dat pozwala uniknąć niejednorodnych typów Timestamp w PyArrow.
df["measured_at"] = pd.to_datetime(
    df["measured_at"], format="mixed", errors="coerce", utc=True
).dt.strftime("%Y-%m-%d %H:%M:%S %Z").astype("string")

clean = df.drop_duplicates().dropna(subset=["lat", "lon", "pm25"]).copy()
swapped = clean["lat"].between(14, 24.5) & clean["lon"].between(49, 55)
clean.loc[swapped, ["lat", "lon"]] = clean.loc[swapped, ["lon", "lat"]].to_numpy()
clean = clean.loc[
    clean["lat"].between(49, 55)
    & clean["lon"].between(14, 24.5)
    & (clean["pm25"] >= 0)
].copy()

sensors = gpd.GeoDataFrame(
    clean,
    geometry=gpd.points_from_xy(clean["lon"], clean["lat"]),
    crs="EPSG:4326",
)
sensors_m = sensors.to_crs(METRIC_CRS)
districts = gpd.read_file(DATA_DIR / "opole_districts.geojson").to_crs(METRIC_CRS)
schools = gpd.read_file(DATA_DIR / "opole_schools.geojson").to_crs(METRIC_CRS)

# Przygotowanie wspólnych wyników dla SJOIN i eksportu.
joined = gpd.sjoin(
    sensors_m, districts[["name", "geometry"]], how="inner", predicate="within"
)
stats = joined.groupby("name", as_index=False).agg(
    pm25_mean=("pm25", "mean"), sensor_count=("pm25", "size")
)
summary = districts.merge(stats, on="name", how="left")

(tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8) = st.tabs([
    "1. Analiza CSV", "2. Czyszczenie", "3. CSV → GeoPandas",
    "4. Układy CRS", "5. Poligony", "6. Spatial Join",
    "7. Bufory", "8. Eksport wyników"
])

with tab1:
    st.header("1. Analiza danych CSV")
    st.write("Odczyt danych, statystyki opisowe, typy kolumn i kontrola jakości.")

    st.subheader("1.1 Dane źródłowe")
    st.code('df = pd.read_csv("data/pm25_sensors.csv")', language="python")
    st.dataframe(df, hide_index=True)

    st.subheader("1.2 Statystyki opisowe")
    st.code("df.describe()", language="python")
    st.dataframe(df.describe())

    st.subheader("1.3 Typy danych i brakujące wartości")
    st.code('df.dtypes\ndf.isna().sum()', language="python")
    c1, c2 = st.columns(2)
    with c1:
        st.dataframe(df.dtypes.astype(str).rename("Typ"))
    with c2:
        st.dataframe(df.isna().sum().rename("Braki"))

    st.subheader("1.4 Wiersze z brakami i duplikaty")
    st.code('df[df.isna().any(axis=1)]\ndf[df.duplicated(keep=False)]', language="python")
    st.write("**Wiersze z brakami**")
    st.dataframe(df[df.isna().any(axis=1)], hide_index=True)
    st.write("**Duplikaty**")
    st.dataframe(df[df.duplicated(keep=False)], hide_index=True)

with tab2:
    st.header("2. Czyszczenie danych")
    st.write("Usuwamy duplikaty, niekompletne i niepoprawne pomiary oraz zamienione współrzędne.")
    st.code('''clean = df.drop_duplicates().dropna(subset=["lat", "lon", "pm25"]).copy()
swapped = clean["lat"].between(14, 24.5) & clean["lon"].between(49, 55)
clean.loc[swapped, ["lat", "lon"]] = clean.loc[swapped, ["lon", "lat"]].to_numpy()
clean = clean[clean["lat"].between(49, 55) & clean["lon"].between(14, 24.5)
              & (clean["pm25"] >= 0)]''', language="python")
    c1, c2, c3 = st.columns(3)
    c1.metric("Wiersze przed", len(df))
    c2.metric("Wiersze po", len(clean))
    c3.metric("Zamienione lat/lon", int(swapped.sum()))
    st.subheader("2.1 Dane po czyszczeniu")
    st.dataframe(clean, hide_index=True)
    st.subheader("2.2 Statystyki po czyszczeniu")
    st.dataframe(clean.describe())

with tab3:
    st.header("3. Z CSV do GeoPandas")
    st.write("Tworzymy obiekty Point ze współrzędnych geograficznych czujników.")
    st.code('''sensors = gpd.GeoDataFrame(
    clean,
    geometry=gpd.points_from_xy(clean["lon"], clean["lat"]),
    crs="EPSG:4326"
)''', language="python")
    c1, c2 = st.columns(2)
    c1.metric("Punkty", len(sensors))
    c2.metric("CRS", str(sensors.crs))
    # PyArrow nie serializuje bezpośrednio kolumny GeoPandas geometry.
    st.dataframe(sensors.to_wkt(), hide_index=True)
    st.subheader("3.1 Mapa czujników")
    m = folium.Map(tiles=ESRI_TILES, attr="Tiles © Esri and its data providers")
    sensors.explore(m=m, color="orange", marker_kwds={"radius": 5},
                    tooltip=["sensor_id", "pm25"], name="Czujniki PM2.5")
    folium.LayerControl().add_to(m)
    st_folium(m, height=550, width="stretch", returned_objects=[])

with tab4:
    st.header("4. Układy współrzędnych (CRS)")
    st.write("EPSG:4326 przechowuje stopnie, a EPSG:2180 pozwala liczyć odległości w metrach.")
    st.code('''sensors_m = sensors.to_crs("EPSG:2180")
a, b = sensors.geometry.iloc[0], sensors.geometry.iloc[1]
degrees = a.distance(b)
meters = sensors_m.geometry.iloc[0].distance(sensors_m.geometry.iloc[1])''', language="python")
    a, b = sensors.geometry.iloc[0], sensors.geometry.iloc[1]
    meters = sensors_m.geometry.iloc[0].distance(sensors_m.geometry.iloc[1])
    c1, c2, c3 = st.columns(3)
    c1.metric("EPSG:4326", f"{a.distance(b):.5f}°")
    c2.metric("EPSG:2180", f"{meters:,.0f} m")
    p = sensors_m.geometry.iloc[0]
    c3.metric("Punkt w EPSG:2180", f"{p.x:,.0f}, {p.y:,.0f}")
    st.subheader("4.1 Odległość dwóch czujników")
    m = folium.Map(tiles=ESRI_TILES, attr="Tiles © Esri and its data providers")
    folium.PolyLine([[a.y, a.x], [b.y, b.x]], color="yellow", weight=4,
                    tooltip=f"{meters:.0f} m").add_to(m)
    sensors.iloc[:2].explore(m=m, color="cyan", tooltip=["sensor_id"])
    m.fit_bounds([[min(a.y, b.y), min(a.x, b.x)], [max(a.y, b.y), max(a.x, b.x)]])
    st_folium(m, height=450, width="stretch", returned_objects=[])

    st.subheader("4.2 EPSG:3857 kontra EPSG:2180")
    st.code('''points = gpd.GeoSeries.from_xy(
    [18.6466, 19.9496], [54.352, 49.2992], crs="EPSG:4326"
)
_, _, true_m = Geod(ellps="WGS84").inv(
    18.6466, 54.352, 19.9496, 49.2992
)''', language="python")
    points = gpd.GeoSeries.from_xy(
        [18.6466, 19.9496], [54.352, 49.2992], crs="EPSG:4326"
    )
    _, _, true_m = Geod(ellps="WGS84").inv(18.6466, 54.352, 19.9496, 49.2992)
    comparison = pd.DataFrame({
        "Układ": ["EPSG:4326", "EPSG:3857", "EPSG:2180", "Geodezyjna WGS84"],
        "Odległość": [points.iloc[0].distance(points.iloc[1]),
                      points.to_crs("EPSG:3857").iloc[0].distance(points.to_crs("EPSG:3857").iloc[1]),
                      points.to_crs(METRIC_CRS).iloc[0].distance(points.to_crs(METRIC_CRS).iloc[1]), true_m],
        "Jednostka": ["stopnie", "metry", "metry", "metry"]
    })
    st.dataframe(comparison, hide_index=True)
    chart = comparison[comparison["Jednostka"] == "metry"].copy()
    chart["Odległość (km)"] = chart["Odległość"] / 1000
    st.bar_chart(chart, x="Układ", y="Odległość (km)")
    st.metric("Błąd EPSG:3857", f"{(chart.iloc[0]['Odległość'] / true_m - 1)*100:+.2f}%")

with tab5:
    st.header("5. Poligony — powierzchnia dzielnic")
    st.write("Obliczamy powierzchnie poligonów w układzie metrycznym.")
    st.code('''districts["area_km2"] = districts.geometry.area / 1_000_000''', language="python")
    area_gdf = districts.copy()
    area_gdf["area_km2"] = area_gdf.geometry.area / 1_000_000
    c1, c2 = st.columns(2)
    c1.metric("Dzielnice", len(area_gdf))
    c2.metric("Suma powierzchni", f"{area_gdf['area_km2'].sum():.2f} km²")
    st.dataframe(area_gdf[["name", "area_km2"]].sort_values("area_km2", ascending=False), hide_index=True)
    st.subheader("5.1 Mapa powierzchni")
    m = folium.Map(tiles=ESRI_TILES, attr="Tiles © Esri and its data providers")
    area_gdf.explore(m=m, column="area_km2", cmap="YlOrRd", legend=True,
                     tooltip=["name", "area_km2"], name="Powierzchnia dzielnic")
    folium.LayerControl().add_to(m)
    st_folium(m, height=550, width="stretch", returned_objects=[])

with tab6:
    st.header("6. Spatial Join — czujniki i dzielnice")
    st.write("Relacja within przypisuje pomiary PM2.5 do dzielnic.")
    st.code('''joined = gpd.sjoin(sensors_m, districts[["name", "geometry"]],
                   how="inner", predicate="within")
stats = joined.groupby("name", as_index=False).agg(
    pm25_mean=("pm25", "mean"), sensor_count=("pm25", "size")
)
summary = districts.merge(stats, on="name", how="left")''', language="python")
    c1, c2 = st.columns(2)
    c1.metric("Punkty wejściowe", len(sensors_m))
    c2.metric("Dopasowania", len(joined))
    st.subheader("6.1 Połączone rekordy")
    st.dataframe(joined.to_wkt(), hide_index=True)
    st.subheader("6.2 Statystyki według dzielnic")
    st.dataframe(stats, hide_index=True)
    st.subheader("6.3 Dzielnice ze statystykami")
    st.dataframe(summary.to_wkt(), hide_index=True)
    st.subheader("6.4 Mapa średniego PM2.5")
    m = folium.Map(tiles=ESRI_TILES, attr="Tiles © Esri and its data providers")
    summary.explore(m=m, column="pm25_mean", cmap="YlOrRd", legend=True,
                    missing_kwds={"color": "lightgray", "label": "Brak pomiarów"},
                    tooltip=["name", "pm25_mean", "sensor_count"],
                    style_kwds={"fillOpacity": 0.5}, name="Dzielnice PM2.5")
    sensors_m.explore(m=m, color="cyan", marker_kwds={"radius": 5},
                      tooltip=["pm25"], name="Czujniki")
    folium.LayerControl().add_to(m)
    st_folium(m, height=550, width="stretch", returned_objects=[])

with tab7:
    st.header("7. Bufory wokół szkół")
    st.write("Wybierz promień, policz pomiary w strefach i sprawdź pokrycie dzielnic.")
    radius = st.slider("Promień bufora (m)", 100, 2000, 500, 100)
    st.code('''buffers = schools.copy()
buffers["geometry"] = schools.geometry.buffer(radius)
nearby = gpd.sjoin(sensors_m, buffers[["name", "geometry"]],
                   how="inner", predicate="within")''', language="python")
    buffers = schools.copy()
    buffers["geometry"] = schools.geometry.buffer(radius)
    nearby = gpd.sjoin(sensors_m, buffers[["name", "geometry"]],
                       how="inner", predicate="within")
    buffer_stats = nearby.groupby("name")["pm25"].agg(["mean", "size"]).reset_index()
    city = districts.geometry.union_all()
    covered = buffers.geometry.union_all().intersection(city)
    coverage = covered.area / city.area * 100 if city.area else 0
    c1, c2, c3 = st.columns(3)
    c1.metric("Promień", f"{radius} m")
    c2.metric("Pomiary w buforach", len(nearby))
    c3.metric("Pokrycie miasta", f"{coverage:.2f}%")
    st.dataframe(buffer_stats.rename(columns={"mean": "PM2.5 średnia", "size": "Liczba pomiarów"}),
                 hide_index=True)
    st.subheader("7.1 Mapa buforów")
    m = folium.Map(tiles=ESRI_TILES, attr="Tiles © Esri and its data providers")
    buffers.explore(m=m, color="orange", style_kwds={"fillOpacity": 0.25},
                    name="Bufory szkół")
    schools.explore(m=m, color="cyan", marker_kwds={"radius": 5},
                    tooltip=["name"], name="Szkoły")
    sensors_m.explore(m=m, color="red", marker_kwds={"radius": 5},
                      tooltip=["pm25"], name="Czujniki PM2.5")
    folium.LayerControl().add_to(m)
    st_folium(m, height=550, width="stretch", returned_objects=[])

with tab8:
    st.header("8. Eksport wyników")
    st.write("Pobierz wyniki jako GeoPackage, GeoJSON lub CSV.")
    st.code('''summary.to_file("pm25_opole.gpkg", layer="districts", driver="GPKG")
sensors_m.to_file("pm25_opole.gpkg", layer="sensors", driver="GPKG", mode="a")
summary.to_crs("EPSG:4326").to_file("pm25_districts.geojson", driver="GeoJSON")''', language="python")
    c1, c2, c3 = st.columns(3)
    c1.metric("Dzielnice", len(summary))
    c2.metric("Czujniki", len(sensors_m))
    c3.metric("CRS GPKG", METRIC_CRS)
    st.dataframe(summary[["name", "pm25_mean", "sensor_count"]], hide_index=True)

    # GeoPackage jest przygotowywany w katalogu tymczasowym.
    with TemporaryDirectory() as temporary_folder:
        gpkg_path = Path(temporary_folder) / "pm25_opole.gpkg"
        summary.to_file(gpkg_path, layer="districts", driver="GPKG", index=False)
        sensors_m.to_file(gpkg_path, layer="sensors", driver="GPKG", mode="a", index=False)
        gpkg_bytes = gpkg_path.read_bytes()

    geojson_bytes = summary.to_crs("EPSG:4326").to_json().encode("utf-8")
    csv_bytes = summary.drop(columns="geometry").to_csv(index=False).encode("utf-8-sig")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("Pobierz GeoPackage", gpkg_bytes, "pm25_opole.gpkg",
                           mime="application/geopackage+sqlite3", use_container_width=True)
    with c2:
        st.download_button("Pobierz GeoJSON", geojson_bytes, "pm25_districts.geojson",
                           mime="application/geo+json", use_container_width=True)
    with c3:
        st.download_button("Pobierz CSV", csv_bytes, "pm25_districts.csv",
                           mime="text/csv", use_container_width=True)
    st.info("GeoPackage zawiera dwie warstwy w EPSG:2180; GeoJSON jest w EPSG:4326.")
