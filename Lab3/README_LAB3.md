# Analiza danych przestrzennych – wykrywanie obiektów na ortofotomapach (YOLO)

## 1. Cel ćwiczenia

Celem ćwiczenia było przygotowanie aplikacji **Streamlit** do wczytywania obrazów GeoTIFF oraz wykrywania obiektów na zdjęciach lotniczych za pomocą modelu **YOLO11n-OBB**.

## 2. Wykorzystane narzędzia i dane

- **Python, PyCharm** – przygotowanie aplikacji.
- **Streamlit** – interfejs użytkownika.
- **Rasterio, NumPy, Pillow** – odczyt i przetwarzanie obrazu.
- **Plotly** – interaktywny podgląd ortofotomapy.
- **Ultralytics YOLO** – wykrywanie obiektów.
- **Pandas** – zestawienie liczby wykryć według klas.

**Dane wejściowe:** plik `.tif` lub `.tiff` przesyłany przez użytkownika oraz model `yolo11n-obb.pt` (wagi wytrenowane na zbiorze DOTA, pobierane przy pierwszym użyciu, jeśli nie ma ich lokalnie).

## 3. Przebieg ćwiczenia

### 3.1. Przygotowanie środowiska

Zainstalowano biblioteki:

```bash
python -m pip install streamlit numpy plotly pillow rasterio pandas ultralytics
```

Aplikację uruchamia się poleceniem (zakładając zapis kodu w `app.py`):

```bash
streamlit run app.py
```

### 3.2. Wczytanie obrazu GeoTIFF

Za pomocą `rasterio.io.MemoryFile` odczytano maksymalnie trzy pasma obrazu. W panelu bocznym wyświetlane są jego rozmiary, typ danych, CRS i rozdzielczość piksela.

Dane przekształcono do formatu RGB `uint8`. W przypadku obrazów o większej głębi kolorów zastosowano skalowanie wartości na podstawie 2. i 98. percentyla.

### 3.3. Wizualizacja

Biblioteka Plotly umożliwia przybliżanie i przesuwanie obrazu. Na potrzeby wyświetlania duże obrazy są zmniejszane do maksymalnie 3000 pikseli na bok; nie zmienia to rozdzielczości obrazu przekazywanego do detekcji.

### 3.4. Detekcja obiektów

Po wybraniu przycisku **Wykrywaj** uruchamiany jest model YOLO11n-OBB:

```python
result = load_model().predict(
    image[..., ::-1].copy(), conf=0.25, verbose=False
)[0]
```

Model wykrywa obiekty za pomocą **obróconych ramek (OBB)**. Wyniki są przedstawiane na obrazie i w tabeli z liczbą wykryć dla poszczególnych klas, m.in. `small vehicle` i `large vehicle`.

## 4. Rezultaty

Przygotowano aplikację pozwalającą wczytać ortofotomapę, odczytać jej metadane, przeglądać obraz oraz automatycznie wykrywać i zliczać obiekty. Wyniki wizualizowane są na obrazie z zaznaczonymi ramkami detekcji.

## 5. Wnioski

Ćwiczenie pokazało możliwość połączenia przetwarzania danych rastrowych z rozpoznawaniem obiektów przy użyciu YOLO. Ograniczeniem jest analiza całego obrazu bez podziału na fragmenty, co może obniżać skuteczność detekcji drobnych obiektów. Aplikacja nie zapisuje również współrzędnych geograficznych wykryć.
