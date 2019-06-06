# fitbit-lambda-csv-drive
Some of the functions and code in this script have been modified from a previous programmer who wrote it in Python 2 to be run in Python 3 on AWS. Other parts, in fact a large portion of it now, are my own original code, including the __fitbit_activities_data_complete__ function and the Google Drive environment setup and CSV file creation parts of the Lambda handler. Thus, I will mostly cover these two aspects of the code here.

## Fitbit Activities Data
There are three steps to this process:
1. Retrieving
2. Interpreting
3. Sorting

### The First Step: Retrieving
To retrieve each client's Fitbit activities data, I must make a call to the Fitbit API with their access token. The response that comes from this call is a dictionary where one of the keys ("activities") has a value that is an array of dictionaries. This what I want to put into a CSV.

### The Second Step: Interpretting
After defining the list of activities, I used a for loop to iterate over each activity dictionary and used the __fitbit_activities_data_complete__ function to extract the data I want from it and add that data to an empty dictionary defined as __d__. I added some logic to determine whether a certain activity counts or not based on certain information retrieved from the response. For example, some activities are of log type "auto-detected", meaning Fitbit detected some increase in heart rate and created an activity based on that. If this is the case, the activity is not counted, since it was not intentionally logged by the user. Other reasons for not counting an activity are included in the Python script.

### The Third Step: Sorting
Each of the pieces of data is then placed into the empty dictionary with its corresponding key. A dictionary is created for each activity for each person and a long list of everyone's activities is returned. Then, these dictionaries a sorted into CSVs. Each CSV corresponds to a class, denoted by a number called 'ou', Everyone in the same class has their data written into a CSV with each activity taking up a row and each column being a piece of data retrieved from the Fitbit API response. The first row of each CSV contains the keys from the __d__ dictionary. The activities are placed in alphabetical order by the last name of the student.

## Writing to Google Drive
