import streamlit as st
import requests
import pandas as pd
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="POI Downloader", layout="wide")

st.title("📍 POI Downloader dari OpenStreetMap (Gratis)")

# Input dari user
wilayah = st.text_input("Nama Wilayah Administrasi", "Jakarta")
kategori = st.text_input("Kategori POI (contoh: restaurant, hospital, school)", "restaurant")

if st.button("🔍 Cari & Unduh Data"):
    with st.spinner("Mengunduh data dari OSM..."):
        overpass_url = "http://overpass-api.de/api/interpreter"
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
        response = requests.get(overpass_url, params={'data': query})
        data = response.json()

        pois = []
        for element in data['elements']:
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
            st.warning("⚠️ Tidak ada data ditemukan untuk kategori & wilayah ini.")
        else:
            df = pd.DataFrame(pois)
            st.success(f"✅ Ditemukan {len(df)} POI di {wilayah}")

            # Tampilkan tabel
            st.dataframe(df)

            # Download CSV
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", csv, "poi.csv", "text/csv")

            # Peta interaktif
            m = folium.Map(location=[df["lat"].mean(), df["lon"].mean()], zoom_start=12)
            for _, row in df.iterrows():
                folium.Marker(
                    [row["lat"], row["lon"]],
                    popup=row["name"] if row["name"] else kategori,
                    tooltip=row["name"] if row["name"] else kategori
                ).add_to(m)

            st_folium(m, width=700, height=500)
