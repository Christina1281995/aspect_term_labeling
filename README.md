# Aspect-Term Labeling

Currently, this app runs at https://emotionlabeling.streamlit.app/

## To Run the App on Streamlit Cloud 

### Setup

This app is hosted on [Streamlit Cloud](https://docs.streamlit.io/streamlit-community-cloud) and uses a postgres database to store labeled data (via psycopg2). You will need to set up your own Streamlit account to host an app from GitHub (clone and adjust this app for exmaple) and you will need to set up a database table ("results"). The database connection details can be stored directly when you configure the app on Streamlit cloud in the "secrets". For local testing you can create a ```.streamlit``` folder with a ```secrets.toml``` file that contains the connection  details e.g. 

```
db_host = "..."
db_database = "..."
db_username = "..."
db_password = "..."
db_port = "..."
```

## To Run the App Locally
### Setup Conda Environment
First install the dependencies using conda. The environment.yml file contains all the dependencies. To create the environment, run the following command in the root directory of the project.
``` conda env create -f environment.yml ```
This will create a conda environment called "stream-env". To activate the environment, run the following command.
``` conda activate stream-env ```

### Running the App
To run the app, run the following command.
``` streamlit run app.py ```
if that is not working, try the following command.
``` python -m streamlit run app.py```

## Managing Users
There is a `config.json` file in which you can specify the experimental settings.
It contains a list of `users` which has the following fields:
- `id`: Unique id of the user
- `name`: Name of the user
- `data_path`: Path to the data file for the user

When you first open up the app you have to type in the username which is validated with a json file of predefined users in the `config.json` file. If the user name is matched, the app will load the data file specified in the `config.json` file or if you turn of the predefined flag in the `config.json` file, you can specify the data file in the app by uploading it.

## The Input Data (to be labeled)
The data file should be a csv file laying in the `data` directory. The csv file should contain the following columns:

- `text`: The text to be labeled
- `Aspect Term`: The aspect term to be labeled
- `Sentiment`: The sentiment of the aspect term

The results are then either stored in a csv file in the `results` directory, where the name of the file is the username, or they are passed to the database table `results`.

You can also pause and continue the labeling process. If you want to continue the labeling process, you'll have to type in the username again and the app will load your current progress and continue the labeling process from there.

