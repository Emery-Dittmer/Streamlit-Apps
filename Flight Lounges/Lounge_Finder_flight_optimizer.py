import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# Function to load data from Google Sheets CSV
@st.cache_data
def load_data(csv_url):
    try:
        data = pd.read_csv(csv_url)
        return data
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        return pd.DataFrame()

# Main function to build the app
def main():
    st.title("Lounge Data Dashboard")
    st.markdown("This app visualizes lounges and provides filters for IATA code and lounge name.")

    # URL to the Google Sheets CSV (replace this with your actual CSV link)
    csv_url = st.text_input(
        "Enter the Google Sheets CSV URL", 
        "https://drive.google.com/file/d/1G9d_NQkV_d3sMqIJjWZ5HkBCVVHy_r3N/view?usp=sharing"
    )
    csv_url = 'https://drive.google.com/uc?id=' + csv_url.split('/')[-2]

    # Load data
    lounges = load_data(csv_url)

    # Validate data
    if not lounges.empty:
        # Summary Table: Most Common Airport Lounge Names
        st.subheader("Most Common Airport Lounge Names")
        lounge_counts = (
            lounges.groupby(["IATA Code", "Name"])
            .size()
            .reset_index(name="Count")
            .sort_values(["IATA Code", "Count"], ascending=[True, False])
        )
        most_common_lounges = lounge_counts.groupby("IATA Code").head(1)
        st.write(most_common_lounges)

        # Sidebar for filters
        st.sidebar.header("Filters")

        # Filter options
        iata_codes = lounges["IATA Code"].dropna().unique()
        lounge_names = lounges["Name"].dropna().unique()

        # Sidebar dropdown filters
        selected_iata = st.sidebar.selectbox("Select IATA Code", options=["All"] + list(iata_codes))
        selected_lounge_name = st.sidebar.selectbox("Select Lounge Name", options=["All"] + list(lounge_names))

        # Apply filters
        filtered_data = lounges.copy()
        if selected_iata != "All":
            filtered_data = filtered_data[filtered_data["IATA Code"] == selected_iata]
        if selected_lounge_name != "All":
            filtered_data = filtered_data[filtered_data["Name"] == selected_lounge_name]

        # Map visualization
        st.subheader("Lounge Map")
        if "Latitude" in filtered_data.columns and "Longitude" in filtered_data.columns:
            fig = px.scatter_mapbox(
                filtered_data,
                lat="Latitude",
                lon="Longitude",
                color="Lounge Name",
                hover_name="Name",
                zoom=3,
                height=500,
                mapbox_style="open-street-map"
            )
            st.plotly_chart(fig)
            
        else:
            st.error("Latitude and Longitude columns are required for plotting the map.")
            
        # Display filtered data
        st.subheader("Filtered Data")
        st.write(filtered_data)
    else:
        st.warning("No data to display. Please check the CSV URL.")

# Run the app
if __name__ == "__main__":
    main()
