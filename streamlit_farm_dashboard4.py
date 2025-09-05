import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt

st.set_page_config(layout="wide")
st.title("🌱 Farm Monitoring Dashboard")

# --------------------------
# 1️⃣ Load Monitoring CSV
# --------------------------
monitoring_df = pd.read_csv("monitoring_data.csv", encoding='utf-8')
monitoring_df.columns = monitoring_df.columns.str.strip()
monitoring_df['Crop_id'] = monitoring_df['Crop_id'].astype(str).str.strip()
monitoring_df['date_observed'] = pd.to_datetime(
    monitoring_df['date_observed'], dayfirst=True, errors='coerce'
)
monitoring_df = monitoring_df.dropna(subset=['date_observed'])
monitoring_df['height_cm'] = pd.to_numeric(monitoring_df['height_cm'], errors='coerce')

# --------------------------
# 2️⃣ Load Planting Centroids
# --------------------------
planting_centroids = gpd.read_file("planting_centroids.geojson")
planting_centroids.columns = planting_centroids.columns.str.strip()
planting_centroids['id'] = planting_centroids['id'].astype(str).str.strip()
planting_centroids['Plant date'] = pd.to_datetime(
    planting_centroids['Plant date'], errors='coerce'
).dt.date

# --------------------------
# 3️⃣ Aggregate Monitoring Data
# --------------------------
agg_monitoring = monitoring_df.groupby('Crop_id').agg(
    avg_height=('height_cm', 'mean'),
    last_stage=('stage', 'last'),
    last_crop_health=('crop_health', 'last'),
    last_observed=('date_observed', 'max'),
    observations_count=('fid', 'count')
).reset_index()

# --------------------------
# 4️⃣ Merge with Planting Centroids
# --------------------------
merged_gdf = planting_centroids.merge(
    agg_monitoring,
    left_on='id',
    right_on='Crop_id',
    how='left'
)
# Rename 'Row ID' to 'Plot ID' for consistency
merged_gdf = merged_gdf.rename(columns={'Row ID': 'Plot ID'})

merged_gdf.fillna({
    'avg_height': 0,
    'last_stage': 'N/A',
    'last_crop_health': 'N/A',
    'observations_count': 0
}, inplace=True)

# ✅ Compute centroids for all geometries
merged_gdf['centroid'] = merged_gdf.geometry.centroid

# --------------------------
# 5️⃣ Sidebar: Menu & Filters
# --------------------------
menu_choice = st.sidebar.radio("Menu", ["Farm Monitoring", "Check Progress"])

with st.sidebar.expander("🔍 Filters", expanded=True):
    # Crop Class filter
    crop_classes = merged_gdf['Crop Class'].dropna().unique().tolist()
    selected_crop = st.selectbox("Select Crop Class", ["All"] + crop_classes)
    filtered_gdf = merged_gdf.copy()
    if selected_crop != "All":
        filtered_gdf = filtered_gdf[filtered_gdf['Crop Class'] == selected_crop]

    # Linked Crop Variety filter
    if selected_crop == "All":
        crop_varieties = merged_gdf['Crop Varie'].dropna().unique().tolist()
    else:
        crop_varieties = merged_gdf[merged_gdf['Crop Class'] == selected_crop]['Crop Varie'].dropna().unique().tolist()
    selected_variety = st.selectbox("Select Crop Varie", ["All"] + list(crop_varieties))
    if selected_variety != "All":
        filtered_gdf = filtered_gdf[filtered_gdf['Crop Varie'] == selected_variety]

    # Stage filter
    stages = filtered_gdf['last_stage'].dropna().unique().tolist()
    selected_stage = st.selectbox("Filter by Stage", ["All"] + list(stages))
    if selected_stage != "All":
        filtered_gdf = filtered_gdf[filtered_gdf['last_stage'] == selected_stage]

# --------------------------
# 6️⃣ Farm Monitoring Page
# --------------------------
if menu_choice == "Farm Monitoring":
    st.subheader("🌱 Farm Map")

    if not filtered_gdf.empty:
        farm_center = [filtered_gdf['centroid'].y.mean(), filtered_gdf['centroid'].x.mean()]
    else:
        farm_center = [0,0]

    # Map base selection
    base_map_options = {
        "OpenStreetMap": {"type": "builtin", "url": "OpenStreetMap", "attribution": "© OpenStreetMap contributors"},
        "CartoDB Dark": {"type": "builtin", "url": "CartoDB dark_matter", "attribution": "© CartoDB"},
        "Google Satellite": {"type": "custom", "url": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", "attribution": "© Google Maps"},
        "Google Hybrid": {"type": "custom", "url": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "attribution": "© Google Maps"}
    }
    selected_base_map = st.selectbox("Choose a base map:", list(base_map_options.keys()))
    chosen_map = base_map_options[selected_base_map]

    # Create Folium map
    if chosen_map["type"] == "builtin":
        m = folium.Map(location=farm_center, zoom_start=18, tiles=chosen_map["url"], attr=chosen_map["attribution"])
    else:
        m = folium.Map(location=farm_center, zoom_start=18, tiles=None)
        folium.TileLayer(
            tiles=chosen_map["url"],
            attr=chosen_map["attribution"],
            name=selected_base_map
        ).add_to(m)

    # Add markers
    for _, row in filtered_gdf.iterrows():
        lat = row['centroid'].y
        lon = row['centroid'].x
        popup_html = f"""
        <div style="width:300px">
            <strong>Plot ID:</strong> {row['Plot ID']}<br>
            <strong>Crop:</strong> {row['Crop Varie']}<br>
            <strong>Plant date:</strong> {row['Plant date']}<br>
            <strong>Block ID:</strong> {row['Block_ID']}<br>
            <strong>Crop Class:</strong> {row['Crop Class']}<br>
            <hr>
            <strong>Avg Height (cm):</strong> {row['avg_height']:.1f}<br>
            <strong>Crop Health:</strong> {row['last_crop_health']}<br>
            <strong>Stage Observed:</strong> {row['last_stage']}<br>
            <strong>Date Observed:</strong> {row['last_observed'].date() if pd.notnull(row['last_observed']) else 'N/A'}<br>
            <strong>Observations:</strong> {int(row['observations_count'])}
        </div>
        """

        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color="green",
            fill=True,
            fill_opacity=0.7,
            popup=popup_html
        ).add_to(m)

    st_folium(m, width=1000, height=500)

# --------------------------
# --------------------------
# 7️⃣ Check Progress Page
# --------------------------
import matplotlib.dates as mdates

if menu_choice == "Check Progress":
    st.subheader("📊 Crop Growth Over Time")

    # Get unique Plot IDs (grouped by name)
    plot_ids = merged_gdf['Plot ID'].dropna().unique().tolist()
    selected_plot = st.selectbox("Select Plot ID to track progress:", plot_ids)

    # Get corresponding Crop_id for selected plot
    crop_id = merged_gdf.loc[merged_gdf['Plot ID'] == selected_plot, 'id'].values[0]
    progress_df = monitoring_df[monitoring_df['Crop_id'] == str(crop_id)]

    if not progress_df.empty:
        # Aggregate by date_observed
        progress_agg = progress_df.groupby('date_observed').agg(
            avg_height=('height_cm', 'mean'),
            avg_crop_health=('crop_health', lambda x: x.mode()[0] if not x.mode().empty else 'N/A')
        ).reset_index()

        # Plotting
        fig, ax1 = plt.subplots(figsize=(8, 4))

        # Height plot
        ax1.plot(progress_agg['date_observed'], progress_agg['avg_height'], marker='o', label="Height (cm)")
        ax1.set_xlabel("Date Observed")
        ax1.set_ylabel("Height (cm)")
        ax1.legend(loc="upper left")

        # Format x-axis as date
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate()

        # Crop health on secondary axis
        ax2 = ax1.twinx()
        ax2.plot(progress_agg['date_observed'], progress_agg['avg_crop_health'], 'r--', label="Crop Health")
        ax2.set_ylabel("Crop Health")
        ax2.legend(loc="upper right")

        st.pyplot(fig)
    else:
        st.warning("No monitoring data available for this Plot ID.")

