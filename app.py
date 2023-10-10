# Imports
import os
import json
import re
import pandas as pd
import psycopg2
import streamlit as st
import logging
from st_text_annotator import StTextAnnotator # target annotation
import json
from datetime import datetime
import time
import pytz


st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans&display=swap');

        .sidebar .markdown-text-container {
            word-wrap: break-word;
            white-space: pre-line;
        }
            
        .sidebar .block-container {
            width: 33%;
        }
    </style>
""", unsafe_allow_html=True)


# Constants

CREATE_TABLE_QUERY = '''CREATE TABLE IF NOT EXISTS public.aspect_terms
(
    id SERIAL PRIMARY KEY,
    author text COLLATE pg_catalog."default",
    data_id integer,
    message_id BIGINT, 
    text text COLLATE pg_catalog."default",
    source text COLLATE pg_catalog."default",
    aspect_terms text COLLATE pg_catalog."default"
);'''

EMOTION_OPTIONS = [('Anger', 'Anger'), ('Sadness', 'Sadness'), ('Happiness', 'Happiness'), ('Fear', 'Fear'), ('None', 'None')]

# Functions

def connect_to_database():
    """Connect to the PostgreSQL database."""
    try:
        conn = psycopg2.connect(
            host=st.secrets["db_host"],
            database=st.secrets["db_database"],
            user=st.secrets["db_username"],
            password=st.secrets["db_password"],
            port="5432"
        )
        return conn
    except psycopg2.Error as e:
        logging.debug("Error connecting to the database:", e)
        return None


@st.cache_data
def load_data(upload_obj):
    """Load data from uploaded CSV."""
    if upload_obj is None:
        return None
    try:
        df = pd.read_csv(upload_obj)
    except (ValueError, RuntimeError, TypeError, NameError):
        logging.debug("Unable to process your request.")
    return df


def save_results(data):
    """Save aspect_terms to the database."""

    conn = connect_to_database()                    # Connect to db
    if not conn:
        return

    cursor = conn.cursor()                          # Create cursor to execute queries
    cursor.execute(CREATE_TABLE_QUERY)              # Create a new table if it doesn't exist

    for row in data.to_dict(orient='records'):      # Insert the data into the table
        insert_query = "INSERT INTO aspect_terms (id, author, data_id, message_id, text, source, aspect_terms) VALUES (DEFAULT, %s, %s, %s, %s, %s, %s);"
        values = (st.session_state.user_id, row['data_id'], row['message_id'], row['text'], row['source'], row['aspect_terms'])
        cursor.execute(insert_query, values)

    st.session_state["data_id"] += 1                # Increment the question number for the next row
    conn.commit()                                   # Commit the changes and close the connection
    conn.close()


def get_user_data(user_id):
    """Retrieve user data from the database."""

    conn = connect_to_database()                # Connect to the PostgreSQL database
    if not conn:
        return None

    cursor = conn.cursor()                      # Create a cursor to execute queries
    query = "SELECT * FROM aspect_terms WHERE author = %s ORDER BY data_id DESC LIMIT 1;"   # Query the database to get the user's data
    values = (user_id,)
    cursor.execute(query, values)
    result = cursor.fetchone()
    conn.close()                                # Close the connection

    return result


def get_user_data_all(user_id):
    """Retrieve user data from the database."""

    conn = connect_to_database()                # Connect to the PostgreSQL database
    if not conn:
        return None

    cursor = conn.cursor()                      # Create a cursor to execute queries
    query = "SELECT * FROM aspect_terms WHERE author = %s ORDER BY data_id DESC;"   # Query the database to get the user's data
    values = (user_id,)
    cursor.execute(query, values)
    result = cursor.fetchall()
    conn.close()                                # Close the connection

    return result



def extract_emotion_labels(emotion_data):
    return [emotion for emotion, label in emotion_data]


def reset_form():
    st.session_state.emotion = 4
    st.session_state.irrelevance = False
    st.session_state.urgency = False


def calculate_basic_emotion_percentages(selected_emotions):
    basic_emotion_counts = {}
    total_selected = len(selected_emotions)
    
    for emotion in selected_emotions:
        basic_emotion = EMOTION_DICT[emotion]
        basic_emotion_counts[basic_emotion] = basic_emotion_counts.get(basic_emotion, 0) + 1

    # Convert counts to percentages
    for basic_emotion, count in basic_emotion_counts.items():
        basic_emotion_counts[basic_emotion] = (count / total_selected) * 100

    return basic_emotion_counts


# App

# Load config file
with open('config.json') as f:
    config = json.load(f)

st.title('Aspect Term Labeling')

# Initialize session state
if "start" not in st.session_state:
    st.session_state["start"] = False
if "irrelevance" not in st.session_state:
    st.session_state.irrelevance = False
if "emotion" not in st.session_state:
    st.session_state.emotion = 4

# Login
if not st.session_state["start"]:
    
    # User input
    user_name = st.text_input('Please enter your username', label_visibility='hidden', placeholder="Enter Username")             # Prompt for user name
    
    # Configured users
    original_config_users = [j["name"] for j in config["users"]]
    config_users = [name.lower() for name in original_config_users]

    if user_name:
        st.write(' ')    

        # Check if user is in the config list
        if user_name.strip().lower() in config_users:
            
            # Check if user is already in database with entries
            user_data = get_user_data(user_name)                            # Get database data on user
            data_id = user_data[2] + 1 if user_data else 0                  # Set data_id to last labeled data item if user already exists in db, else 0

            if user_data != None:
                st.write(f"**Found**: {user_data[1]}")
                st.write(f"**Your progress**: {user_data[2]} tweets annotated so far")
                st.write(" ")
                # Add data into session state
                st.session_state.update({
                    "start": True,
                    "data_id": data_id,
                    "user_id": user_name.strip().lower().capitalize()
                })
                
            else:
                st.write(f"**User found**: {user_name.strip().capitalize()}")
                st.write(f"You haven't made any annotations yet, click 'Start Labeling' to begin!")
                st.write(" ")
                # Add data into session state
                st.session_state.update({
                    "start": True,
                    "data_id": data_id,
                    "user_id": user_name.strip().lower().capitalize()
                })

            st.button("Start Labeling")
               
        else:
            st.write(f"There's no username configured for '{user_name}'.")


# If session_state["start"] == True
else:
    
    # Load data into a df for user to annotate
    path = [j["data_path"] for j in config["users"] if j["name"] == st.session_state.user_id][-1]
    df = pd.read_csv(path) if config["predefined"] else load_data(st.file_uploader("Csv file", type=['.csv']))

    if df is not None:                                                                  # If there is data
        st.progress(round((int(st.session_state.data_id) / len(df)) * 100))             # Show progress bar

        if st.session_state.data_id < len(df):                                          # If we haven't reached the end of the labeling task yet
            message_id, text, source, photo_url = df.loc[st.session_state.data_id, ['message_id', 'text', 'source', 'photo_url']]       # Set labeling parameters
            tw_nr = str(st.session_state.data_id)

            tab1, tab2 = st.tabs(["Annotation", "Guide"])

            with tab1:              # Tab 1: Annotations     

                st.write("Tweet Nr " + {tw_nr})
                st.subheader({text})


                # Annotations Form
                with st.form(key="my_form"):                                    
                    with st.container():
                        st.subheader(f"Aspect Terms") 
                        output = StTextAnnotator(text)
                    st.write("---")
                    st.markdown("  ")
                    
                    if st.form_submit_button("Submit"):
                        if output:
                            aspect_terms = json.dumps(output)
                        else:
                            aspect_terms = ''
                        
                        data = [[st.session_state.data_id, message_id, text, source, aspect_terms]]
                        save_results(pd.DataFrame(data, columns=["data_id", "message_id", "text", "source", "aspect_terms"]))
                        
                        reset_form()
                        st.experimental_rerun()


            with tab2:              # Tab 2: Guide
                
                st.subheader("Overview")

                with st.expander("Details on this labeling task"):
                    st.write("The dataset you are given in this labeling tool is a disaster-related twitter dataset, specifically on the topics"+ 
                                "of wildfires and flood events. It consists of 6700 tweets. "+
                                "This labeling task is designed to generate a high-quality training dataset for several natural language "+
                                "processing (NLP) models in the context of sentiment and semantic information extraction from complex "+
                                "natural language. Ultimately, the intended use from such a training dataset is to aid emergency responders "+
                                "in the event of natural disasters. The dataset will later be made publicly available, so that the broader "+
                                "scientific community can also make use of it. ")
                    st.write(" ")
                    st.write("The high-level aims related to this labeling task are to generate:")
                    st.write("- a high-quality social media training dataset which contains complex natural language (slang words, "+
                                "colloquial phrasing, incorrect grammar, sarcasm, etc.) ")
                    st.write("- an aspect-level training dataset for the domain of natural disaster response.")
                    st.write(" ")
                    st.write("NLP tasks that can be addressed using this dataset include: ")
                    st.write("- Aspect-based emotion analysis: a fine-trained analysis of the emotions in text and their respective "+
                                "targets ")
                    st.write("- Sentence-level emotion classification (where no aspect term is identified, or all aspect-level "+
                                "emotions are the same) ")
                    st.write("- Urgency classification: identifying the urgent need for help.")
                



                st.subheader("Definitions")

                with st.expander("Emotions and Targets?"):
                    st.write("For each tweet, you can annotate up to 3 :red[emotion-target pairs]. To be exact, an emotion-target pair refers to an aspect-term and its associated emotion. Identifying these pairs is one aim of ABEA.")
                
                with st.expander("What is ABEA?"):
                    st.write("ABEA stands for aspect-based emotion analysis. It originates from sentiment analysis, which is a technique for "+
                             "automatically recognizing positive or negative opinions in texts. Whereas sentiment analysis aims to classify opinions"+
                              " on a binary scale (from positive to negative), emotion analysis (or emotion detection) aims to classify text into distinct emotion categories. ")
                    st.write("Traditionally, most methods detect sentiments or emotions on the sentence level. This means that if several expressions of "+
                             "sentiment/emotion occur in a sentence, the analysis results are a single generalized value. Aspect-based analyses try to distinguish "+
                             "between different sentiments/emotions within the same sentence, while also extracting the target to which they relate."+
                              " This breaks down a general sentiment/emotion on the sentence level into detailed aspects.")
                with st.expander("What is an Aspect Term?"):
                    st.write("An aspect term is a word or phrase within a text that represents a specific entity, feature, or topic that "+
                            "emotions are directed towards. It is the :red[focal point of the emotion in the statement]. In simpler terms, it's "+
                            "the 'what' or 'who' that the sentiment, opinion or emotion in the statement is about. In the context of "+
                            "disaster-related tweets, aspect terms can be entities, locations, events, or any other specific subject that "+
                            "the tweet's emotion is about. ")
                    st.write("Emotion Association: An aspect term is typically associated with a particular emotion in the text. If a term "+
                            "does not have any emotion directed towards it, it might not be an aspect term. For example, in the tweet "+
                            "'The response team was quick during the flood,' 'response team' is the aspect term, not 'flood.'")
                    st.write("Multiple Aspect Terms: A single tweet can have multiple aspect terms. Each aspect term should be +"
                                "associated with its respective emotion. For instance, in the tweet 'The firefighters were brave, but the "+
                                "equipment was outdated,' both 'firefighters' and 'equipment' are aspect terms with different emotions "+
                                "associated with them.")
                    st.write(" ")
                    st.image("images/aspect based explanation.png")

                with st.expander("What is the Aspect-Based Emotion?"):
                    st.write("The aspect-based emotion is the :red[emotion associated with the aspect term]. The aspect-based emotion refers to the emotions"+
                             "or sentiments associated with a particular aspect. It involves identifying and understanding the emotions expressed in relation to that specific aspect.")
                    st.write(" ")
                    st.image("images/aspect based explanation.png")





                st.subheader("Annotating Aspect-Terms and Emotions")

                with st.expander("How do I annotate the Aspect-term and Emotion?"):
                    st.write("**Step 1**: Read the current tweet carefully.")    
                    st.write("**Step 2**: Identify the emotion in the text.")
                    st.write("**Step 3**: Select the target word(s) using your mouse.")
                    st.write("**Step 4**: You can click the 'x' to de-select the text.")
                    st.write("If you find any additional aspect-terms, you can annotate those in the additional sections.")
                    st.image("images/HowTo1.png")

                with st.expander("What is the best strategy for labeling emotion-target pairs?"):
                    st.write("Try to :red[first identify any emotions] from the text. The detection of emotions is a more "+
                             "intuitive process for humans than the exact pinpointing of aspect terms. Once you have identified"+
                              " the emotion, try to identify the exact target of that emotion. ")

                with st.expander("What if there is no explicit aspect term?"):
                    st.write("When there is no target of the emotion or the target is implicitly expressed (e.g., “Terrible!”), leave the "+
                             "target selection blank and just choose the appropriate emotion for the text. In such cases, the emotion will "+
                              "be considered as applicable to the entire tweet text. These annotations will later be used for sentence level emotion detection. ")

                with st.expander("Should I select a target if there is no emotion (e.g. reporting)?"):
                    st.write("No, since the essence of ABEA is to identify emotion-target pairs, there cannot be a “target” if there is no emotion. To ensure consistency "+
                             "in the training dataset, please make sure you only annotate aspect terms (targets) if they come in a pair with an emotion. ")
                
                with st.expander("How much time and effort should I invest to decide on the exact words I select for the aspect-term?"):
                    st.write("Please take enough time to fully understand the tweet and annotate it to the best of your judgement. Your judgement is critical for"+
                             " deciding whether the target of an emotion is just a single word or a series of words or no words at all. After all annotations are completed,"+
                              " only those words that match between most annotators will be kept in the result dataset. ")
                    
                with st.expander("What if the text is a citation or a 3rd person account? Should I still annotate the emotions and targets?"):
                    st.write("Yes, please annotate as usual.")

                with st.expander("I'm really unsure which emotion is in this tweet."):
                    st.write("If you're unsure, consider the Emotion Graph (Shaver et al., 1987)! You may find it useful to print out the Graph and keep it handy while you annotate!")

                with st.expander("When to use the **None** Emotion Category"):
                    st.write("This category is used for tweets where :red[**no**] clear emotion is directed towards the aspect term. That includes neutral observations, factual statements, "+
                             "or any content where the emotion of the person posting the tweet is not explicitly expressed or inferred. The 'none' category is relevant when the"+
                              " text provides information without conveying personal feelings, opinions, or reactions. ")
                    st.write("**Caution**: :red[Do not use the 'None' emotion category when you are unsure which emotion to choose]. As long as there is any emotion contained in the text,"+
                             " the emotion category should not be set to 'None'. Please refer to the emotion graph to help you make a decision on the emotion.")


                st.subheader("Annotating Urgency")

                with st.expander("When is a Tweet considered 'Urgent'?"):
                    st.write("A tweet can be marked as urgent if the tweet refers to a situation that is :red[serious/dangerous], where people urgently :red[need help]"+
                             " :red[now] or are likely to need help in the :red[near future].")
                    st.write(" ")

                


                st.subheader("Annotating Disaster-Relatedness")

                with st.expander("When is a Tweet considered 'Non Disaster-Related'?"):
                    st.write("A tweet should be marked as non disaster-related if it makes :red[no direct or indirect reference to a natural disaster], such as flooding or wildfires.")
                    st.write(" ")
                       


        else:
            st.markdown("End of data.")
            