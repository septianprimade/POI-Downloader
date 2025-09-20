import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="POI Downloader", layout="wide")
st.title("📍 POI Downloader dari OpenStreetMap (OSM) + BPS Wilayah")

# Daftar kategori umum (amenity OSM)
kategori_list = [
    "restaurant", "cafe", "fast_food", "bar",
    "hospital", "clinic", "pharmacy",
    "school", "university", "college",
    "bank", "atm", "post_office",
    "fuel", "parking", "supermarket", "marketplace",
    "bus_station", "train_station", "airport"
]

# Server Overpass alternatif
overpass_servers = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter"
]

def query_overpass(query):
    """Coba query ke beberapa server Overpass"""
    for server in overpass_servers:
        try:
            response = requests.get(server, params={'data': query}, timeout=60)
            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    st.warning(f"❌ Gagal parse JSON dari {server}, coba server lain...")
            else:
                st.warning(f"⚠️ Server {server} balas status {response.status_code}")
        except Exception as e:
            st.warning(f"⚠️ Error akses {server}: {e}")
    return None


# ==============================
# Wilayah dari API BPS
# ==============================
BPS_BASE = "https://sig.bps.go.id/rest-bridging"

@st.cache_data
def get_provinces():
    url = f"{BPS_BASE}/getwilayah?level=provinsi"
    r = requests.get(url, timeout=60)
    data = r.json()
    return pd.DataFrame(data)

@st.cache_data
def get_regencies(kode_prov):
    url = f"{BPS_BASE}/getwilayah?level=kabupaten&kode_provinsi={kode_prov}"
    r = requests.get(url, timeout=60)
    data = r.json()
    return pd.DataFrame(data)

@st.cache_data
def get_districts(kode_kab):
    url = f"{BPS_BASE}/getwilayah?level=kecamatan&kode_kabupaten={kode_kab}"
    r = requests.get(url, timeout=60)
    data = r.json()
    return pd.DataFrame(data)


# ==============================
# Session State untuk hasil
# ==============================
if "pois_df" not in st.session_state:
    st.session_state["pois_df"] = None
if "wilayah" not in st.session_state:
    st.session_state["wilayah"] = None
if "kategori" not in st.session_state:
    st.session_state["kategori"] = None


# ==============================
# Dropdown berjenjang
# ==============================
prov_df = get_provinces()
prov_name = st.selectbox("Pilih Provinsi", [""] + prov_df["nama"].tolist())
kode_prov = prov_df.loc[prov_df["nama"] == prov_name, "kode"].values[0] if prov_name else ""

kab_name, kec_name = "", ""

if kode_prov:
    kab_df = get_regencies(kode_prov)
    kab_name = st.selectbox("Pilih Kabupaten/Kota", [""] + kab_df["nama"].tolist())
    kode_kab = kab_df.loc[kab_df["nama"] == kab_name, "kode"].values[0] if kab_name else ""
else:
    kode_kab = ""

if kode_kab:
    kec_df = get_districts(kode_kab)
    kec_name = st.selectbox("Pilih Kecamatan", [""] + kec_df["nama"].tolist())
else:
    kec_df = pd.DataFrame()

kategori = st.selectbox("Kategori POI", kategori_list, index=0)


# ==============================
# Tombol Query
# ==============================
if st.button("🔍 Cari & Simpan Data"):
    wilayah = kec_name if kec_name else (kab_name if kab_name else prov_name)
    if not wilayah:
        st.error("⚠️ Silakan pilih minimal Provinsi atau lebih spesifik (Kabupaten/Kota/Kecamatan).")
    else:
        with st.spinner(f"Mengunduh data POI {kategori} di {wilayah}..."):
            query = f"""
            [out:json][timeout:60];
            area["name"="{wilayah}"]->.searchArea;
            (
              node["amenity"="{kategori}"](area.searchArea);
              way["amenity"="{kategori}"](area.searchArea);
              relation["amenity"="{kategori}"](area.searchArea);
            );
            out center;
            """
            data = query_overpass(query)

            pois = []
            if data:
                for element in data.get('elements', []):
                    lat = element.get('lat')
                    lon = element.get('lon')
                    if lat is None and "center" in element:
                        lat = element["center"]["lat"]
                        lon = element["center"]["lon"]

                    pois.append({
                        "id": element['id'],
                        "lat": lat,
                        "lon": lon,
                        "name": element.get('tags', {}).get('name', ''),
                        "address": element.get('tags', {}).get('addr:full', ''),
                        "kategori": kategori
                    })

            if len(pois) == 0:
                st.session_state["pois_df"] = None
                st.warning("⚠️ Tidak ada data ditemukan untuk kategori & wilayah ini. Coba ganti input.")
            else:
                df = pd.DataFrame(pois)
                st.session_state["pois_df"] = df
                st.session_state["wilayah"] = wilayah
                st.session_state["kategori"] = kategori
                st.success(f"✅ Ditemukan {len(df)} POI di {wilayah}")


# ==============================
# Render hasil
# ==============================
if st.session_state["pois_df"] is not None:
    df = st.session_state["pois_df"]
    wilayah = st.session_state["wilayah"]
    kategori = st.session_state["kategori"]

    # 1. Tabel
    st.subheader("📊 Data POI")
    st.dataframe(df)

    # 2. Peta
    st.subheader("🗺️ Peta POI")
    m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=10)
    for _, row in df.iterrows():
        if pd.notna(row["lat"]) and pd.notna(row["lon"]):
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=row["name"] if row["name"] else kategori,
                tooltip=row["name"] if row["name"] else kategori
            ).add_to(m)
    st_folium(m, width=1500, height=700)

    # 3. Tombol download CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, "poi.csv", "text/csv")
