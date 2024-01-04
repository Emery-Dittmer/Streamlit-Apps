import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
import ast
import requests
from io import BytesIO


#%%
##Formatting
#format Page
st.set_page_config(layout="wide",initial_sidebar_state="expanded")
#Formatting for Markdown
st.title("MLB Games This Season")
st.markdown("This is a dahsboard to map out the homes games within the *2024 MLB baseball season.* You can sort by team, state and date to find the ideal game based on geography.")






#%%
#Check if data is avaialble 
# #if not Get the Data
#modify data as needed
try:
    CSV = '1aPOm3oFMmz0nUgGhBVGEwucAKIdokC-p'
    csv_url = f'https://drive.google.com/uc?export=download&id={CSV}'
    file = requests.get(csv_url)
    bytesio = BytesIO(file.content)
    games = pd.read_csv(bytesio)
except:
    st.text("DATA ERROR")
    

#DATA_URL="https://github.com/Emery-Dittmer/Streamlit-Apps/blob/main/MLB/MLB%20Games.xlsx"
#mlb_data = requests.get(DATA_URL)
#st.write(mlb_data.content)

try:
    games=games.drop(columns=['Unnamed: 0'])
except:
    games=games
    
st.dataframe(games)
    
games['Full Date']=games['Date']
games['Date'] = pd.to_datetime(games['Date'], format='%A, %B %d, %Y')
cols = games.columns.tolist()
cols = cols[-1:] + cols[:-1]
games = games[cols]

# Create a new DataFrame to store cumulative counts
cumulative_counts_df = pd.DataFrame(columns=['Date', 'Home Team', 'Cumulative Games'])

# Iterate over unique teams
for team in games['Home Team'].unique():
    team_df = games[games['Home Team'] == team].sort_values('Date')
    team_df['Cumulative Games'] = range(1, len(team_df) + 1)
    cumulative_counts_df = pd.concat([cumulative_counts_df, team_df])


team = games['Home Team'].drop_duplicates()

#%%
#functions

def datafilter(df):
    #Home Team
    df = df[df['Home Team'].str.contains('|'.join(team))]
    #Dates
    start_date = pd.to_datetime(d1)
    end_date = pd.to_datetime(d2)
    df=df[df['Date'].between(start_date, end_date)]
    #US State
    df=df[df['State'].str.contains('|'.join(us_state))]
    
    #reset delta
    delta=start_date-end_date
    min_date=start_date
    return df

def increment_week():
    st.session_state.min_date= pd.to_datetime(d[0])
    st.session_state.min_date+= datetime.timedelta(days=7)

#%%
#Session State
if 'ult_min_date' not in st.session_state:
    st.session_state.ult_min_date = games['Date'].min()

if 'min_date' not in st.session_state:
    st.session_state.min_date = games['Date'].min()
    min_date=st.session_state.min_date
    
if 'delta' not in st.session_state:
    st.session_state.delta = 7
    



#%%
#Get the Sidebar with calendar
with st.sidebar:
    
    d1 = st.date_input(
        "Start Date",
        st.session_state.min_date,
        format="DD.MM.YYYY"
    )
    
    delta=st.slider('Number of Days',1,150)
    st.session_state.delta=delta
    
    d2=(st.session_state.min_date + datetime.timedelta(days=delta-1))
    
    st.markdown("Time Period <br> " +
                "**"+ d1.strftime("%A, %B %d, %Y") + "**"+
                '  <br> to <br> ' + 
                "**"+ d2.strftime("%A, %B %d, %Y") + "**",
                unsafe_allow_html=True)
    team = st.multiselect(
        'Select Team',
        (games['Home Team'].drop_duplicates().sort_values())
    )
    
    us_state=st.multiselect(
        'Select US State',
        games['State'].drop_duplicates().sort_values()
    )
    
    # Increment the date forward by 1 week when the button is clicked
    st.button('Next Week', on_click=increment_week)
    #games=st.button('Reset',on_click=reset_data,type='primary')
    
games=datafilter(games)
cumulative_counts_df=datafilter(cumulative_counts_df)

#%%
#Dashboard Elements

#expander with raw data
with st.expander('Open for Raw Data'):
    st.dataframe(games)
#st.map(homegames,latitude='LAT',longitude='LON')

map_games = px.scatter_mapbox(games, 
                        lat = 'Home Team Lat',
                        lon = 'Home Team Long', 
                        color = 'Home Team',
                        zoom=2.5,
                        mapbox_style = 'carto-darkmatter')
st.plotly_chart(map_games, use_container_width=True)

tab1, tab2, tab3 = st.tabs(["Heatmap of Games","Distribution of Games", "Cumulative Games"])
with tab1:
   # Create a new DataFrame for heatmap
    heatmap_df = pd.DataFrame(columns=['Team', 'Opponent', 'Count'])

    # Iterate through each row and count occurrences of home and away teams
    for _, row in games.iterrows():
        # Home team
        heatmap_df = pd.concat([heatmap_df, pd.DataFrame({'Team': [row['Home Team']], 'Opponent': [row['Away Team']], 'Count': [1]})], ignore_index=True)
        # Away team
        heatmap_df = pd.concat([heatmap_df, pd.DataFrame({'Team': [row['Away Team']], 'Opponent': [row['Home Team']], 'Count': [1]})], ignore_index=True)

    # Group by team and opponent and sum the counts
    heatmap_df = heatmap_df.groupby(['Team', 'Opponent']).sum().reset_index()

    # Create a pivot table for the heatmap
    heatmap_pivot = heatmap_df.pivot(index='Team', columns='Opponent', values='Count').fillna(0)

    # Create heatmap using Plotly
    fig = px.imshow(heatmap_pivot.values,
                    labels=dict(color='Count'),
                    x=heatmap_pivot.columns,
                    y=heatmap_pivot.index,
                    color_continuous_scale='Viridis')

    # Customize the layout if needed
    fig.update_layout(
        title='Home vs Away Teams Heatmap',
        xaxis_title='Opponent',
        yaxis_title='Team'
    )
   
    st.plotly_chart(fig, theme="streamlit", use_container_width=True)
with tab2:
    # Use the Streamlit theme.
    # This is the default. So you can also omit the theme argument.
    fig=px.pie(games,names='Home Team')
    st.plotly_chart(fig, theme="streamlit", use_container_width=True)
with tab3:
    # Use the native Plotly theme.
    fig=px.line(cumulative_counts_df,x='Date',y='Cumulative Games',color='Home Team')
    st.plotly_chart(fig, theme="streamlit", use_container_width=True)




#st.write(d)