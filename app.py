import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

# --- Konfigurasi Halaman ---
st.set_page_config(page_title="POI Downloader", layout="wide")
st.title("📍 POI Downloader dari OpenStreetMap + BPS")

# --- Daftar kategori umum (amenity OSM) ---
kategori_list = [
    "restaurant", "cafe", "fast_food", "bar",
    "hospital", "clinic", "pharmacy",
    "school", "university", "college",
    "bank", "atm", "post_office",
    "fuel", "parking", "supermarket", "marketplace",
    "bus_station", "train_station", "airport"
]

# --- Server Overpass alternatif ---
overpass_servers = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter"
]

# --- Base API BPS ---
BPS_BASE = "https://sig.bps.go.id/rest-bridging"

# --- Fungsi Query Overpass ---
def query_overpass(query):
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

# --- Fungsi Normalisasi Kolom JSON BPS ---
def normalize_bps_df(data):
    df = pd.DataFrame(data)
    if "nama" not in df.columns:
        if "value" in df.columns:
            df = df.rename(columns={"value": "nama"})
        elif "label" in df.columns:
            df = df.rename(columns={"label": "nama"})
    if "kode" not in df.columns and "kode_bps" in df.columns:
        df = df.rename(columns={"kode_bps": "kode"})
    return df

# --- Ambil Wilayah BPS ---
@st.cache_data
def get_provinces():
    url = f"{BPS_BASE}/getwilayah?level=provinsi"
    data = requests.get(url, timeout=60).json()
    df = normalize_bps_df(data)
    return df[["kode", "nama"]]

@st.cache_data
def get_regencies(kode_prov):
    url = f"{BPS_BASE}/getwilayah?level=kabupaten&parent={kode_prov}"
    data = requests.get(url, timeout=60).json()
    df = normalize_bps_df(data)
    return df[["kode", "nama"]]

@st.cache_data
def get_districts(kode_kab):
    url = f"{BPS_BASE}/getwilayah?level=kecamatan&parent={kode_kab}"
    data = requests.get(url, timeout=60).json()
    df = normalize_bps_df(data)
    return df[["kode", "nama"]]

# --- Session State ---
if "pois_df" not in st.session_state:
    st.session_state["pois_df"] = None
if "wilayah" not in st.session_state:
    st.session_state["wilayah"] = None
if "kategori" not in st.session_state:
    st.session_state["kategori"] = None

# --- Dropdown Berjenjang ---
prov_df = get_provinces()
prov_name = st.selectbox("Pilih Provinsi", [""] + prov_df["nama"].tolist())
prov_code = prov_df.loc[prov_df["nama"] == prov_name, "kode"].values[0] if prov_name else ""

kab_name, kab_code = "", ""
kec_name, kec_code = "", ""

if prov_code:
    kab_df = get_regencies(prov_code)
    kab_name = st.selectbox("Pilih Kabupaten/Kota", [""] + kab_df["nama"].tolist())
    if kab_name:
        kab_code = kab_df.loc[kab_df["nama"] == kab_name, "kode"].values[0]

if kab_code:
    kec_df = get_districts(kab_code)
    kec_name = st.selectbox("Pilih Kecamatan", [""] + kec_df["nama"].tolist())
    if kec_name:
        kec_code = kec_df.loc[kec_df["nama"] == kec_name, "kode"].values[0]

kategori = st.selectbox("Kategori POI", kategori_list, index=0)

# --- Tombol Query ---
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

# --- Render Hasil ---
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
