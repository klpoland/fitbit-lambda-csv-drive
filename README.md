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
Each of the pieces of data is then placed into the empty dictionary with its corresponding key. A dictionary is created for each activity for each person and a long list of everyone's activities is returned. Then, these dictionaries are sorted into CSVs. Each CSV corresponds to a course, denoted by a number called 'ou', Everyone in the same course has their data written into a CSV with each activity taking up a row and each column being a piece of data retrieved from the Fitbit API response. The first row of each CSV contains the keys from the __d__ dictionary. The activities are placed in alphabetical order by the last name of the student.

For Example:
```
    Name    | Username | Course ID | Age | Weight (kg) | ....
---------------------------------------------------------------    
 Reed, Jim  |  jr5678  |  567890   | 25  |     65      | ....
---------------------------------------------------------------
Smith, John |  js1234  |  567890   | 21  |     50      | ....

```
## Writing to Google Drive
Next, I wanted to move these local CSVs built in Python to a Google Drive folder. To do this, I set up a service account on the Google Client API and added the Google Drive API to the account. I downloaded the service-keys.json file and loaded it into my script so the Lambda function can have permission to access the Google API and the service account's Google Drive. I built a check into my code to see if there is already a folder in the drive with the name I want to use and, if it doesn't exist, my code creates one and adds a permission for the account where the application frontend is being built to access the folder. Otherwise, the code opens the desired folder, adds the same permission, and does another check to find files with the same name as the course activities CSVs. If one doesn't exist, a fileis created, the contents of the CSVs are added to the file, and the file is uploaded to Drive. If a file already exists, that file is deleted (since Google Drive does not automatically delete older files of the same name) and a new file is uploade din the same fashion.
