import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="POI Downloader", layout="wide")
st.title("📍 POI Downloader dari OpenStreetMap (Gratis)")

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

# Ambil daftar provinsi dari OSM (admin_level=4)
@st.cache_data
def get_provinces():
    query = """
    [out:json][timeout:60];
    area["admin_level"="2"]["name"="Indonesia"]->.indo;
    relation(area.indo)["admin_level"="4"];
    out;
    """
    data = query_overpass(query)
    provs = []
    if data:
        for el in data.get("elements", []):
            provs.append(el.get("tags", {}).get("name"))
    return sorted(list(set(filter(None, provs))))

# Ambil daftar kabupaten/kota berdasarkan provinsi
def get_regencies(provinsi):
    query = f"""
    [out:json][timeout:60];
    relation["admin_level"="4"]["name"="{provinsi}"]->.prov;
    relation(area.prov)["admin_level"="6"];
    out;
    """
    data = query_overpass(query)
    regs = []
    if data:
        for el in data.get("elements", []):
            regs.append(el.get("tags", {}).get("name"))
    return sorted(list(set(filter(None, regs))))

# Ambil daftar kecamatan berdasarkan kabupaten/kota
def get_districts(regency):
    query = f"""
    [out:json][timeout:60];
    relation["admin_level"="6"]["name"="{regency}"]->.reg;
    relation(area.reg)["admin_level"="8"];
    out;
    """
    data = query_overpass(query)
    dists = []
    if data:
        for el in data.get("elements", []):
            dists.append(el.get("tags", {}).get("name"))
    return sorted(list(set(filter(None, dists))))

# --- Inisialisasi session state untuk simpan hasil ---
if "pois_df" not in st.session_state:
    st.session_state["pois_df"] = None
if "wilayah" not in st.session_state:
    st.session_state["wilayah"] = None
if "kategori" not in st.session_state:
    st.session_state["kategori"] = None

# Dropdown berjenjang
provinsi = st.selectbox("Pilih Provinsi", [""] + get_provinces())
kabupaten = ""
kecamatan = ""

if provinsi:
    kabupaten = st.selectbox("Pilih Kabupaten/Kota", [""] + get_regencies(provinsi))
if kabupaten:
    kecamatan = st.selectbox("Pilih Kecamatan", [""] + get_districts(kabupaten))

kategori = st.selectbox("Kategori POI", kategori_list, index=0)

if st.button("🔍 Cari & Simpan Data"):
    wilayah = kecamatan if kecamatan else (kabupaten if kabupaten else provinsi)
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

# --- Render hasil tersimpan ---
if st.session_state["pois_df"] is not None:
    df = st.session_state["pois_df"]
    wilayah = st.session_state["wilayah"]
    kategori = st.session_state["kategori"]

    # 1. Tabel
    st.subheader("📊 Data POI")
    st.dataframe(df)

    # 2. Peta
    st.subheader("🗺️ Peta POI")
    m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=12)
    for _, row in df.iterrows():
        if pd.notna(row["lat"]) and pd.notna(row["lon"]):
            folium.Marker(
                [row["lat"], row["lon"]],
                popup=row["name"] if row["name"] else kategori,
                tooltip=row["name"] if row["name"] else kategori
            ).add_to(m)
    st_folium(m, width=1000, height=700)

    # 3. Tombol download CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", csv, "poi.csv", "text/csv")
