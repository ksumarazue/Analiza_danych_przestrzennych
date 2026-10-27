# Analiza danych przestrzennych – czujniki PM2.5 na terenie Opola

## 1. Cel ćwiczenia

Celem ćwiczenia było zapoznanie się z podstawowymi możliwościami bibliotek **Pandas** i **GeoPandas** w zakresie przetwarzania, analizy oraz wizualizacji danych przestrzennych.

W ramach laboratorium przeprowadzono analizę danych dotyczących czujników jakości powietrza PM2.5, lokalizacji szkół oraz granic administracyjnych dzielnic Opola.

Ćwiczenie wykonano w środowisku **Google Colab**, wykorzystując język Python. Końcowym rezultatem było przygotowanie oczyszczonego zbioru danych oraz interaktywnej mapy przedstawiającej analizowane obiekty.

## 2. Wykorzystane narzędzia i dane

### Narzędzia

- **Google Colab** – środowisko umożliwiające uruchamianie kodu Python w przeglądarce.
- **Python** – język programowania wykorzystany do przetwarzania danych.
- **Pandas** – biblioteka służąca do analizy i czyszczenia danych tabelarycznych.
- **GeoPandas** – biblioteka umożliwiająca przetwarzanie danych przestrzennych.
- **Folium** – biblioteka wykorzystywana do tworzenia interaktywnych map.
- **GitHub** – repozytorium przechowujące notatnik oraz dokumentację.

### Dane wejściowe

W ćwiczeniu wykorzystano trzy pliki:

| Plik | Format | Opis |
|---|---|---|
| `pm25_sensors.csv` | CSV | Dane czujników jakości powietrza, współrzędne geograficzne i wartości PM2.5 |
| `opole_districts.geojson` | GeoJSON | Granice administracyjne dzielnic Opola |
| `opole_schools.geojson` | GeoJSON | Lokalizacje szkół na terenie Opola |

## 3. Przebieg ćwiczenia

### Krok 1. Przygotowanie środowiska

Utworzono notatnik w środowisku Google Colab, a następnie zaimportowano biblioteki niezbędne do przeprowadzenia analizy.

```python
import pandas as pd
import geopandas as gpd
import folium
from IPython.display import display
```

### Krok 2. Wczytanie danych

Plik CSV zawierający dane czujników został wczytany przy użyciu biblioteki Pandas.

Pozostałe pliki, zawierające dane przestrzenne w formacie GeoJSON, zostały wczytane za pomocą GeoPandas.

```python
df = pd.read_csv("/content/data/pm25_sensors.csv")

districts = gpd.read_file("/content/data/opole_districts.geojson")
schools = gpd.read_file("/content/data/opole_schools.geojson")
```

Do wyświetlenia pierwszych rekordów wykorzystano metodę `head()`.

```python
display(df.head(10))
```

### Krok 3. Wstępna analiza danych

Przeprowadzono podstawową analizę zbioru danych obejmującą:

- sprawdzenie liczby rekordów,
- identyfikację typów danych,
- wyznaczenie podstawowych statystyk,
- wykrycie brakujących wartości,
- sprawdzenie występowania duplikatów.

Wykorzystano następujące instrukcje:

```python
print("Liczba rekordów:", len(df))

df.info()
display(df.describe())

print(df.isna().sum())
print(df.duplicated().sum())
```

Analiza pozwoliła zidentyfikować rekordy wymagające oczyszczenia przed dalszym przetwarzaniem.

### Krok 4. Czyszczenie danych

Proces czyszczenia obejmował usunięcie duplikatów, konwersję typów danych, obsługę brakujących wartości oraz korektę błędnych współrzędnych geograficznych.

**Usunięcie duplikatów:**

```python
df = df.drop_duplicates().copy()
```

**Konwersja danych na wartości liczbowe:**

```python
for col in ["lat", "lon", "pm25"]:
    df[col] = pd.to_numeric(df[col], errors="coerce")
```

Nieprawidłowe wartości tekstowe zostały zamienione na `NaN`.

**Usunięcie rekordów z brakującymi wartościami:**

```python
df = df.dropna(subset=["lat", "lon", "pm25"])
```

Usunięto rekordy bez wymaganych współrzędnych geograficznych lub wartości PM2.5.

**Wykrycie i poprawienie zamienionych współrzędnych:**

```python
swapped = df["lat"].between(14, 24.5) & df["lon"].between(49, 55)

print("Przed zmianą:")
display(df.loc[swapped, ["lat", "lon"]])

df.loc[swapped, ["lat", "lon"]] = df.loc[swapped, ["lon", "lat"]].to_numpy()

print("Po zmianie:")
display(df.loc[swapped, ["lat", "lon"]])
```

Zastosowano orientacyjne zakresy szerokości i długości geograficznej Polski. Wykryte błędne współrzędne zostały zamienione miejscami.

**Usunięcie nieprawidłowych pomiarów i lokalizacji:**

```python
df = df[df["pm25"] >= 0]

df = df[
    df["lat"].between(49, 55) &
    df["lon"].between(14, 24.5)
]
```

Odrzucono rekordy zawierające ujemne wartości PM2.5 oraz współrzędne znajdujące się poza przyjętym zakresem.

### Krok 5. Przygotowanie danych przestrzennych

Po zakończeniu czyszczenia utworzono obiekt `GeoDataFrame`, umożliwiający przetwarzanie danych czujników jako punktów przestrzennych.

```python
sensors = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["lon"], df["lat"]),
    crs="EPSG:4326"
)
```

Wykorzystano układ współrzędnych **EPSG:4326 (WGS 84)**, stosowany do reprezentowania lokalizacji geograficznych za pomocą szerokości i długości geograficznej.

Każdemu rekordowi przypisano geometrię typu `Point` na podstawie jego współrzędnych.

### Krok 6. Wizualizacja na interaktywnej mapie

Do przygotowania interaktywnej mapy wykorzystano bibliotekę Folium oraz metodę `explore()` z GeoPandas.

Na mapie przedstawiono trzy warstwy:

- granice administracyjne dzielnic Opola,
- lokalizacje czujników PM2.5,
- lokalizacje szkół.

Czujniki zostały oznaczone kolorami odpowiadającymi wartościom PM2.5.

Dzięki zastosowaniu interaktywnej mapy możliwe było przybliżanie widoku, wybieranie poszczególnych punktów oraz wyświetlanie informacji o obiektach.

Dodano również mechanizm `LayerControl`, pozwalający na włączanie i wyłączanie poszczególnych warstw.

### Krok 7. Wyświetlenie tabeli danych

Ostatnim elementem ćwiczenia było wyświetlenie tabeli zawierającej oczyszczone dane czujników.

```python
display(sensors.drop(columns="geometry"))
```

Usunięcie kolumny `geometry` z prezentowanej tabeli pozwoliło na czytelniejsze wyświetlenie podstawowych atrybutów punktów, takich jak współrzędne i wartości PM2.5.

Operacja ta nie zmieniła oryginalnego obiektu `sensors`.

## 4. Rezultaty

W wyniku przeprowadzonych operacji:

- Wczytano i przeanalizowano trzy zbiory danych.
- Zidentyfikowano błędne i brakujące wartości.
- Usunięto powtarzające się rekordy.
- Skorygowano zamienione współrzędne geograficzne.
- Odrzucono rekordy z nieprawidłowymi pomiarami PM2.5.
- Utworzono obiekt `GeoDataFrame` reprezentujący lokalizacje czujników.
- Przygotowano interaktywną mapę z trzema warstwami danych.
- Wyświetlono tabelę z oczyszczonymi danymi.

### Wyniki czyszczenia danych

| Parametr | Wartość |
|---|---:|
| Początkowa liczba rekordów czujników | 145 |
| Liczba rekordów po czyszczeniu | 130 |
| Liczba usuniętych rekordów | 15 |
| Liczba skorygowanych par współrzędnych | 3 |
| Udział zachowanych rekordów | 89,7% |

## 5. Wnioski

W ramach ćwiczenia zapoznano się z praktycznym wykorzystaniem bibliotek Pandas i GeoPandas do analizy danych tabelarycznych i przestrzennych.

Pandas umożliwił wykonanie podstawowych operacji związanych z przeglądaniem, filtrowaniem i czyszczeniem danych. GeoPandas pozwolił na utworzenie obiektów przestrzennych na podstawie współrzędnych geograficznych.

Zastosowanie interaktywnej mapy umożliwiło przedstawienie lokalizacji czujników PM2.5, szkół oraz granic dzielnic na wspólnej wizualizacji.

Ćwiczenie pokazało również znaczenie weryfikacji jakości danych przed ich wizualizacją. Nieprawidłowe współrzędne lub błędne pomiary mogłyby prowadzić do niepoprawnego rozmieszczenia punktów na mapie i błędnej interpretacji wyników.
