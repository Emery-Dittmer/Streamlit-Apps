import streamlit as st
import datetime
import pandas as pd
import plotly.express as px
import ast


#%%
##Formatting
#format Page
st.set_page_config(layout="wide")
#Formatting for Markdown
st.title("MLB Games This Season")
st.markdown("This is a dahsboard to map out the homes games within the *2024 MLB baseball season.* You can sort by team, state and date to find the ideal game based on geography.")



#%%
#Check if data is avaialble 
# #if not Get the Data
#modify data as needed

mlb_data="./data/MLB Games.csv"
games=pd.read_csv(mlb_data)

#DATA_URL="https://github.com/Emery-Dittmer/Streamlit-Apps/blob/main/MLB/MLB%20Games.xlsx"
#mlb_data = requests.get(DATA_URL)
#st.write(mlb_data.content)

try:
    games=games.drop(columns=['Unnamed: 0'])
except:
    games=games
    
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
    start_date = pd.to_datetime(d[0])
    end_date = pd.to_datetime(d[1])
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

    
    delta=st.number_input('Number of Days',1,7)
    st.session_state.delta=delta
    
    d = st.date_input(
        "Time Period for Games",
        (st.session_state.min_date,
        st.session_state.min_date + datetime.timedelta(days=delta-1)),
        st.session_state.ult_min_date,
        st.session_state.min_date + datetime.timedelta(days=365),
        format="DD.MM.YYYY",
    )

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

tab1, tab2 = st.tabs(["Distribution of Games", "Cumulative Games"])
with tab1:
    # Use the Streamlit theme.
    # This is the default. So you can also omit the theme argument.
    fig=px.pie(games,names='Home Team')
    st.plotly_chart(fig, theme="streamlit", use_container_width=True)
with tab2:
    # Use the native Plotly theme.
    fig=px.line(cumulative_counts_df,x='Date',y='Cumulative Games',color='Home Team')
    st.plotly_chart(fig, theme="streamlit", use_container_width=True)




#st.write(d)