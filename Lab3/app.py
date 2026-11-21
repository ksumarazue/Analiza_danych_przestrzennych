import base64
import io

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from PIL import Image
from rasterio.io import MemoryFile

import pandas as pd
from ultralytics import YOLO

MODEL_FILE = "yolo11n-obb.pt"  # trained on DOTA (aerial images), downloaded on first use

DISPLAY_MAX_PX = 3000  # larger images are shrunk for display only (zooming in shows no more detail)
PLOTLY_CONFIG = {"scrollZoom": True, "displaylogo": False}


@st.cache_data
def read_geotiff(data: bytes) -> tuple[np.ndarray, dict]:
    """GeoTIFF bytes -> RGB image (H, W, 3, uint8) + basic metadata."""
    with MemoryFile(data) as memfile, memfile.open() as src:
        bands = src.read(list(range(1, min(src.count, 3) + 1)))
        meta = {
            "width": src.width, "height": src.height, "count": src.count, "dtype": src.dtypes[0],
            "crs": src.crs.to_string() if src.crs else None, "res": src.res, "transform": src.transform,
        }
    if bands.shape[0] == 1:  # single band -> grayscale shown as RGB
        bands = np.repeat(bands, 3, axis=0)
    return to_uint8(bands).transpose(1, 2, 0), meta


def to_uint8(bands: np.ndarray) -> np.ndarray:
    """Stretch any data type to 0-255 (2-98 percentile), so e.g. 16-bit images are visible."""
    if bands.dtype == np.uint8:
        return bands
    low, high = np.nanpercentile(bands, (2, 98))
    return (np.clip((bands - low) / max(high - low, 1e-9), 0, 1) * 255).astype(np.uint8)


@st.cache_resource
def load_model() -> YOLO:
    return YOLO(MODEL_FILE)


@st.cache_data
def image_source(image: np.ndarray) -> tuple[str, float]:
    """Image as a JPEG data URI (shrunk to DISPLAY_MAX_PX) + how many original pixels one shown pixel covers."""
    picture = Image.fromarray(image)
    picture.thumbnail((DISPLAY_MAX_PX, DISPLAY_MAX_PX))
    buffer = io.BytesIO()
    picture.save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode(), image.shape[1] / picture.width


def interactive_view(image: np.ndarray) -> go.Figure:
    """Zoomable image (scroll wheel, drag to pan); axes are pixels of the original image."""
    source, scale = image_source(image)
    # x0/y0: plotly places pixel centres at x0, x0 + dx, ...; box corners use pixel edges (0 = left edge).
    fig = go.Figure(go.Image(source=source, dx=scale, dy=scale, x0=scale / 2, y0=scale / 2, hoverinfo="skip"))
    fig.update_layout(height=750, margin={"l": 0, "r": 0, "t": 0, "b": 0}, dragmode="pan", showlegend=False)
    fig.update_xaxes(visible=False, range=[0, image.shape[1]])
    fig.update_yaxes(visible=False, range=[image.shape[0], 0], scaleanchor="x")  # rows grow downwards
    return fig


st.set_page_config(page_title="Simple Cars Detector", page_icon="🚗", layout="wide")

st.title("🚗 Simple Cars Detector")
st.write("Wgraj zdjęcie lotnicze lub ortofotomapę w formacie GeoTIFF i kliknij „Wykrywaj”.")

uploaded = st.file_uploader("Plik GeoTIFF", type=["tif", "tiff"])
if uploaded is None:
    st.stop()

image, meta = read_geotiff(uploaded.getvalue())

with st.sidebar:
    st.header("Metadane")
    st.write(f"Rozmiar: {meta['width']} x {meta['height']} px, pasma: {meta['count']} ({meta['dtype']})")
    st.write(f"Układ współrzędnych: {meta['crs'] or 'brak (zwykły TIFF)'}")
    if meta["crs"]:
        st.write(f"Rozmiar piksela: {meta['res'][0]:.2f} x {meta['res'][1]:.2f}")

st.caption("Kółko myszy przybliża i oddala, przeciąganie przesuwa obraz, podwójne kliknięcie wraca do całości.")
st.plotly_chart(interactive_view(image), config=PLOTLY_CONFIG, width="stretch")

if st.button("Wykrywaj", type="primary"):
    with st.spinner("Wykrywam obiekty na całym obrazie..."):
        # The model expects BGR (OpenCV order), our image is RGB, so the channels are reversed.
        result = load_model().predict(image[..., ::-1].copy(), conf=0.25, verbose=False)[0]
    labels = [result.names[int(cls)] for cls in result.obb.cls.tolist()]
    st.subheader(f"Wykryte obiekty: {len(labels)}")
    st.dataframe(pd.Series(labels, name="klasa").value_counts())
    st.image(result.plot()[..., ::-1], caption="Wynik modelu dla całego obrazu naraz")  # plot() returns BGR