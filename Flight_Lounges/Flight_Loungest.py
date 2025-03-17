import streamlit as st
import pandas as pd
import plotly.express as px
from itertools import permutations
from itertools import combinations
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

# Function to load data from Google Sheets CSV
@st.cache_data
def load_data(csv_url):
    try:
        data = pd.read_csv(csv_url, encoding="utf-8", sep=",")
        return data
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return pd.DataFrame()

# Main function to build the app
def main():
    try:
        st.title("Lounge and Airline Routes Dashboard")
        st.markdown("""
        ### Lounge and Airline Routes Dashboard  

        This app visualizes lounges and airline routes.  

        This project is partially inspired by [this airport lounge map](https://www.reddit.com/r/awardtravel/comments/deqrz9/airport_lounge_map/).  

        Much of the data processing is done within [this Colab file](https://colab.research.google.com/drive/1-I0jMh-E69LxGCS-hZSY9tSNo-8sV1CD#scrollTo=hpvcOjcA9TVp).
        """)
       
        # Load Lounges Data
        csv_url = st.text_input("Enter the Google Sheets CSV URL for Lounges", 
                                "https://drive.google.com/file/d/1dmumzrtLm-rkeUfbkjOhNiY7UJ1OC_rV/view?usp=sharing")
        csv_url = 'https://drive.google.com/uc?id=' + csv_url.split('/')[-2]
        lounges = load_data(csv_url)

        # Load Routes Data
        routes_csv = st.text_input("Enter the Google Sheets CSV URL for Routes", 
                                   "https://drive.google.com/file/d/1LVaUcPnBjYzq5kLMv5Bn4Bw__Hs1x-xw/view?usp=sharing")
        routes_csv = 'https://drive.google.com/uc?id=' + routes_csv.split('/')[-2]
        routes = load_data(routes_csv)

        if not lounges.empty:
            lounges["IATA_Airport"] = lounges["IATA Code"] + " - " + lounges["Airport Name"]

            # Sidebar Filters
            st.sidebar.header("Filters")
            iata_airport_combined = lounges["IATA_Airport"].dropna().unique()
            lounge_names = lounges["Lounge Name"].dropna().unique()

            selected_iata_airport = st.sidebar.multiselect("Select Airport(s)", options=list(sorted(iata_airport_combined)), default=[])
            selected_lounge_name = st.sidebar.selectbox("Select Lounge Name", options=["All"] + list(sorted(lounge_names)))

            # Apply filters
            filtered_data = lounges.copy()
            if selected_iata_airport:
                filtered_data = filtered_data[filtered_data["IATA_Airport"].isin(selected_iata_airport)]
            if selected_lounge_name != "All":
                filtered_data = filtered_data[filtered_data["Lounge Name"] == selected_lounge_name]

            # Grouping for tables
            lounge_counts = (
                filtered_data.groupby(["IATA_Airport", "Lounge Name"])
                .size()
                .reset_index(name="Count")
            )

            # Pivot for display
            lounge_pivot = lounge_counts.pivot_table(index="Lounge Name", columns="IATA_Airport", values="Count", fill_value=0)

            st.subheader("Lounge Count by Airport")
            styled_pivot = lounge_pivot.style.background_gradient(cmap="Blues")
            st.dataframe(styled_pivot)

            # Airport Count by Lounge
            airport_pivot = lounge_counts.pivot_table(index="IATA_Airport", columns="Lounge Name", values="Count", fill_value=0)
            st.subheader("Airport Count by Lounge")
            styled_airport_pivot = airport_pivot.style.background_gradient(cmap="Greens")
            st.dataframe(styled_airport_pivot)
            
            
            #
            st.subheader("Map of All Selected Lounges vs. All Lounges")

            st.markdown("### Filtered Lounges")
            if "Latitude" in filtered_data.columns and "Longitude" in filtered_data.columns:
                fig_filtered = px.scatter_mapbox(
                    filtered_data,
                    lat="Latitude",
                    lon="Longitude",
                    color="IATA_Airport",
                    zoom=0,
                    hover_name="Lounge Name",
                    height=500,
                    mapbox_style="carto-darkmatter"
                )
                st.plotly_chart(fig_filtered)
            else:
                st.error("Latitude and Longitude columns are required for plotting the map.")

            st.markdown("All filtered Lounges")
            if "Latitude" in lounges.columns and "Longitude" in lounges.columns:
                fig_lounge_filtered = px.scatter_mapbox(
                    filtered_data,
                    lat="Latitude",
                    lon="Longitude",
                    color="Lounge Name",
                    zoom = 0,
                    hover_name="Lounge Name",
                    height=500,
                    mapbox_style="carto-darkmatter"
                )
                st.plotly_chart(fig_lounge_filtered)
            else:
                st.error("Latitude and Longitude columns are required for plotting the map.")


            # Restore previous route visualization between selected airports
            st.subheader("Routes Between Selected Airports")
    

            routes_grouped = routes.groupby(["Source airport", "Destination airport"]).agg({
                "Source Latitude": "first",
                "Source Longitude": "first",
                "Destination Latitude": "first",
                "Destination Longitude": "first"
            }).reset_index()
            
            
            #st.dataframe(routes_grouped)
            
            #get the IATA codes since the airport names do not exist in the routes data
            selected_iata_codes=filtered_data['IATA Code'].unique().tolist()
            
            #st.dataframe(routes_grouped)
            
            if len(selected_iata_codes) > 1:
                # Generate possible routes as a set of (source, destination) tuples
                possible_routes = {tuple(sorted(pair)) for pair in combinations(selected_iata_codes, 2)}

                # Create a column with (Source, Destination) tuples for fast lookup
                routes_grouped["route_tuple"] = routes_grouped.apply(lambda row: tuple(sorted((row["Source airport"], row["Destination airport"]))), axis=1)

                # Filter grouped routes to only be the ones needed
                routes_available = routes_grouped[routes_grouped["route_tuple"].apply(lambda x: x in possible_routes)]
                
                

            else:
                routes_available = routes_grouped[
                    routes_grouped["Source airport"].isin(selected_iata_codes) |
                    routes_grouped["Destination airport"].isin(selected_iata_codes)
                ]
                
            st.dataframe(routes_available)
            
            
            # Plot Routes
            if not routes_available.empty:
                for _, row in routes_available.iterrows():
                    fig_filtered.add_scattermapbox(
                        lon=[row["Source Longitude"], row["Destination Longitude"]],
                        lat=[row["Source Latitude"], row["Destination Latitude"]],
                        mode="lines",
                        line=dict(width=2, color="blue"),
                        name=f"{row['Source airport']} to {row['Destination airport']}"
                    )
                else:
                    t=""
                    
                
            
                st.plotly_chart(fig_filtered)
                
                # Sidebar: Select an Airport
                st.sidebar.header("Select a Single Airport for Routes")
                selected_airport = st.sidebar.selectbox(
                    "Select Airport", 
                    ["Select an airport"] + list((lounges["IATA_Airport"]).unique())
                )

                if selected_airport == "Select an airport":
                    st.write("Please select an airport from the filters on the left.")

                elif selected_airport:
                    # Get the IATA code for the selected airport
                    selected_airport_code = lounges[lounges["IATA_Airport"] == selected_airport]["IATA Code"].iloc[0]

                    # Filter routes that include the selected airport
                    selected_routes = routes[
                        (routes["Source airport"] == selected_airport_code) | (routes["Destination airport"] == selected_airport_code)
                    ]

                    st.subheader(f"Routes for {selected_airport} ({selected_airport_code})")

                    # Create a base map centered at the selected airport
                    source_lat = lounges[lounges["IATA Code"] == selected_airport_code]["Latitude"].iloc[0]
                    source_lon = lounges[lounges["IATA Code"] == selected_airport_code]["Longitude"].iloc[0]
                    
                    m = folium.Map(location=[source_lat, source_lon], zoom_start=4, tiles="CartoDB dark_matter")

                    # Create a marker cluster layer
                    marker_cluster = MarkerCluster().add_to(m)
                    
                    # Add routes to the map
                    for _, row in selected_routes.iterrows():
                        source = (row["Source Latitude"], row["Source Longitude"])
                        destination = (row["Destination Latitude"], row["Destination Longitude"])

                        
                        
                        # Add markers for source and destination
                        folium.Marker(
                            source, 
                            popup=f"Source: {row['Source airport']} ({row['Source airport']})",
                            icon=folium.Icon(color="blue", icon="plane", prefix="fa")
                        ).add_to(marker_cluster)

                        # Add route as a line
                        folium.PolyLine([source, destination], color="gold", weight=2.5, opacity=0.7).add_to(marker_cluster)

                    # Display the map in Streamlit
                    
                    st_map = st_folium(m)

            # # Single Airport Flight Routes
            # st.sidebar.header("Select a Single Airport for Routes")
            # selected_airport = st.sidebar.selectbox(
            # "Select Airport", 
            # ["Select an airport"] + list((lounges["IATA_Airport"]).unique())
            # )
            
            
            # if selected_airport=="Select an airport":
            #     st.write("Please selecte an aiport on the filters to the left")
            
            # elif selected_airport:
            #     #get the IATA codes since the airport names do not exist in the routes data
                
            #     selected_airport = lounges[lounges["IATA_Airport"] == selected_airport]["IATA Code"].iloc[0]
            
            #     selected_routes = routes[
            #         (routes["Source airport"] == selected_airport) | (routes["Destination airport"] == selected_airport)
            #     ]

            #     st.subheader(f"Routes for {selected_airport}")

            #     fig_airline = px.scatter_mapbox(
            #         selected_routes,
            #         lat="Source Latitude",
            #         lon="Source Longitude",
            #         color="Airline",
            #         hover_name="Source airport",
            #         zoom=3,
            #         height=500,
            #         mapbox_style="carto-darkmatter"
            #     )

            #     for _, row in selected_routes.iterrows():
            #         fig_airline.add_scattermapbox(
            #             lon=[row["Source Longitude"], row["Destination Longitude"]],
            #             lat=[row["Source Latitude"], row["Destination Latitude"]],
            #             mode="lines",
            #             line=dict(width=2, color="gold"),
            #             name=f"{row['Airline']} route"
            #         )
            #     st.plotly_chart(fig_airline)

        else:
            st.warning("No lounge data available. Please check the CSV URL.")

    except Exception as e:
        st.markdown(
            f"<h3 style='color: red; text-align: center;'>🚨 An error occurred. Please try selecting an airport or lounge 🚨 {e}</h3>", 
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()
