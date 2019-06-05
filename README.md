# fitbit-lambda-csv-drive
Some of the functions and code in this script have been modified from a previous programmer who wrote it in Python 2 to be run in Python 3 on AWS. Other parts, in fact a large portion of it now, are my own original code, including the __fitbit_activities_data_complete__ function and the Google Drive environment setup and CSV file creation parts of the Lambda handler. Thus, I will mostly cover these two aspects of the code here.

## Fitbit Activities Data
There are three steps to this process:
1. Retrieving
2. Interpreting
3. Sorting

### The First Step: Retrieving
To retrieve each client's Fitbit activities data, I must make a call to the Fitbit API with their access token. The response that comes from this call is a dictionary where one of the keys ("activities") is an array of dictionaries
