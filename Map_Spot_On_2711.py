import csv
import streamlit as st
import folium
from streamlit_folium import st_folium
import os


def get_icon_color(location_type): #different colours for icons, based on type of spot
    color_map = {
        'Nightclub': 'red',
        'Bar': 'blue',
        'Restaurant': 'green'
    }
    return color_map.get(location_type, 'gray')

def process_csv_file(file_path): #separated processing of the CSV files with rows: Name, Coordinates, Type
    data = []
    try:
        with open(file_path, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    latitude, longitude = map(str.strip, row['Coordinates'].split(","))
                    data.append({
                        'name': row['ï»¿Name'],
                        'type': row['Type'],
                        'latitude': float(latitude),
                        'longitude': float(longitude)
                    })
                except (KeyError, ValueError) as e:
                    st.error(f"Error processing row: {row} - {e}")
    except FileNotFoundError:
        st.error(f"File not found: {file_path}")
    except Exception as e:
        st.error(f"Error reading file {file_path}: {e}")
    
    return data if data else None

def create_map_with_feature_groups(csv_files): #create folium feature group for the map, based on spot lists from CSV
    SG_CENTER = [47.4245, 9.3767]
    map = folium.Map(location=SG_CENTER, zoom_start=16)

    for csv_file in csv_files:
        feature_group = folium.FeatureGroup(name=os.path.splitext(os.path.basename(csv_file))[0]) #creates the name of the folium feature group based on the CSV file name
        data = process_csv_file(csv_file)
        if data:
            for spot in data:
                location = (spot['latitude'], spot['longitude'])
                folium.Marker(
                    location,
                    popup=f"{spot['name']} ({spot['type']})",
                    icon=folium.Icon(color=get_icon_color(spot['type'])),
                ).add_to(feature_group)
            feature_group.add_to(map)
        else:
            st.error(f"No valid data in file: {csv_file}") #error check to see if the data in the CSV file is in the correct format

    folium.LayerControl().add_to(map) #adds a menu on the map to switch between layers
    return map

# When a new CSV file from the lists tabs gets created, it needs to go in here -> don't know yet how to make it happen
csv_files = [
    'StGallen_Locations_Test.csv',
    # Add more CSV files here
]

map_SG = create_map_with_feature_groups(csv_files)

st.header('Spot On Map St.Gallen')
st_folium(map_SG)

st.logo('Spot_On_Logo.png', size= 'medium')