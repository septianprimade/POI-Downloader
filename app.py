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

# Dropdown berjenjang
provinsi = st.selectbox("Pilih Provinsi", [""] + get_provinces())
kabupaten = ""
kecamatan = ""

if provinsi:
    kabupaten = st.selectbox("Pilih Kabupaten/Kota", [""] + get_regencies(provinsi))
if kabupaten:
    kecamatan = st.selectbox("Pilih Kecamatan", [""] + get_districts(kabupaten))

kategori = st.selectbox("Kategori POI", kategori_list, index=0)

if st.button("🔍 Cari & Unduh Data"):
    wilayah = kecamatan if kecamatan else (kabupaten if kabupaten else provinsi)
    if not wilayah:
        st.error("⚠️ Silakan pilih minimal Provinsi atau lebih spesifik (Kabupaten/Kota/Kecamatan).")
        st.stop()

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

        if data is None:
            st.error("❌ Semua server Overpass gagal merespons. Coba ulangi nanti atau gunakan wilayah lebih kecil.")
            st.stop()

        pois = []
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
            st.warning("⚠️ Tidak ada data ditemukan untuk kategori & wilayah ini. Coba ganti input.")
        else:
            df = pd.DataFrame(pois)
            st.success(f"✅ Ditemukan {len(df)} POI di {wilayah}")

            # 1. Tabel
            st.dataframe(df)

            # 2. Peta
            m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=12)
            for _, row in df.iterrows():
                if pd.notna(row["lat"]) and pd.notna(row["lon"]):
                    folium.Marker(
                        [row["lat"], row["lon"]],
                        popup=row["name"] if row["name"] else kategori,
                        tooltip=row["name"] if row["name"] else kategori
                    ).add_to(m)
            st_folium(m, width=700, height=500)

            # 3. Download CSV (lengkap dengan koordinat)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, "poi.csv", "text/csv")
