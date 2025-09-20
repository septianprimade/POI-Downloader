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

wilayah = st.text_input("Nama Wilayah Administrasi", "Jakarta")
kategori = st.selectbox("Kategori POI", kategori_list, index=0)

# Server Overpass alternatif
overpass_servers = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter"
]

def query_overpass(query):
    """Coba query ke beberapa server sampai berhasil"""
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

if st.button("🔍 Cari & Unduh Data"):
    with st.spinner("Mengunduh data dari OSM..."):
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

            # Tabel
            st.dataframe(df)

            # Download CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, "poi.csv", "text/csv")

            # Peta
            m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=12)
            for _, row in df.iterrows():
                if pd.notna(row["lat"]) and pd.notna(row["lon"]):
                    folium.Marker(
                        [row["lat"], row["lon"]],
                        popup=row["name"] if row["name"] else kategori,
                        tooltip=row["name"] if row["name"] else kategori
                    ).add_to(m)

            st_folium(m, width=700, height=500)
