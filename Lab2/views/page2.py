import streamlit as st
import rasterio
import pandas as pd
import geopandas as gpd

from pathlib import Path

import numpy as np
import folium

import rasterio.mask
from rasterio.windows import Window
from rasterio.warp import transform as transform_coordinates
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm
from matplotlib.patches import Patch
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.cm import ScalarMappable
from shapely.geometry import box

from rasterio.warp import (
    calculate_default_transform,
    reproject,
    Resampling
)

from rasterio.io import MemoryFile
from rasterio.transform import array_bounds
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

st.title("Rasterio — dane rastrowe i NDVI")
st.write("Analiza danych Sentinel-2 L2A z 6 października 2026 r.")

# Ścieżka do danych
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "sentinel"
raster_path_b04 = DATA_DIR / "B04.tiff"
raster_path_b08 = DATA_DIR / "B08.tiff"

tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "0. Informacje Raster i GeoTIFF",
    "1. Metadane",
    "2. Piksel i współrzędne",
    "3. Odczyt pasm",
    "4. Wspólna siatka",
    "5. NDVI",
    "6. Klasyfikacja",
    "7. Statystyki strefowe"
])

with tab0:
    st.header("0. Informacje Raster i GeoTIFF")

with tab1:
    st.header("1. Otwarcie pliku i metadane")

    st.write(
        "Rasterio pozwala otwierać pliki rastrowe, "
        "odczytywać informacje o ich strukturze, "
        "rozdzielczości i układzie współrzędnych."
    )

    st.subheader("1.1 Otwarcie rastra")

    st.code("""
with rasterio.open(raster_path) as src:
    print(src.profile)
""", language="python")

    with rasterio.open(raster_path_b04) as src_b04,\
            rasterio.open(raster_path_b08) as src_b08:

        st.subheader("1.2 Podstawowe metadane")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Szerokość (px)", src_b04.width)

        with col2:
            st.metric("Wysokość (px)", src_b04.height)

        with col3:
            st.metric("Liczba pasm", src_b04.count)

        st.subheader("1.3 Informacje o rastrze")

        st.code("""
src.crs
src.res
src.bounds
src.dtypes
src.nodata
src.transform
""", language="python")

        metadata = {
            "Parametr": [
                "Szerokość (px)",
                "Wysokość (px)",
                "Liczba pasm",
                "CRS",
                "Rozdzielczość",
                "Granice rastra",
                "Typ danych",
                "NoData",
                "Transformacja"
            ],
            "B04 (Red)": [
                src_b04.width,
                src_b04.height,
                src_b04.count,
                str(src_b04.crs),
                str(src_b04.res),
                str(src_b04.bounds),
                str(src_b04.dtypes),
                str(src_b04.nodata),
                str(src_b04.transform)
            ],
            "B08 (NIR)": [
                src_b08.width,
                src_b08.height,
                src_b08.count,
                str(src_b08.crs),
                str(src_b08.res),
                str(src_b08.bounds),
                str(src_b08.dtypes),
                str(src_b08.nodata),
                str(src_b08.transform)
            ]
        }

        df_metadata = pd.DataFrame(metadata)

        st.dataframe(df_metadata, hide_index=True)

        st.subheader("1.4 Pełne profile rastrów")

        st.code("""
src.profile
""",  language="python")

        # st.json(dict(src_b04.profile))

        col1, col2 = st.columns(2)

        with col1:
            st.write("**B04 — Red**")
            st.json(dict(src_b04.profile))

        with col2:
            st.write("**B08 — NIR**")
            st.json(dict(src_b08.profile))


with tab2:
    st.header("2. Piksel ↔ współrzędne")

    st.write(
        "Transformacja afiniczna (src.transform) przelicza "
        "indeksy pikseli na współrzędne terenowe."
    )

    with rasterio.open(raster_path_b04) as src, \
            rasterio.open(raster_path_b08) as nir_src:

        st.subheader("2.1 Informacje o siatce")

        st.write("CRS:", src.crs)
        st.write("Rozdzielczość:", src.res)
        st.write("Lewy górny róg:", (src.bounds.left, src.bounds.top))

        # Sprawdzenie, czy oba rastry mają wspólną siatkę
        same_grid = (
                src.crs == nir_src.crs
                and src.transform == nir_src.transform
                and src.width == nir_src.width
                and src.height == nir_src.height
        )

        if not same_grid:
            st.error(
                "B04 i B08 mają różne siatki pikseli. "
                "Przed porównaniem wartości konieczne "
                "jest ich wyrównanie."
            )

        else:
            st.subheader("2.2 Wybór piksela")

            row = st.slider(
                "Wiersz (row)",
                min_value=0,
                max_value=src.height - 1,
                value=min(858, src.height - 1)
            )

            col = st.slider(
                "Kolumna (col)",
                min_value=0,
                max_value=src.width - 1,
                value=min(750, src.width - 1)
            )

            # Indeksy piksela -> współrzędne
            x, y = src.xy(row, col)

            # Współrzędne -> indeksy piksela
            new_row, new_col = src.index(x, y)

            # Odczyt tylko jednego piksela z każdego rastra
            window = Window(col, row, 1, 1)

            red = src.read(
                1, window=window, masked=True
            )[0, 0]

            nir = nir_src.read(
                1, window=window, masked=True
            )[0, 0]

            # Obliczenie NDVI
            if (
                    np.ma.is_masked(red)
                    or np.ma.is_masked(nir)
            ):
                red_value = np.nan
                nir_value = np.nan
                ndvi = np.nan

            else:
                red_value = float(red)
                nir_value = float(nir)

                denominator = nir_value + red_value

                ndvi = (
                    (nir_value - red_value) / denominator
                    if denominator != 0 else np.nan
                )

            st.subheader("2.3 Wartości wybranego piksela")

            c1, c2, c3 = st.columns(3)

            with c1:
                st.metric(
                    "X, Y — środek piksela",
                    f"{x:.6f}, {y:.6f}"
                )

            with c2:
                st.metric(
                    "src.index(x, y)",
                    f"{new_row}, {new_col}"
                )

            with c3:
                st.metric(
                    "Rozmiar piksela",
                    f"{abs(src.res[0]):.6f} × {abs(src.res[1]):.6f}"
                )

            c1, c2, c3 = st.columns(3)

            with c1:
                st.metric(
                    "Red (B04)",
                    f"{red_value:.4f}"
                )

            with c2:
                st.metric(
                    "NIR (B08)",
                    f"{nir_value:.4f}"
                )

            with c3:
                st.metric(
                    "NDVI",
                    f"{ndvi:.3f}"
                )

            st.subheader("2.4 Kod wykonywanych operacji")

            st.code(f"""
    # Piksel -> współrzędne
    x, y = src.xy({row}, {col})

    # Współrzędne -> piksel
    row, col = src.index(x, y)

    # Odczyt pojedynczego piksela B04
    red = src.read(
        1,
        window=Window({col}, {row}, 1, 1),
        masked=True
    )[0, 0]

    # NDVI
    ndvi = (nir - red) / (nir + red)
    """, language="python")

            st.subheader("2.5 Wizualizacja rastrów B04 i B08")

            # Współrzędne wybranego piksela w WGS 84
            lon, lat = transform_coordinates(
                src.crs,
                "EPSG:4326",
                [x],
                [y]
            )

            lon, lat = lon[0], lat[0]

            # Utworzenie mapy
            m = folium.Map(
                location=[lat, lon],
                zoom_start=15,
                tiles=(
                    "https://server.arcgisonline.com/ArcGIS/rest/"
                    "services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                ),
                attr="Tiles © Esri and its data providers"
            )

            # Dodanie obu rastrów
            for name, raster in [
                ("B04 - Red", src),
                ("B08 - NIR", nir_src)
            ]:

                # Odczyt całego rastra
                band = raster.read(1, masked=True)

                # Maska pikseli bez danych
                valid = ~np.ma.getmaskarray(band)
                values = band.filled(np.nan).astype("float32")
                valid &= np.isfinite(values)

                # Normalizacja wartości do zakresu 0-255
                image = np.zeros(values.shape, dtype=np.uint8)

                if valid.any():
                    vmin, vmax = np.percentile(
                        values[valid],
                        [2, 98]
                    )

                    if vmax > vmin:
                        image[valid] = (
                                np.clip(
                                    (values[valid] - vmin) / (vmax - vmin),
                                    0,
                                    1
                                ) * 255
                        ).astype(np.uint8)

                # Obraz RGBA: odcienie szarości + przezroczystość
                rgba = np.zeros(
                    (raster.height, raster.width, 4),
                    dtype=np.uint8
                )

                rgba[:, :, 0] = image
                rgba[:, :, 1] = image
                rgba[:, :, 2] = image
                rgba[:, :, 3] = np.where(valid, 255, 0).astype("uint8")

                # Granice rastra w EPSG:4326
                from rasterio.warp import transform_bounds

                west, south, east, north = transform_bounds(
                    raster.crs,
                    "EPSG:4326",
                    *raster.bounds
                )

                folium.raster_layers.ImageOverlay(
                    image=rgba,
                    bounds=[
                        [south, west],
                        [north, east]
                    ],
                    name=name,
                    opacity=0.85,
                    show=(name == "B04 - Red")
                ).add_to(m)

            # Marker wybranego piksela
            folium.CircleMarker(
                location=[lat, lon],
                radius=5,
                color="yellow",
                fill=True,
                fill_color="yellow",
                fill_opacity=1,
                tooltip=f"row={row}, col={col}"
            ).add_to(m)

            # Dopasowanie mapy do rastra B04
            west, south, east, north = transform_bounds(
                src.crs,
                "EPSG:4326",
                *src.bounds
            )

            m.fit_bounds([
                [south, west],
                [north, east]
            ])

            # Kontrolka warstw
            folium.LayerControl(collapsed=False).add_to(m)

            st_folium(
                m,
                width="stretch",
                height=600,
                returned_objects=[]
            )

with tab3:
    st.header("3. Odczyt pasm i statystyki")

    st.write(
        "Rasterio pozwala odczytywać wartości pikseli "
        "oraz obliczać statystyki dla poszczególnych pasm."
    )

    # 1. ODCZYT RASTRÓW
    st.subheader("3.1 Odczyt B04 i B08")

    st.code("""
    with rasterio.open(raster_b04) as src:
        red = src.read(1, masked=True).astype("float32")

    with rasterio.open(raster_b08) as src:
        nir = src.read(1, masked=True).astype("float32")
    """, language="python")

    with rasterio.open(raster_path_b04) as src:
        red = src.read(1, masked=True).astype("float32")

    with rasterio.open(raster_path_b08) as src:
        nir = src.read(1, masked=True).astype("float32")

    # Maskowanie wartości nieskończonych i NaN
    red = np.ma.masked_invalid(red)
    nir = np.ma.masked_invalid(nir)

    st.info(
        "masked=True oznacza, że piksele NoData "
        "są pomijane podczas obliczania statystyk."
    )

    # 2. STATYSTYKI PASM
    st.subheader("3.2 Statystyki Red i NIR")

    st.code("""
    red.min()
    red.max()
    red.mean()
    np.ma.median(red)
    red.std()
    np.ma.getmaskarray(red).sum()
    """, language="python")

    statistics = pd.DataFrame({
        "Pasmo": ["Red (B04)", "NIR (B08)"],
        "Min": [red.min(), nir.min()],
        "Maks": [red.max(), nir.max()],
        "Średnia": [red.mean(), nir.mean()],
        "Mediana": [
            np.ma.median(red),
            np.ma.median(nir)
        ],
        "Odch. stand.": [red.std(), nir.std()],
        "Piksele NoData": [
            np.ma.getmaskarray(red).sum(),
            np.ma.getmaskarray(nir).sum()
        ]
    })

    st.dataframe(
        statistics.round(4),
        hide_index=True,
        width="stretch"
    )

    # 3. WIZUALIZACJA RASTRÓW
    st.subheader("3.3 Wizualizacja pasm")

    st.write(
        "Oba rastry wyświetlamy w skali szarości. "
        "Ciemniejsze piksele mają niższe wartości odbicia, "
        "a jaśniejsze — wyższe."
    )

    st.code("""
    plt.imshow(red, cmap="gray", vmin=0, vmax=1)
    plt.colorbar(label="Odbicie")
    """, language="python")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Red (B04) — odbicie 0–1**")

        fig, ax = plt.subplots(figsize=(6, 5))

        img = ax.imshow(
            red,
            cmap="gray",
            vmin=0,
            vmax=1
        )

        fig.colorbar(
            img,
            ax=ax,
            label="Odbicie"
        )

        ax.set_axis_off()

        st.pyplot(fig)
        plt.close(fig)

    with col2:
        st.write("**NIR (B08) — odbicie 0–1**")

        fig, ax = plt.subplots(figsize=(6, 5))

        img = ax.imshow(
            nir,
            cmap="gray",
            vmin=0,
            vmax=1
        )

        fig.colorbar(
            img,
            ax=ax,
            label="Odbicie"
        )

        ax.set_axis_off()

        st.pyplot(fig)
        plt.close(fig)

    # 4. HISTOGRAM
    st.subheader("3.4 Histogram odbicia Red i NIR")

    st.write(
        "Histogram przedstawia liczbę pikseli "
        "w poszczególnych zakresach odbicia."
    )

    st.code("""
    plt.hist(
        red.compressed(),
        bins=60,
        alpha=0.6,
        label="Red"
    )

    plt.hist(
        nir.compressed(),
        bins=60,
        alpha=0.6,
        label="NIR"
    )
    """, language="python")

    fig, ax = plt.subplots(figsize=(10, 4))

    ax.hist(
        red.compressed(),
        bins=60,
        range=(0, 1),
        alpha=0.6,
        color="red",
        label="Red (B04)"
    )

    ax.hist(
        nir.compressed(),
        bins=60,
        range=(0, 1),
        alpha=0.6,
        color="green",
        label="NIR (B08)"
    )

    ax.set_xlabel("Odbicie (0–1)")
    ax.set_ylabel("Liczba pikseli")
    ax.set_title("Rozkład odbicia Red i NIR")
    ax.legend()
    ax.grid(alpha=0.2)

    st.pyplot(fig)
    plt.close(fig)


with tab4:
    st.header("4. Wspólna siatka w metrach")

    st.write(
        "Przed obliczeniem NDVI musimy upewnić się, "
        "że pasma Red i NIR mają identyczną siatkę. "
        "Następnie przeliczymy je do EPSG:2180."
    )

    with rasterio.open(raster_path_b04) as red_src, \
         rasterio.open(raster_path_b08) as nir_src:

        # 1. PORÓWNANIE SIATEK
        st.subheader("4.1 Sprawdzenie zgodności rastrów")

        st.code("""
same_grid = (
    red_src.crs == nir_src.crs
    and red_src.transform == nir_src.transform
    and red_src.shape == nir_src.shape
)
""", language="python")

        same_grid = (
            red_src.crs == nir_src.crs
            and red_src.transform == nir_src.transform
            and red_src.shape == nir_src.shape
        )

        if same_grid:
            st.success("Pasma Red i NIR mają identyczną siatkę.")
        else:
            st.warning(
                "Pasma mają różne siatki. "
                "Zostaną wyrównane podczas reprojekcji."
            )

        metadata = pd.DataFrame({
            "Parametr": [
                "CRS",
                "Szerokość (px)",
                "Wysokość (px)",
                "Rozdzielczość"
            ],
            "B04 (Red)": [
                str(red_src.crs),
                red_src.width,
                red_src.height,
                str(red_src.res)
            ],
            "B08 (NIR)": [
                str(nir_src.crs),
                nir_src.width,
                nir_src.height,
                str(nir_src.res)
            ]
        })

        st.dataframe(metadata, hide_index=True)

        # 2. DOCELOWA SIATKA EPSG:2180
        st.subheader("4.2 Utworzenie siatki metrycznej")

        st.write(
            "Tworzymy wspólną siatkę w EPSG:2180 "
            "o rozdzielczości 10 metrów."
        )

        st.code("""
dst_crs = "EPSG:2180"

dst_transform, width, height = calculate_default_transform(
    red_src.crs,
    dst_crs,
    red_src.width,
    red_src.height,
    *red_src.bounds,
    resolution=10
)
""", language="python")

        dst_crs = "EPSG:2180"

        dst_transform, width, height = calculate_default_transform(
            red_src.crs,
            dst_crs,
            red_src.width,
            red_src.height,
            *red_src.bounds,
            resolution=10
        )

        # 3. REPROJEKCJA B04
        st.subheader("4.3 Reprojekcja pasma Red")

        st.code("""
red_m = np.full(
    (height, width),
    np.nan,
    dtype="float32"
)

reproject(
    source=rasterio.band(red_src, 1),
    destination=red_m,
    dst_transform=dst_transform,
    dst_crs=dst_crs,
    dst_nodata=np.nan,
    resampling=Resampling.bilinear
)

red_m = np.ma.masked_invalid(red_m)
""", language="python")

        red_m = np.full(
            (height, width),
            np.nan,
            dtype="float32"
        )

        reproject(
            source=rasterio.band(red_src, 1),
            destination=red_m,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear
        )

        red_m = np.ma.masked_invalid(red_m)

        # 4. REPROJEKCJA B08
        st.subheader("4.4 Reprojekcja pasma NIR")

        st.code("""
nir_m = np.full(
    (height, width),
    np.nan,
    dtype="float32"
)

reproject(
    source=rasterio.band(nir_src, 1),
    destination=nir_m,
    dst_transform=dst_transform,
    dst_crs=dst_crs,
    dst_nodata=np.nan,
    resampling=Resampling.bilinear
)

nir_m = np.ma.masked_invalid(nir_m)
""", language="python")

        nir_m = np.full(
            (height, width),
            np.nan,
            dtype="float32"
        )

        reproject(
            source=rasterio.band(nir_src, 1),
            destination=nir_m,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear
        )

        nir_m = np.ma.masked_invalid(nir_m)

        # 5. PORÓWNANIE PRZED / PO
        st.subheader("4.5 Porównanie siatek")

        comparison = pd.DataFrame({
            "Parametr": [
                "CRS",
                "Szerokość (px)",
                "Wysokość (px)",
                "Rozdzielczość"
            ],
            "Przed (B04)": [
                str(red_src.crs),
                red_src.width,
                red_src.height,
                str(red_src.res)
            ],
            "Po (B04 i B08)": [
                dst_crs,
                width,
                height,
                str((dst_transform.a, abs(dst_transform.e)))
            ]
        })

        st.dataframe(comparison, hide_index=True)

        st.success(
            "Oba pasma zostały przeliczone do EPSG:2180 "
            "i umieszczone na wspólnej siatce 10 × 10 m."
        )

        # 6. WIZUALIZACJA
        st.subheader("4.6 Wizualizacja po reprojekcji")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Red (B04)**")

            fig, ax = plt.subplots(figsize=(6, 5))

            img = ax.imshow(
                red_m,
                cmap="gray",
                vmin=0,
                vmax=1
            )

            fig.colorbar(img, ax=ax, label="Odbicie")
            ax.set_axis_off()

            st.pyplot(fig)
            plt.close(fig)

        with col2:
            st.write("**NIR (B08)**")

            fig, ax = plt.subplots(figsize=(6, 5))

            img = ax.imshow(
                nir_m,
                cmap="gray",
                vmin=0,
                vmax=1
            )

            fig.colorbar(img, ax=ax, label="Odbicie")
            ax.set_axis_off()

            st.pyplot(fig)
            plt.close(fig)

        # 7. PODSUMOWANIE
        st.subheader("4.7 Wynik transformacji")

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric("CRS", dst_crs)

        with c2:
            st.metric("Rozdzielczość", "10 × 10 m")

        with c3:
            st.metric(
                "Wymiary",
                f"{width} × {height} px"
            )


with tab5:
    st.header("5. Obliczenie NDVI")

    st.write(
        "NDVI (Normalized Difference Vegetation Index) "
        "pozwala ocenić aktywność roślinności na podstawie "
        "odbicia światła czerwonego (B04) oraz "
        "bliskiej podczerwieni (B08)."
    )

    # 1. OBLICZENIE NDVI
    st.subheader("5.1 Obliczenie wskaźnika")

    st.latex(r"NDVI = \frac{NIR - Red}{NIR + Red}")

    st.code("""
with np.errstate(divide="ignore", invalid="ignore"):
    ndvi = (nir_m - red_m) / (nir_m + red_m)

ndvi = np.ma.masked_invalid(ndvi)
""", language="python")

    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir_m - red_m) / (nir_m + red_m)

    ndvi = np.ma.masked_invalid(ndvi)

    valid = ndvi.compressed()

    if valid.size == 0:
        st.warning("Brak poprawnych pikseli NDVI.")
        st.stop()

    # 2. STATYSTYKI NDVI
    st.subheader("5.2 Statystyki NDVI")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Średnie NDVI", f"{valid.mean():.3f}")

    with col2:
        st.metric("Mediana NDVI", f"{np.median(valid):.3f}")

    with col3:
        st.metric(
            "Zakres NDVI",
            f"{valid.min():.2f} … {valid.max():.2f}"
        )

    # 3. PRZYKŁADOWE PIKSELE
    st.subheader("5.3 Przykładowe wartości pikseli")

    st.write(
        "Wyszukujemy piksele o najwyższym, medianowym "
        "i najniższym NDVI w przetworzonym rastrze."
    )

    ndvi_values = ndvi.filled(np.nan)

    max_row, max_col = np.unravel_index(
        np.nanargmax(ndvi_values),
        ndvi.shape
    )

    min_row, min_col = np.unravel_index(
        np.nanargmin(ndvi_values),
        ndvi.shape
    )

    median_value = np.median(valid)

    median_row, median_col = np.unravel_index(
        np.nanargmin(np.abs(ndvi_values - median_value)),
        ndvi.shape
    )

    pixel_data = []

    for name, row, col in [
        ("Najwyższe NDVI", max_row, max_col),
        ("Mediana NDVI", median_row, median_col),
        ("Najniższe NDVI", min_row, min_col)
    ]:
        red_value = float(red_m[row, col])
        nir_value = float(nir_m[row, col])
        ndvi_value = float(ndvi[row, col])

        pixel_data.append({
            "Przykład": name,
            "Piksel (row, col)": f"({row}, {col})",
            "Red (B04)": red_value,
            "NIR (B08)": nir_value,
            "NDVI": ndvi_value
        })

    st.dataframe(
        pd.DataFrame(pixel_data).round(4),
        hide_index=True,
        width="stretch"
    )

    st.info(
        "Współrzędne pikseli zostały obliczone automatycznie. "
        "Mogą różnić się od przykładów z materiałów ćwiczeniowych."
    )

    # 4. MAPA NDVI
    st.subheader("5.4 Mapa NDVI")

    st.write(
        "Wartości ujemne oznaczają zwykle wodę lub inne "
        "powierzchnie słabo odbijające NIR, natomiast "
        "wysokie dodatnie wartości wskazują roślinność."
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    image = ax.imshow(
        ndvi,
        cmap="RdYlGn",
        vmin=-1,
        vmax=1
    )

    fig.colorbar(
        image,
        ax=ax,
        label="NDVI (-1 do 1)"
    )

    ax.set_title("NDVI — Sentinel-2")
    ax.set_axis_off()

    st.pyplot(fig)
    plt.close(fig)

    # 5. HISTOGRAM NDVI
    st.subheader("5.5 Histogram NDVI")

    st.write(
        "Histogram pokazuje rozkład wartości NDVI "
        "dla wszystkich poprawnych pikseli."
    )

    st.code("""
plt.hist(
    ndvi.compressed(),
    bins=80,
    range=(-1, 1)
)
""", language="python")

    fig, ax = plt.subplots(figsize=(10, 4))

    ax.hist(
        valid,
        bins=80,
        range=(-1, 1),
        color="forestgreen",
        edgecolor="none"
    )

    ax.set_xlabel("Wartość NDVI")
    ax.set_ylabel("Liczba pikseli")
    ax.set_title("Rozkład wartości NDVI")
    ax.grid(alpha=0.2)

    st.pyplot(fig)
    plt.close(fig)



with tab6:
    st.header("6. Klasyfikacja i powierzchnie")

    st.write(
        "Dzielimy NDVI na cztery klasy na podstawie "
        "trzech progów. Zmiana progów wpływa na "
        "mapę i obliczone powierzchnie."
    )

    # 1. PROGI KLASYFIKACJI
    st.subheader("6.1 Progi NDVI")

    col1, col2, col3 = st.columns(3)

    with col1:
        water = st.slider(
            "Próg: woda <",
            min_value=-1.0,
            max_value=1.0,
            value=-0.25,
            step=0.05
        )

    with col2:
        soil = st.slider(
            "Próg: gleba/zabudowa <",
            min_value=-1.0,
            max_value=1.0,
            value=0.20,
            step=0.05
        )

    with col3:
        vegetation = st.slider(
            "Próg: rzadka roślinność <",
            min_value=-1.0,
            max_value=1.0,
            value=0.50,
            step=0.05
        )

    # 2. KLASYFIKACJA NDVI
    st.subheader("6.2 Klasyfikacja pikseli")

    st.code(f"""
classes = np.digitize(
    ndvi.filled(np.nan),
    bins=[{water:.2f}, {soil:.2f}, {vegetation:.2f}]
)

classes = np.ma.masked_where(
    np.ma.getmaskarray(ndvi),
    classes
)
""", language="python")

    thresholds = sorted([water, soil, vegetation])

    classes = np.digitize(
        ndvi.filled(np.nan),
        bins=thresholds
    )

    classes = np.ma.masked_where(
        np.ma.getmaskarray(ndvi),
        classes
    )

    classes = np.ma.masked_where(
        np.ma.getmaskarray(ndvi),
        classes
    )

    # 3. OBLICZANIE POWIERZCHNI
    st.subheader("6.3 Powierzchnia klas")

    st.code("""
pixel_area_m2 = abs(dst_transform.a * dst_transform.e)

area_ha = (
    np.bincount(classes.compressed(), minlength=4)
    * pixel_area_m2 / 10_000
)
""", language="python")

    pixel_area_m2 = abs(
        dst_transform.a * dst_transform.e
    )

    counts = np.bincount(
        classes.compressed(),
        minlength=4
    )

    area_ha = counts * pixel_area_m2 / 10_000

    class_names = [
        "Woda / bardzo niskie NDVI",
        "Gleba / zabudowa",
        "Rzadka roślinność",
        "Gęsta roślinność"
    ]

    colors = [
        "#2563eb",  # Niebieski
        "#a16207",  # Brązowy
        "#facc15",  # Żółty
        "#15803d"   # Zielony
    ]

    results = pd.DataFrame({
        "Klasa": class_names,
        "Liczba pikseli": counts,
        "Powierzchnia (ha)": area_ha.round(2)
    })

    results["Udział (%)"] = (
        results["Liczba pikseli"]
        / results["Liczba pikseli"].sum()
        * 100
    ).round(2)

    # 4. MAPA KLAS NDVI
    st.subheader("6.4 Klasy NDVI")

    cmap = ListedColormap(colors)
    norm = BoundaryNorm(
        [-0.5, 0.5, 1.5, 2.5, 3.5],
        cmap.N
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.imshow(
        classes,
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    ax.set_title("Klasy NDVI")
    ax.set_axis_off()

    legend = [
        Patch(color=colors[i], label=class_names[i])
        for i in range(4)
    ]

    ax.legend(
        handles=legend,
        loc="upper left",
        bbox_to_anchor=(1.02, 1)
    )

    st.pyplot(fig)
    plt.close(fig)

    # -----------------------------------
    # 5. TABELA WYNIKÓW
    # -----------------------------------

    st.subheader("6.5 Powierzchnia według klas")

    st.dataframe(
        results,
        hide_index=True,
        width="stretch"
    )

    st.metric(
        "Łączna sklasyfikowana powierzchnia",
        f"{area_ha.sum():,.2f} ha"
    )


with tab7:
    st.header("7. Statystyki strefowe (GeoPandas)")

    st.write(
        "Łączymy raster NDVI z poligonami dzielnic Opola. "
        "Dla każdej dzielnicy obliczamy pokrycie sceną "
        "oraz statystyki NDVI."
    )

    # 1. WCZYTANIE POLIGONÓW
    st.subheader("7.1 Wczytanie dzielnic")

    st.code("""
zones = gpd.read_file(
    DATA_DIR.parent / "opole_districts.geojson"
).to_crs(dst_crs)
""", language="python")

    zones = gpd.read_file(
        DATA_DIR.parent / "opole_districts.geojson"
    ).to_crs(dst_crs)

    zones = zones.reset_index(drop=True)

    # Zachowujemy identyfikator dzielnicy
    if "zone_id" not in zones.columns:
        zones["zone_id"] = zones.index + 1

    st.metric("Liczba poligonów", len(zones))

    # 2. PRZYGOTOWANIE RASTRA
    st.subheader("7.2 Przygotowanie rastra NDVI")

    st.write(
        "Tworzymy tymczasowy raster w pamięci, "
        "zachowując CRS i transformację z tab4."
    )

    st.code("""
profile = {
    "driver": "GTiff",
    "height": ndvi.shape[0],
    "width": ndvi.shape[1],
    "count": 1,
    "dtype": "float32",
    "crs": dst_crs,
    "transform": dst_transform,
    "nodata": np.nan
}
""", language="python")

    profile = {
        "driver": "GTiff",
        "height": ndvi.shape[0],
        "width": ndvi.shape[1],
        "count": 1,
        "dtype": "float32",
        "crs": dst_crs,
        "transform": dst_transform,
        "nodata": np.nan
    }

    # 3. STATYSTYKI STREFOWE
    st.subheader("7.3 Obliczenie statystyk")

    st.code("""
for i, zone in zones.iterrows():

    clipped, _ = rasterio.mask.mask(
        src,
        [zone.geometry],
        crop=True,
        nodata=np.nan
    )

    values = clipped[np.isfinite(clipped)]

    coverage = (
        values.size * pixel_area
        / zone.geometry.area
    ) * 100

    zones.loc[i, "coverage"] = coverage

    if coverage >= 50 and values.size > 0:
        zones.loc[i, "ndvi_mean"] = values.mean()
        zones.loc[i, "ndvi_min"] = values.min()
        zones.loc[i, "ndvi_max"] = values.max()
""", language="python")

    pixel_area = abs(
        dst_transform.a * dst_transform.e
    )

    zones["coverage"] = 0.0
    zones["ndvi_mean"] = np.nan
    zones["ndvi_min"] = np.nan
    zones["ndvi_max"] = np.nan

    with MemoryFile() as memfile:
        with memfile.open(**profile) as dst:
            dst.write(
                ndvi.filled(np.nan).astype("float32"),
                1
            )

        with memfile.open() as src:

            for i, zone in zones.iterrows():

                try:
                    clipped, _ = rasterio.mask.mask(
                        src,
                        [zone.geometry],
                        crop=True,
                        nodata=np.nan
                    )

                except ValueError:
                    # Poligon poza zasięgiem rastra
                    continue

                values = clipped[np.isfinite(clipped)]

                if zone.geometry.area <= 0:
                    continue

                coverage = (
                    values.size * pixel_area
                    / zone.geometry.area
                ) * 100

                zones.loc[i, "coverage"] = min(
                    coverage, 100
                )

                if coverage >= 50 and values.size > 0:
                    zones.loc[i, "ndvi_mean"] = values.mean()
                    zones.loc[i, "ndvi_min"] = values.min()
                    zones.loc[i, "ndvi_max"] = values.max()

    # 4. PODSUMOWANIE
    st.subheader("7.4 Podsumowanie analizy")

    low_coverage = zones["coverage"] < 50
    valid_zones = zones["ndvi_mean"].notna()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Liczba dzielnic",
            len(zones)
        )

    with col2:
        st.metric(
            "Pokrycie < 50%",
            int(low_coverage.sum())
        )

    with col3:
        st.metric(
            "Dzielnice ze statystykami",
            int(valid_zones.sum())
        )

    # 5. MAPA NDVI I POLIGONY
    st.subheader("7.5 NDVI + średnie w poligonach")

    # Granice rastra w EPSG:2180
    west, south, east, north = array_bounds(
        ndvi.shape[0],
        ndvi.shape[1],
        dst_transform
    )

    # Ograniczenie wyświetlania poligonów do sceny
    scene = box(west, south, east, north)

    visible_zones = zones[
        zones.geometry.intersects(scene)
    ].copy()

    visible_zones["geometry"] = (
        visible_zones.geometry.intersection(scene)
    )

    # Skala kolorów NDVI
    cmap = LinearSegmentedColormap.from_list(
        "ndvi_colors",
        [
            (0.00, "#542788"),  # Fioletowy
            (0.25, "#2c7fb8"),  # Niebieski
            (0.50, "#d73027"),  # Czerwony
            (0.625, "#fdae61"),  # Pomarańczowy
            (0.75, "#fee08b"),  # Żółty
            (0.875, "#91cf60"),  # Zielony
            (1.00, "#00d83a")  # Intensywna zieleń
        ]
    )

    cmap.set_bad("#e8e8e8")
    norm = Normalize(vmin=-1, vmax=1)

    fig, ax = plt.subplots(figsize=(10, 12))

    ax.set_facecolor("#e8e8e8")

    # Raster NDVI
    ax.imshow(
        ndvi,
        extent=[west, east, south, north],
        origin="upper",
        cmap=cmap,
        norm=norm,
        interpolation="nearest"
    )

    # Poligony z pokryciem >= 50%
    valid_polygons = visible_zones[
        visible_zones["coverage"] >= 50
        ]

    valid_polygons.plot(
        ax=ax,
        color=[
            cmap(norm(value))
            for value in valid_polygons["ndvi_mean"]
        ],
        edgecolor="black",
        linewidth=0.9,
        alpha=0.88,
        zorder=3
    )

    # Poligony z pokryciem < 50%
    low_polygons = visible_zones[
        visible_zones["coverage"] < 50
        ]

    low_polygons.plot(
        ax=ax,
        facecolor="none",
        edgecolor="#333333",
        linewidth=0.8,
        hatch="///",
        zorder=4
    )

    # Nazwy i średnie NDVI dla dzielnic
    for _, zone in valid_polygons.iterrows():
        point = zone.geometry.representative_point()

        ax.text(
            point.x,
            point.y,
            f"{zone['name']}\n{zone['ndvi_mean']:.2f}",
            fontsize=7,
            ha="center",
            va="center",
            linespacing=1.0,
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.8,
                "pad": 0.5
            },
            zorder=5
        )

    # Legenda kolorów NDVI
    colorbar = fig.colorbar(
        ScalarMappable(norm=norm, cmap=cmap),
        ax=ax,
        fraction=0.046,
        pad=0.04
    )

    colorbar.set_label("NDVI")

    # Opis wykresu
    ax.set_title("NDVI + średnie w poligonach")
    ax.set_xlabel("Easting [metre]")
    ax.set_ylabel("Northing [metre]")

    ax.set_xlim(west, east)
    ax.set_ylim(south, north)
    ax.set_aspect("equal")

    fig.tight_layout()

    st.pyplot(fig)
    plt.close(fig)

    # 6. TABELA WYNIKÓW
    st.subheader("7.6 Statystyki dzielnic")

    results = zones[[
        "zone_id",
        "coverage",
        "ndvi_mean",
        "ndvi_min",
        "ndvi_max"
    ]].copy()

    results = results.rename(columns={
        "coverage": "Pokrycie [%]"
    })

    st.dataframe(
        results.round(3),
        hide_index=True,
        width="stretch"
    )

    st.info(
        f"{low_coverage.sum()} z {len(zones)} poligonów "
        "ma pokrycie poniżej 50% (kreskowane). "
        "Nie obliczamy dla nich statystyk NDVI, "
        "ponieważ mogłyby być niereprezentatywne."
    )

    st.caption(
        "Granice dzielnic: OpenStreetMap contributors (ODbL)."
    )
