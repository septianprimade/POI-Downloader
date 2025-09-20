import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

st.set_page_config(page_title="POI Downloader v5", layout="wide")

st.title("📍 POI Downloader (OSM + Overpass API)")
st.write("Unduh data Point of Interest (POI) berdasarkan kategori & wilayah administrasi dari OpenStreetMap.")

# --- Dropdown kategori POI ---
kategori_options = ["hospital", "school", "fuel", "restaurant", "bank", "atm", "place_of_worship"]
kategori = st.selectbox("Pilih kategori POI:", kategori_options, index=0)

# --- Dropdown wilayah (contoh sederhana, bisa diperluas) ---
provinsi_options = {
    "DKI Jakarta": {
        "Jakarta Selatan": ["Kebayoran Baru", "Mampang Prapatan", "Pasar Minggu"],
        "Jakarta Pusat": ["Gambir", "Menteng", "Tanah Abang"],
    },
    "Jawa Barat": {
        "Bandung": ["Coblong", "Sukajadi", "Lengkong"],
        "Bogor": ["Bogor Tengah", "Bogor Utara", "Bogor Selatan"],
    },
}
provinsi = st.selectbox("Pilih Provinsi:", list(provinsi_options.keys()))
kabupaten = st.selectbox("Pilih Kabupaten/Kota:", list(provinsi_options[provinsi].keys()))
kecamatan = st.selectbox("Pilih Kecamatan:", provinsi_options[provinsi][kabupaten])

wilayah = f"{kecamatan}, {kabupaten}, {provinsi}"

# --- Inisialisasi session_state ---
if "pois_df" not in st.session_state:
    st.session_state["pois_df"] = None

# --- Fungsi query Overpass ---
def ambil_data_poi(kategori, wilayah):
    query = f"""
    [out:json];
    area["name"="{wilayah}"]->.searchArea;
    (
      node["amenity"="{kategori}"](area.searchArea);
      way["amenity"="{kategori}"](area.searchArea);
      relation["amenity"="{kategori}"](area.searchArea);
    );
    out center;
    """
    url = "http://overpass-api.de/api/interpreter"
    try:
        response = requests.get(url, params={"data": query}, timeout=60)
        response.raise_for_status()
        data = response.json()
        pois = []
        for el in data.get("elements", []):
            lat, lon = None, None
            if el["type"] == "node":
                lat, lon = el.get("lat"), el.get("lon")
            elif "center" in el:
                lat, lon = el["center"].get("lat"), el["center"].get("lon")
            pois.append({
                "id": el.get("id"),
                "name": el.get("tags", {}).get("name"),
                "kategori": kategori,
                "lat": lat,
                "lon": lon,
                "alamat": el.get("tags", {}).get("addr:full"),
            })
        return pd.DataFrame(pois)
    except Exception as e:
        st.error(f"Gagal mengambil data dari Overpass API: {e}")
        return pd.DataFrame()

# --- Tombol pencarian ---
if st.button("🔍 Cari & Simpan Data"):
    df = ambil_data_poi(kategori, wilayah)
    if not df.empty:
        st.session_state["pois_df"] = df
        st.success(f"Ditemukan {len(df)} data POI di {wilayah}.")
    else:
        st.session_state["pois_df"] = None
        st.warning("⚠️ Tidak ada data ditemukan untuk kategori & wilayah ini.")

# --- Render hasil ---
if st.session_state["pois_df"] is not None:
    df = st.session_state["pois_df"]

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
                popup=row["name"] if row["name"] else row["kategori"],
                tooltip=row["name"] if row["name"] else row["kategori"]
            ).add_to(m)
    st_folium(m, width=700, height=500)

    # 3. Tombol download
    st.subheader("⬇️ Unduh Data")
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "poi.csv", "text/csv")
