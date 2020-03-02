import os
import glob
import psycopg2
import pandas as pd
from sql_queries import *
import json
from datetime import datetime

def json_to_df(filepath):
    """
    This function takes a valid JSON filepath and returns the JSON data formatted as a pandas DataFrame.
    """
    try:
        with open(filepath, 'r') as json_data:
            data = json.load(json_data)
            
        df = pd.DataFrame([data])
        
    except json.decoder.JSONDecodeError:
        df = pd.read_json(filepath, lines = True)
    
    return df


def process_song_file(cur, filepath):
    """
    Split the song data into a songs table and an artists table.
    """
    # Open song file
    df = json_to_df(filepath)
    
    # Insert song record
    song_data = df[['song_id', 'title', 'artist_id', 'year', 'duration']].values[0].tolist()
    cur.execute(song_table_insert, song_data)
    
    # Insert artist record
    artist_data = df[['artist_id', 'artist_name', 'artist_location', 'artist_latitude', 'artist_longitude']].values[0].tolist()
    cur.execute(artist_table_insert, artist_data)


def process_log_file(cur, filepath):
    """
    Read in the log data, clean it, and split the data into the users, time and songplay tables.
    """
    # open log file
    df = json_to_df(filepath)

    # filter by NextSong action
    df = df[df['page'] == 'NextSong']

    # convert timestamp column to datetime
    ms = df['ts']
    t = ms.apply(lambda x: datetime.utcfromtimestamp(x//1000).replace(microsecond = x%1000*1000))
    
    # insert time data records
    time_data = [t, t.dt.hour, t.dt.day, t.dt.week, t.dt.month, t.dt.year, t.dt.day_name()]
    column_labels = ['timestamp', 'hour', 'day', 'week_of_year', 'month', 'year', 'weekday_name']
    time_df = pd.DataFrame(dict(zip(column_labels, time_data)))

    for i, row in time_df.iterrows():
        cur.execute(time_table_insert, list(row))

    # load user table
    user_df = df[['userId', 'firstName', 'lastName', 'gender', 'level']]

    # insert user records
    for i, row in user_df.iterrows():
        cur.execute(user_table_insert, row)
        
    # Reset the indices on the dataframes
    df.reset_index(drop = True, inplace = True)
    time_df.reset_index(drop = True, inplace = True)

    # Insert songplay records
    for index, row in df.iterrows():
        
        # Get songid and artistid from song and artist tables
        cur.execute(song_select, (row.song, row.artist, row.length))
        results = cur.fetchone()
        
        if results:
            songid, artistid = results
        else:
            songid, artistid = None, None

        # Insert songplay record
        songplay_data = [time_df.iloc[index].timestamp, row.userId, row.level, songid, artistid, row.sessionId, row.location, row.userAgent]
        cur.execute(songplay_table_insert, songplay_data)


def process_data(cur, conn, filepath, func):
    """
    Crawl the directories for all song and log data and run our processing functions on the data.
    """
    # Get all files matching extension from directory
    all_files = []
    for root, dirs, files in os.walk(filepath):
        files = glob.glob(os.path.join(root,'*.json'))
        for f in files :
            all_files.append(os.path.abspath(f))

    # Get total number of files found
    num_files = len(all_files)
    print('{} files found in {}'.format(num_files, filepath))

    # iterate over files and process
    for i, datafile in enumerate(all_files, 1):
        func(cur, datafile)
        conn.commit()
        print('{}/{} files processed.'.format(i, num_files))


def main():
    conn = psycopg2.connect("host=127.0.0.1 dbname=sparkifydb user=student password=student")
    cur = conn.cursor()

    process_data(cur, conn, filepath='data/song_data', func=process_song_file)
    process_data(cur, conn, filepath='data/log_data', func=process_log_file)

    conn.close()


if __name__ == "__main__":
    main()