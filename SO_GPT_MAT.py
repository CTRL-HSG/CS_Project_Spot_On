import streamlit as st
import sqlite3
import hashlib
import os
import base64
import json
import pandas as pd
import matplotlib.pyplot as plt
import folium
from streamlit_folium import st_folium

# =============================
# Configuration
# =============================
UPLOAD_FOLDER = "uploaded_images"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

CSV_FILE_PATH = "final_CSV.csv"  # Your CSV with Name,Coordinates,Type
CSV_SEPARATOR = ";"  # Update if your file uses a different delimiter

# =============================
# Database and User Management
# =============================

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            activities TEXT,
            bio TEXT DEFAULT '',
            profile_image TEXT DEFAULT '',
            liked_lists TEXT DEFAULT '',
            saved_lists TEXT DEFAULT '',
            user_created_lists TEXT DEFAULT ''
        )
    """)
    columns = [row[1] for row in cursor.execute("PRAGMA table_info(users);")]
    if 'liked_lists' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN liked_lists TEXT DEFAULT ''")
    if 'saved_lists' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN saved_lists TEXT DEFAULT ''")
    if 'user_created_lists' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN user_created_lists TEXT DEFAULT ''")
    conn.commit()
    conn.close()

def save_user(username, password, activities, bio='', profile_image=''):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password, activities, bio, profile_image) VALUES (?, ?, ?, ?, ?)",
        (username, password, ",".join(activities), bio, profile_image)
    )
    conn.commit()
    conn.close()

def authenticate_user(username, password):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT password FROM users WHERE username = ?", (username,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0] == hash_password(password):
        return True
    return False

def get_user_profile(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT activities, bio, profile_image, liked_lists, saved_lists, user_created_lists 
        FROM users WHERE username = ?
    """, (username,))
    result = cursor.fetchone()
    conn.close()
    if result:
        activities, bio, profile_image, liked_lists, saved_lists, user_created_lists = result
        return {
            "activities": activities.split(",") if activities else [],
            "bio": bio,
            "profile_image": profile_image,
            "liked_lists": json.loads(liked_lists) if liked_lists else {},
            "saved_lists": json.loads(saved_lists) if saved_lists else {},
            "user_created_lists": json.loads(user_created_lists) if user_created_lists else {}
        }
    return None

def update_user_profile(username, new_username=None, new_password=None, new_bio=None, new_profile_image=None,
                        new_activities=None, new_liked_lists=None, new_saved_lists=None, new_user_created_lists=None):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    if new_username:
        cursor.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, username))
    if new_password:
        cursor.execute("UPDATE users SET password = ? WHERE username = ?", (new_password, username))
    if new_bio is not None:
        cursor.execute("UPDATE users SET bio = ? WHERE username = ?", (new_bio, username))
    if new_profile_image is not None:
        cursor.execute("UPDATE users SET profile_image = ? WHERE username = ?", (new_profile_image, username))
    if new_activities is not None:
        cursor.execute("UPDATE users SET activities = ? WHERE username = ?", (",".join(new_activities), username))
    if new_liked_lists is not None:
        cursor.execute("UPDATE users SET liked_lists = ? WHERE username = ?", (json.dumps(new_liked_lists), username))
    if new_saved_lists is not None:
        cursor.execute("UPDATE users SET saved_lists = ? WHERE username = ?", (json.dumps(new_saved_lists), username))
    if new_user_created_lists is not None:
        cursor.execute("UPDATE users SET user_created_lists = ? WHERE username = ?", (json.dumps(new_user_created_lists), username))

    conn.commit()
    conn.close()

def delete_user(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users")
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_base64_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode()

init_db()

# =============================
# Load Locations from CSV
# =============================

def load_locations_from_csv(file_path, sep=","):
    #error message for file not found
    if not os.path.exists(file_path):
        st.warning(f"CSV file not found at: {file_path}")
        return pd.DataFrame(columns=["Name", "Latitude", "Longitude", "Type"])

    # Attempt to read and skip bad lines if any
    data = pd.read_csv(file_path, sep=CSV_SEPARATOR, dtype=str, on_bad_lines='skip')

    #error message if expecting columns: Name, Coordinates, Type wrongly named/not findable
    if not {"Name", "Coordinates", "Type"}.issubset(set(data.columns)):
        st.warning("CSV file is missing required columns: Name, Coordinates, Type")
        return pd.DataFrame(columns=["Name", "Latitude", "Longitude", "Type"])

    # Parse Coordinates column to extract Latitude and Longitude
    def parse_coordinates(coord_str):
        # coord_str expected like "47.4245,9.3767"
        # Handle cases if quotes or spaces
        coord_str = coord_str.strip().replace('"','')
        parts = coord_str.split(",")
        if len(parts) == 2:
            try:
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
                return lat, lon
            except ValueError:
                return None, None
        return None, None

    data["Latitude"] = None
    data["Longitude"] = None

    for i, row in data.iterrows():
        lat, lon = parse_coordinates(row["Coordinates"])
        data.at[i, "Latitude"] = lat
        data.at[i, "Longitude"] = lon

    # Drop rows with invalid coords
    data = data.dropna(subset=["Latitude", "Longitude"])

    # Final cleaned dataframe
    processed_locations = data[["Name", "Latitude", "Longitude", "Type"]]
    return processed_locations

# Load CSV data
locations_df = load_locations_from_csv(CSV_FILE_PATH, sep=CSV_SEPARATOR)

if "logo_base64" not in st.session_state:
    try:
        st.session_state["logo_base64"] = get_base64_image("SpotOn_Logo.jpg")
    except FileNotFoundError:
        st.warning("Logo file not found.")
        st.session_state["logo_base64"] = None

def sync_user_data_to_db():
    if "logged_in_user" in st.session_state:
        username = st.session_state["logged_in_user"]
        liked_lists = st.session_state.get("liked_flags", {})
        saved_lists = st.session_state.get("saved_lists", {})
        user_created_lists = st.session_state.get("user_created_lists", {})
        update_user_profile(
            username,
            new_liked_lists=liked_lists,
            new_saved_lists=saved_lists,
            new_user_created_lists=user_created_lists
        )

def load_user_data_from_db(username):
    user_profile = get_user_profile(username)
    if user_profile:
        st.session_state.liked_flags = user_profile["liked_lists"]
        st.session_state.saved_lists = user_profile["saved_lists"]
        st.session_state.user_created_lists = user_profile["user_created_lists"]
        if "list_likes" not in st.session_state:
            st.session_state.list_likes = {}
        for k, v in st.session_state.user_created_lists.items():
            if k not in st.session_state.list_likes:
                st.session_state.list_likes[k] = v.get("likes", 0)
            if k not in st.session_state.liked_flags:
                st.session_state.liked_flags[k] = False
    else:
        st.session_state.liked_flags = {}
        st.session_state.saved_lists = {}
        st.session_state.user_created_lists = {}
        st.session_state.list_likes = {}

def get_all_user_created_lists():
    all_users = get_all_users()
    combined_user_lists = {}
    for user in all_users:
        profile = get_user_profile(user)
        if profile and profile["user_created_lists"]:
            for lst_name, lst_data in profile["user_created_lists"].items():
                combined_user_lists[lst_name] = lst_data
    return combined_user_lists

def generate_liked_locations_csv():
    liked_locations = []
    all_lists = get_all_user_created_lists()
    if "liked_flags" in st.session_state:
        for list_name, data in all_lists.items():
            if st.session_state.liked_flags.get(list_name, False):
                liked_locations.extend([
                    {"Name": loc["name"], "Type": loc["type"]}
                    for loc in data["locations"]
                ])
    liked_df = pd.DataFrame(liked_locations)
    file_path = "liked_locations.csv"
    if not liked_df.empty:
        liked_df.to_csv(file_path, index=False)
    else:
        if os.path.exists(file_path):
            os.remove(file_path)
        file_path = None
    return file_path

def save_list_as_csv(list_name):
    all_lists = get_all_user_created_lists()
    locations = all_lists[list_name]["locations"]
    saved_df = pd.DataFrame(locations)
    file_path = f"{list_name.replace(' ', '_')}_saved.csv"
    saved_df.to_csv(file_path, index=False)
    st.session_state.saved_lists[list_name] = file_path
    sync_user_data_to_db()
    return file_path

def generate_saved_lists_csv():
    saved_lists = []
    all_lists = get_all_user_created_lists()
    if "saved_lists" in st.session_state:
        for list_name, file_path in st.session_state.saved_lists.items():
            if list_name in all_lists:
                locations = all_lists[list_name]["locations"]
                for loc in locations:
                    saved_lists.append({
                        "List Name": list_name,
                        "Name": loc["name"],
                        "Type": loc["type"]
                    })
    saved_df = pd.DataFrame(saved_lists)
    file_path = "saved_lists.csv"
    if not saved_df.empty:
        saved_df.to_csv(file_path, index=False)
    else:
        if os.path.exists(file_path):
            os.remove(file_path)
            file_path = None
    return file_path

def delete_created_list(list_name):
    if "logged_in_user" in st.session_state and "user_created_lists" in st.session_state:
        if list_name in st.session_state.user_created_lists:
            del st.session_state.user_created_lists[list_name]
            if "list_likes" in st.session_state and list_name in st.session_state.list_likes:
                del st.session_state.list_likes[list_name]
            if "liked_flags" in st.session_state and list_name in st.session_state.liked_flags:
                del st.session_state.liked_flags[list_name]
            if "saved_lists" in st.session_state and list_name in st.session_state.saved_lists:
                del st.session_state.saved_lists[list_name]
            sync_user_data_to_db()

def edit_created_list(original_name, new_name, new_locations):
    updated_locations = []
    for loc in new_locations:
        loc_name = loc["name"]
        loc_type = loc["type"]
        match = locations_df[(locations_df["Name"] == loc_name) & (locations_df["Type"] == loc_type)]
        if not match.empty:
            lat = float(match.iloc[0]["Latitude"])
            lon = float(match.iloc[0]["Longitude"])
            updated_locations.append({"name": loc_name, "type": loc_type, "latitude": lat, "longitude": lon})

    if "logged_in_user" in st.session_state and "user_created_lists" in st.session_state:
        if original_name in st.session_state.user_created_lists:
            old_data = st.session_state.user_created_lists[original_name]
            del st.session_state.user_created_lists[original_name]

            st.session_state.user_created_lists[new_name] = {
                "likes": old_data.get("likes", 0),
                "locations": updated_locations
            }

            if original_name in st.session_state.list_likes:
                st.session_state.list_likes[new_name] = st.session_state.list_likes[original_name]
                del st.session_state.list_likes[original_name]

            if original_name in st.session_state.liked_flags:
                st.session_state.liked_flags[new_name] = st.session_state.liked_flags[original_name]
                del st.session_state.liked_flags[original_name]

            if original_name in st.session_state.saved_lists:
                st.session_state.saved_lists[new_name] = st.session_state.saved_lists[original_name]
                del st.session_state.saved_lists[original_name]

            sync_user_data_to_db()

def get_emoji_for_type(place_type):
    return {"Nightclub": "🕺", "Restaurant": "🍴", "Bar": "🍸"}.get(place_type, "❓")

def get_icon_color(location_type): 
    color_map = {
        'Nightclub': 'red',
        'Bar': 'blue',
        'Restaurant': 'green'
    }
    return color_map.get(location_type, 'gray')

def process_csv_file(file_path):
    data = []
    try:
        reader = pd.read_csv(file_path, sep=CSV_SEPARATOR, on_bad_lines='skip')
        # Expect columns: Name, Coordinates, Type
        if {'Name', 'Coordinates', 'Type'}.issubset(reader.columns):
            for idx, row in reader.iterrows():
                coordinates_str = str(row['Coordinates']).strip().replace('"','')
                parts = coordinates_str.split(",")
                if len(parts) == 2:
                    try:
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                        data.append({
                            'name': row['Name'],
                            'type': row['Type'],
                            'latitude': lat,
                            'longitude': lon
                        })
                    except ValueError:
                        continue
                else:
                    continue
        else:
            st.warning("CSV file is missing required columns: Name, Coordinates, Type")
    except FileNotFoundError:
        st.error(f"File not found: {file_path}")
    except Exception as e:
        st.error(f"Error reading file {file_path}: {e}")
    
    return data if data else None

def create_map_with_feature_groups(csv_files, user_lists=None):
    SG_CENTER = [47.4245, 9.3767]
    map_obj = folium.Map(location=SG_CENTER, zoom_start=16)

    # Add CSV-based feature groups
    for csv_file in csv_files:
        feature_group = folium.FeatureGroup(name=os.path.splitext(os.path.basename(csv_file))[0])
        data = process_csv_file(csv_file)
        if data:
            for spot in data:
                folium.Marker(
                    [spot['latitude'], spot['longitude']],
                    popup=f"{spot['name']} ({spot['type']})",
                    icon=folium.Icon(color=get_icon_color(spot['type'])),
                ).add_to(feature_group)
            feature_group.add_to(map_obj)
        else:
            st.error(f"No valid data in file: {csv_file}")

    # Add user-created lists as feature groups
    if user_lists:
        for list_name, list_data in user_lists.items():
            user_feature_group = folium.FeatureGroup(name=f"User List: {list_name}")
            for loc in list_data["locations"]:
                folium.Marker(
                    [loc['latitude'], loc['longitude']],
                    popup=f"{loc['name']} ({loc['type']})",
                    icon=folium.Icon(color=get_icon_color(loc['type']))
                ).add_to(user_feature_group)
            user_feature_group.add_to(map_obj)

    folium.LayerControl().add_to(map_obj)
    return map_obj

def display_map():
    map_SG = create_map_with_feature_groups(csv_files=csv_files, user_lists=all_user_lists)
    st_folium(map_SG)

# Sidebar
st.sidebar.title("Navigation")
if "logged_in_user" in st.session_state:
    if st.sidebar.button("Logout"):
        del st.session_state["logged_in_user"]
        for key in ["liked_flags", "saved_lists", "user_created_lists", "list_likes"]:
            if key in st.session_state:
                del st.session_state[key]
        st.sidebar.success("You have been logged out.")
else:
    options = st.sidebar.radio("Account", ["Login", "Register"])
    if options == "Login":
        st.sidebar.write("### Login")
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type="password")
        if st.sidebar.button("Login"):
            if authenticate_user(username, password):
                st.session_state["logged_in_user"] = username
                load_user_data_from_db(username)
                st.sidebar.success(f"Welcome, {username}!")
            else:
                st.sidebar.error("Invalid credentials. Please try again.")
    elif options == "Register":
        st.sidebar.write("### Register")
        reg_username = st.sidebar.text_input("New Username")
        reg_password = st.sidebar.text_input("New Password", type="password")
        reg_activities = st.sidebar.multiselect(
            "Select Activities", 
            [
                "Sightseeing", "Museum visits", "Art galleries", "Shopping",
                "Coffee tasting", "Nightlife (clubs/bars)", "Local food tasting",
                "Street art tours", "Live music events", "Movie nights", "Escape rooms",
                "Rooftop bars", "City park picnics", "Biking tours", "Historic tours",
                "Photography walks", "Yoga classes", "Cooking workshops",
                "Wine or craft beer tasting", "Theater performances"
            ]
        )
        reg_bio = st.sidebar.text_area("Add a short bio (optional)")
        reg_uploaded_image = st.sidebar.file_uploader("Upload Profile Picture (Optional)")
        if reg_uploaded_image:
            profile_image_path = os.path.join(UPLOAD_FOLDER, reg_uploaded_image.name)
            with open(profile_image_path, "wb") as f:
                f.write(reg_uploaded_image.getbuffer())
        else:
            profile_image_path = ""
        if st.sidebar.button("Register"):
            if not reg_username or not reg_password or not reg_activities:
                st.sidebar.error("Please fill in all required fields: Username, Password, and Activities.")
            else:
                try:
                    save_user(reg_username, hash_password(reg_password), reg_activities, reg_bio, profile_image_path)
                    st.sidebar.success("Registration successful! Please log in.")
                except sqlite3.IntegrityError:
                    st.sidebar.error("Username already exists. Please choose another.")

# Main Tabs
tab1, tab2, tab3 = st.tabs(["Profile", "Map", "Popular Locations"])

with tab1:
    st.header("Profile")
    if "logged_in_user" not in st.session_state:
        st.info("Please log in to view and edit your profile.")
    else:
        username = st.session_state["logged_in_user"]
        user_profile = get_user_profile(username)
        if user_profile:
            st.subheader("My Profile")
            if user_profile["profile_image"] and os.path.exists(user_profile["profile_image"]):
                st.image(user_profile["profile_image"], caption="Your Profile Picture", width=100)
            else:
                st.write("No profile picture uploaded.")
            st.write("**Bio:**")
            st.write(user_profile["bio"] or "No bio provided.")
            st.write("**Activities:**")
            st.write(", ".join(user_profile["activities"]) or "No activities selected.")

            all_lists_combined = get_all_user_created_lists()

            # Liked Lists
            st.write("**Liked Lists:**")
            liked_lists = [lst for lst, liked in user_profile["liked_lists"].items() if liked]
            if liked_lists:
                for lst_name in liked_lists:
                    with st.expander(lst_name, expanded=False):
                        if lst_name in all_lists_combined:
                            for loc in all_lists_combined[lst_name]["locations"]:
                                st.markdown(f"- **{loc['name']}** {get_emoji_for_type(loc['type'])}")
                        else:
                            st.write("No details available.")
            else:
                st.write("No liked lists.")

            # Saved Lists
            st.write("**Saved Lists:**")
            if user_profile["saved_lists"]:
                for lst_name in user_profile["saved_lists"].keys():
                    with st.expander(lst_name, expanded=False):
                        if lst_name in all_lists_combined:
                            for loc in all_lists_combined[lst_name]["locations"]:
                                st.markdown(f"- **{loc['name']}** {get_emoji_for_type(loc['type'])}")
                        else:
                            st.write("No details available.")
            else:
                st.write("No saved lists.")

            # Created Lists
            st.write("**Your Created Lists:**")
            if user_profile["user_created_lists"]:
                for lst_name, lst_data in user_profile["user_created_lists"].items():
                    with st.expander(lst_name, expanded=False):
                        if lst_name in all_lists_combined:
                            st.write("**Locations:**")
                            for loc in all_lists_combined[lst_name]["locations"]:
                                st.markdown(f"- **{loc['name']}** {get_emoji_for_type(loc['type'])}")

                            st.write("---")
                            if f"show_edit_{lst_name}" not in st.session_state:
                                st.session_state[f"show_edit_{lst_name}"] = False
                            if st.button("Edit List", key=f"edit_button_{lst_name}"):
                                st.session_state[f"show_edit_{lst_name}"] = True
                            if st.session_state[f"show_edit_{lst_name}"]:
                                st.write("**Edit List**")
                                new_name = st.text_input("New List Name", value=lst_name)

                                # Use locations from CSV for selection
                                if not locations_df.empty:
                                    all_possible_locations = [
                                        f"{row['Name']} ({row['Type']})" for idx, row in locations_df.iterrows()
                                    ]
                                    current_locations = [f"{loc['name']} ({loc['type']})" for loc in all_lists_combined[lst_name]["locations"]]

                                    new_selected_locations = st.multiselect(
                                        "Select Locations",
                                        options=all_possible_locations,
                                        default=current_locations
                                    )
                                    if st.button("Save Changes", key=f"save_changes_{lst_name}"):
                                        updated_locations = [
                                            {"name": loc.split(" (")[0], "type": loc.split(" (")[1].replace(")", "")}
                                            for loc in new_selected_locations
                                        ]
                                        edit_created_list(lst_name, new_name, updated_locations)
                                        st.success("List updated successfully!")
                                        st.rerun()
                                else:
                                    st.write("No locations available to select.")

                            if st.button("Delete List", key=f"delete_{lst_name}"):
                                delete_created_list(lst_name)
                                st.success("List deleted successfully!")
                                st.rerun()
                        else:
                            st.write("No details available.")
            else:
                st.write("You haven't created any lists yet.")

            # Edit Profile
            with st.expander("Edit Profile"):
                new_username = st.text_input("New Username", value=username)
                new_password = st.text_input("New Password", type="password")
                new_bio = st.text_area("Bio", value=user_profile.get("bio", ""))
                uploaded_image = st.file_uploader("Upload Profile Picture (Optional)")
                if uploaded_image:
                    profile_image_path = os.path.join(UPLOAD_FOLDER, uploaded_image.name)
                    with open(profile_image_path, "wb") as f:
                        f.write(uploaded_image.getbuffer())
                else:
                    profile_image_path = user_profile.get("profile_image", "")

                updated_activities = st.multiselect(
                    "Update Activities",
                    [
                        "Sightseeing", "Museum visits", "Art galleries", "Shopping",
                        "Coffee tasting", "Nightlife (clubs/bars)", "Local food tasting",
                        "Street art tours", "Live music events", "Movie nights", "Escape rooms",
                        "Rooftop bars", "City park picnics", "Biking tours", "Historic tours",
                        "Photography walks", "Yoga classes", "Cooking workshops",
                        "Wine or craft beer tasting", "Theater performances"
                    ],
                    default=user_profile["activities"]
                )

                if st.button("Save Profile Changes"):
                    update_user_profile(
                        username,
                        new_username=new_username if new_username != username else None,
                        new_password=hash_password(new_password) if new_password else None,
                        new_bio=new_bio,
                        new_profile_image=profile_image_path,
                        new_activities=updated_activities
                    )
                    if new_username != username:
                        st.session_state["logged_in_user"] = new_username
                    st.success("Profile updated successfully!")

                if st.button("Delete Profile Permanently"):
                    delete_user(username)
                    del st.session_state["logged_in_user"]
                    st.success("Profile deleted successfully!")
                    st.rerun()

            # Other User Profiles
            st.subheader("Other User Profiles")
            users = sorted(get_all_users())
            if "visible_profiles" not in st.session_state:
                st.session_state["visible_profiles"] = {}

            for user in users:
                if user != username:
                    if st.button(f"{user}", key=f"{user}_button"):
                        if user in st.session_state["visible_profiles"]:
                            del st.session_state["visible_profiles"][user]
                        else:
                            st.session_state["visible_profiles"][user] = True

                    if user in st.session_state["visible_profiles"]:
                        other_user_profile = get_user_profile(user)
                        if other_user_profile:
                            st.write(f"### Profile of {user}")
                            if other_user_profile["profile_image"] and os.path.exists(other_user_profile["profile_image"]):
                                st.image(other_user_profile["profile_image"], caption=f"{user}'s Profile Picture", width=100)
                            else:
                                st.write("No profile picture uploaded.")
                            st.write("**Bio:**")
                            st.write(other_user_profile["bio"] or "No bio provided.")
                            st.write("**Activities:**")
                            st.write(", ".join(other_user_profile["activities"]) or "No activities selected.")

                            all_lists_combined_other = get_all_user_created_lists()
                            if other_user_profile["user_created_lists"]:
                                st.write("**Their Created Lists:**")
                                for other_lst_name, other_lst_data in other_user_profile["user_created_lists"].items():
                                    with st.expander(other_lst_name, expanded=False):
                                        if other_lst_name in all_lists_combined_other:
                                            st.write("**Locations:**")
                                            for loc in all_lists_combined_other[other_lst_name]["locations"]:
                                                st.markdown(f"- **{loc['name']}** {get_emoji_for_type(loc['type'])}")
                                        else:
                                            st.write("No details available.")

with tab2:
    st.header("Map")
    if "logged_in_user" in st.session_state:
        load_user_data_from_db(st.session_state["logged_in_user"])
    # Get all user-created lists
    all_user_lists = get_all_user_created_lists()
    # CSV files for base layers
    csv_files = [
        'final_CSV.csv',
    ]

#this should be in the tab above, 
#but somehow if I put it in there, it doesn't show up int the tab :(
display_map()








    

with tab3:
    st.header("Popular Locations")
    all_user_lists = get_all_user_created_lists()
    all_lists = all_user_lists

    if "list_likes" not in st.session_state:
        st.session_state.list_likes = {}
        for k, v in all_user_lists.items():
            st.session_state.list_likes[k] = v.get("likes", 0)

    leaderboard_data = {
        "List": list(all_lists.keys()),
        "Likes": [st.session_state.list_likes.get(list_name, all_lists[list_name].get("likes", 0)) for list_name in all_lists]
    }

    if leaderboard_data["List"]:
        leaderboard_df = pd.DataFrame(leaderboard_data).sort_values(by="Likes", ascending=False)

        st.subheader("Trending")
        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor("#0e1117")
        ax.set_facecolor("#0e1117")
        bars = ax.barh(leaderboard_df["List"], leaderboard_df["Likes"], color="skyblue")
        ax.set_xlabel("Likes", fontsize=12, color="white")
        ax.tick_params(axis="x", colors="white")
        ax.tick_params(axis="y", colors="white")
        for bar in bars:
            ax.text(bar.get_width() + 0.3, bar.get_y() + bar.get_height() / 2,
                    f'{int(bar.get_width())}', va='center', fontsize=10, color="white")
        plt.gca().invert_yaxis()
        st.pyplot(fig)
    else:
        st.write("No lists available yet.")

    # Add a New List (only if logged in)
    if "logged_in_user" in st.session_state:
        with st.expander("➕ Add a New List", expanded=False):
            st.markdown("### Create a New List")

            if not locations_df.empty:
                global_locs = [
                    {"name": row["Name"], "type": row["Type"], "latitude": row["Latitude"], "longitude": row["Longitude"]}
                    for idx, row in locations_df.iterrows()
                ]
                list_name = st.text_input("List Name")
                options_for_selection = [f"{loc['name']} ({loc['type']})" for loc in global_locs]
                selected_locations = st.multiselect("Select Locations", options=options_for_selection)

                if st.button("Add List", key="add_list_tab3"):
                    if not list_name.strip():
                        st.warning("List name cannot be empty.")
                    elif list_name in all_user_lists:
                        st.warning("A list with this name already exists.")
                    elif not selected_locations:
                        st.warning("You must select at least one location.")
                    else:
                        updated_locations = []
                        for loc_str in selected_locations:
                            loc_name = loc_str.split(" (")[0]
                            loc_type = loc_str.split(" (")[1].replace(")", "")
                            match = locations_df[(locations_df["Name"] == loc_name) & (locations_df["Type"] == loc_type)]
                            if not match.empty:
                                lat = float(match.iloc[0]["Latitude"])
                                lon = float(match.iloc[0]["Longitude"])
                                updated_locations.append({"name": loc_name, "type": loc_type, "latitude": lat, "longitude": lon})
                            else:
                                st.warning(f"Coordinates not found for {loc_name} ({loc_type})")

                        if "user_created_lists" not in st.session_state:
                            st.session_state.user_created_lists = {}
                        st.session_state.user_created_lists[list_name] = {
                            "likes": 0,
                            "locations": updated_locations,
                        }

                        if "liked_flags" not in st.session_state:
                            st.session_state.liked_flags = {}
                        st.session_state.liked_flags[list_name] = False
                        st.session_state.list_likes[list_name] = 0
                        sync_user_data_to_db()
                        st.success(f"List '{list_name}' created successfully!")
                        st.rerun()
            else:
                st.write("No locations available to create a list.")

    else:
        st.write("Log in to create your own lists.")

    st.subheader("All Lists")
    all_user_lists = get_all_user_created_lists()
    all_lists = all_user_lists

    for l_name, l_details in all_lists.items():
        with st.container():
            col1, col2, col3 = st.columns([6, 2, 2])
            with col1:
                st.markdown(f"### {l_name}")

            if "logged_in_user" in st.session_state:
                with col2:
                    if st.session_state.liked_flags.get(l_name, False):
                        if st.button("✔️ Liked", key=f"liked_{l_name}"):
                            st.session_state.liked_flags[l_name] = False
                            if l_name in st.session_state.list_likes:
                                st.session_state.list_likes[l_name] = max(st.session_state.list_likes[l_name] - 1, 0)
                            else:
                                st.session_state.list_likes[l_name] = 0
                            if l_name in st.session_state.get("user_created_lists", {}):
                                st.session_state.user_created_lists[l_name]["likes"] = st.session_state.list_likes[l_name]
                            sync_user_data_to_db()
                            st.rerun()
                    else:
                        if st.button("👍 Like", key=f"like_{l_name}"):
                            if l_name in st.session_state.list_likes:
                                st.session_state.list_likes[l_name] += 1
                            else:
                                st.session_state.list_likes[l_name] = 1
                            st.session_state.liked_flags[l_name] = True
                            if l_name in st.session_state.get("user_created_lists", {}):
                                st.session_state.user_created_lists[l_name]["likes"] = st.session_state.list_likes[l_name]
                            sync_user_data_to_db()
                            st.rerun()

                with col3:
                    if l_name in st.session_state.get("saved_lists", {}):
                        if st.button("✔️ Saved", key=f"saved_{l_name}"):
                            del st.session_state.saved_lists[l_name]
                            sync_user_data_to_db()
                            st.rerun()
                    else:
                        if st.button("💾 Save List", key=f"save_{l_name}"):
                            save_list_as_csv(l_name)
                            st.rerun()
            else:
                col2.write("Login to like")
                col3.write("Login to save")

            st.markdown("##### Spots:")
            for loc in l_details["locations"]:
                st.markdown(f"- **{loc['name']}** {get_emoji_for_type(loc['type'])}")

    st.subheader("Export Liked Locations")
    if "logged_in_user" in st.session_state:
        csv_file_path = generate_liked_locations_csv()
        if csv_file_path and os.path.exists(csv_file_path):
            with open(csv_file_path, "rb") as file:
                st.download_button(
                    "Download Liked Locations CSV",
                    data=file,
                    file_name="liked_locations.csv",
                    mime="text/csv",
                )
        else:
            st.write("No liked locations to export.")
    else:
        st.write("Log in to export liked locations.")

    st.subheader("Export Saved Lists")
    if "logged_in_user" in st.session_state:
        saved_csv_path = generate_saved_lists_csv()
        if saved_csv_path and os.path.exists(saved_csv_path):
            with open(saved_csv_path, "rb") as file:
                st.download_button(
                    "Download Saved Lists CSV",
                    data=file,
                    file_name="saved_lists.csv",
                    mime="text/csv",
                )
        else:
            st.write("No saved lists to export.")
    else:
        st.write("Log in to export saved lists.")