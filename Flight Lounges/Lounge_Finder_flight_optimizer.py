import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO
from itertools import permutations



# Function to load data from Google Sheets CSV
@st.cache_data
def load_data(csv_url):
   
    try:
        # Read CSV with flexible options
        data = pd.read_csv(
            csv_url,
            error_bad_lines=False,  # Ignore malformed rows
            warn_bad_lines=True,  # Show warnings for problematic rows
            encoding="utf-8",  # Handle special characters
            sep=","  # Ensure correct delimiter (change to `sep=";"` if needed)
        )
        return data
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return pd.DataFrame()


# Main function to build the app
def main():
    st.title("Lounge and Airline Routes Dashboard")
    st.markdown("This app visualizes lounges and airline routes.")

    # URL to the Google Sheets CSV
    csv_url = st.text_input(
        "Enter the Google Sheets CSV URL", 
        "https://drive.google.com/file/d/1f-4T5M5gOo8negThDbvexGCMa5XEd5QN/view?usp=sharing"
    )
    csv_url = 'https://drive.google.com/uc?id=' + csv_url.split('/')[-2]
    # Load lounges and routes data
    lounges = load_data(csv_url)
    
    #routes
    routes_csv = st.text_input(
        "Enter the Google Sheets CSV URL", 
        "https://drive.google.com/file/d/1igkdA7emOeNEBpq15GaqFdmYz-dr0Nz3/view?usp=sharing"
    )
    routes_csv = 'https://drive.google.com/uc?id=' + routes_csv.split('/')[-2]
    routes = pd.read_csv(routes_csv)

    # Validate lounges data
    if not lounges.empty:
        # Sidebar for filters
        st.sidebar.header("Filters")

        iata_codes = lounges["IATA Code"].dropna().unique()
        lounge_names = lounges["Lounge Name"].dropna().unique()

        # Multiselect for IATA Codes
        selected_iata = st.sidebar.multiselect(
            "Select IATA Code(s)", options=list(iata_codes), default=[]
        )

        # Single select for Lounge Names
        selected_lounge_name = st.sidebar.selectbox(
            "Select Lounge Name", options=["All"] + list(lounge_names)
        )

        # Apply filters
        filtered_data = lounges.copy()
        

        if selected_iata:  # Apply IATA Code filter if any are selected
            filtered_data = filtered_data[filtered_data["IATA Code"].isin(selected_iata)]
            lounge_counts = (
                filtered_data.groupby(["IATA Code", "Lounge Name"])
                .size()
                .reset_index(name="Count")  # Rename the count column
                .sort_values(["IATA Code", "Count"], ascending=[True, False])  # Sort by IATA Code and Count (Descending)
            )
        if selected_lounge_name != "All":
            filtered_data = filtered_data[filtered_data["Name"] == selected_lounge_name]
            
        #st.write(filtered_data)
        
            # Group by IATA Code and Lounge Name, then count occurrences
        lounge_counts = (
            filtered_data.groupby(["IATA Code", "Lounge Name"])
            .size()
            .reset_index(name="Count")  # Rename the count column
            )
            # Pivot the table so that IATA Codes become columns and Lounge Names remain as rows
        lounge_pivot = lounge_counts.pivot_table(
            index="Lounge Name", 
            columns="IATA Code", 
            values="Count", 
            fill_value=0  # Replace NaNs with 0 for better readability
)
            

        # Display the filtered data
        st.subheader("Lounge Count by Airport")
        # Apply color gradient using Pandas Styler and Streamlit
        styled_pivot = lounge_pivot.style.background_gradient(cmap="Blues")

        # Show styled dataframe in Streamlit
        st.dataframe(styled_pivot)
        
        # Map visualization
        st.subheader("Map of All Lounges")
        if "Latitude" in filtered_data.columns and "Longitude" in filtered_data.columns:
            fig = px.scatter_mapbox(
                filtered_data,
                lat="Latitude",
                lon="Longitude",
                color="Lounge Name",
                hover_name="Name",
                zoom=3,
                height=500,
                mapbox_style="carto-darkmatter"
            )
        if fig:
            st.plotly_chart(fig)
        
        # Group by Source and Destination Airports, keeping first occurrence for unique routes
        routes_grouped = routes.groupby(
            ["Source airport", "Destination airport"]
        ).agg({
            "Source airport ID": "first",
            "Destination airport ID": "first",
            "Source Latitude": "first",
            "Source Longitude": "first",
            "Destination Latitude": "first",
            "Destination Longitude": "first"
        }).reset_index()
        
        if selected_iata and len(selected_iata) > 1:
            # Generate all possible airport pairs (A → B and B → A)
            possible_routes = set(permutations(selected_iata, 2))

            # Filter routes where (Source → Destination) or (Destination → Source) matches the possible pairs
            filtered_grouped_routes = routes_grouped[
                routes_grouped.apply(lambda row: (row["Source airport"], row["Destination airport"]) in possible_routes or
                                        (row["Destination airport"], row["Source airport"]) in possible_routes, axis=1)
            ]
        else:
                filtered_grouped_routes = routes_grouped[
            (routes_grouped["Source airport"].isin(selected_iata)) | (routes_grouped["Destination airport"].isin(selected_iata))
            ]
        
        st.write(filtered_grouped_routes)
        
        # Add routes to the map
        if not filtered_grouped_routes.empty and fig:
            for _, row in filtered_grouped_routes.iterrows():
                fig.add_scattermapbox(
                    lon=[row["Source Longitude"], row["Destination Longitude"]],
                    lat=[row["Source Latitude"], row["Destination Latitude"]],
                    mode="lines",
                    line=dict(width=2, color="blue"),
                    name=f"{row['Source airport']} to {row['Destination airport']}"
                )

        
        else:
            st.error("Latitude and Longitude columns are required for plotting the map.")
        st.subheader("Routes between Airport")
        st.plotly_chart(fig)
                
    else:
        st.warning("No lounge data available. Please check the CSV URL.")

# Run the app
if __name__ == "__main__":
    main()
