from __future__ import print_function  # Python 2/3 compatibility
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError
from datetime import datetime
import io
import csv
from operator import itemgetter
import base64
import urllib
import urllib.request
import urllib.error
import urllib.parse
import sys
import json
import os
import boto3
import botocore
import decimal
import collections
import time
from time import gmtime, strftime
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive


#-------------------------------------- MAKE CSV PARAMETERS ------------------------------------------
# Helper class to convert a DynamoDB item to JSON.
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

revoke = False
key_tabledb = dynamodb.Table('Keys')

baseDate = "YYYY-MM-DD" #Set to the beginning of the semester, used for urls and refreshing data.

#Use this URL to refresh the access token
TokenURL = "https://api.fitbit.com/oauth2/token"

#From the developer site, add b for base64 encode
OAuthTwoClientID = b"*******"
ClientOrConsumerSecret = b"*********************"
concatCode = OAuthTwoClientID + b":" + ClientOrConsumerSecret

#Some constants defining API error handling responses
ErrorInAPI = "Error when making API call that I couldn't handle"

userTable = key_tabledb.scan()
#print(userTable)
#print(len(userTable['Items']))
#-------------------------------------- END MAKE CSV PARAMETERS ----------------------------------------

#-------------------------------------- GOOGLE DRIVE API PARAMETERS ------------------------------------
# authorization parameters for google drive api
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'service_keys.json' #Not included
#------------------------------------- END GOOGLE DRIVE API PARAMETERS ---------------------------------

#--------------------TOKEN: ACCESS / REFRESH FUNCTIONS--------------------------
def GetNewAccessToken(RefToken, user_id, d2lid, ou):
    #Form the data payload
    BodyText = {'grant_type': 'refresh_token',
                'refresh_token': RefToken}
    #URL Encode it
    BodyURLEncoded = urllib.parse.urlencode(BodyText).encode('utf-8')

    #Start the request
    tokenreq = urllib.request.Request(TokenURL, BodyURLEncoded)

    #Add the headers, first we base64 encode the client id and client secret with a : inbetween and create the authorisation header
    base64string = base64.b64encode(concatCode)
    tokenreq.add_header(b'Authorization', b'Basic %s' % base64string)
    tokenreq.add_header(b'Content-Type', b'application/x-www-form-urlencoded')
    #Fire off the request
    try:
        tokenresponse = urllib.request.urlopen(tokenreq)

        #See what we got back.  If it's this part of  the code it was OK
        FullResponse = tokenresponse.read()

        #Need to pick out the access token and write it to the config file.  Use a JSON manipluation module
        ResponseJSON = json.loads(FullResponse)
        print("New Token Response")
        print(ResponseJSON)
        print("------------------")

        #Read the access token as a string
        NewAccessToken = str(ResponseJSON['access_token'])
        NewRefreshToken = str(ResponseJSON['refresh_token'])

        #Write new tokens to database (DynamoDB)
        response = key_tabledb.put_item(
            Item={
                'user_id': user_id,
                'access_token': NewAccessToken,
                'refresh_token': NewRefreshToken,
                'd2lid': d2lid,
                'ou': ou
            }
        )
        return { "newAccessToken": NewAccessToken, "newRefreshToken": NewRefreshToken }

    except urllib.error.URLError as e:
        #Getting to this part of the code means we got an error
        print(e.code)
        print(e.reason)
        print("--------An error was raised when getting the access token.  Need to stop here--------")
        
        
        #This error typically means that the user has revoked persmissions to the app.
        #Expect this error towards the end of the semester.
        #App compensates by skipping over the user and deleting user from DynamoDB database.
        if (e.code == 400):
            global revoke 
            revoke = True
            
            key_tabledb.delete_item(
                Key={
                    'user_id': user_id,
                }
            )            
            
            print(d2lid)
            print(user_id)
            print(ou)
            print("Invalid permissions from user. Skipping to next user.")
            pass
            
            
        


def MakeAPICall(InURL, AccToken, RefToken, user_id, d2lid, ou):
    #Start the request
    req = urllib.request.Request(InURL)

    #Add the access token in the header
    req.add_header('Authorization', 'Bearer ' + AccToken)

    #Fire off the request
    print("Making API Call")
    print(d2lid)
    try:
        #Do the request
        response = urllib.request.urlopen(req)
        #Read the response
        FullResponse = response.read()
        print(FullResponse)
        print("-"*40)

        #Return values
        return True, FullResponse
    #Catch errors, e.g. A 401 error that signifies the need for a new access token
    except urllib.error.URLError as e:
        ErrorInAPI = e
        print("Got this HTTP error: " + str(e.code))
        # HTTPErrorMessage = e.read()
        # print("This was in the HTTP error message: " + HTTPErrorMessage)
        #See what the error was
        if (e.code == 401):
            print("Access token expired. Getting new access token now.")
            print("Expired Tokens")
            print(AccToken)
            print(RefToken)
            print("-"*40)
            newTokens = GetNewAccessToken(RefToken, user_id, d2lid, ou)
            ## Query for new ref and acc token here
            AccToken = newTokens['newAccessToken']
            RefToken = newTokens['newRefreshToken']
            

            ## Put Recursive Function Here
            print("New Tokens")
            print(AccToken)
            print(RefToken)
            print("Making Second API Call with New Tokens")
            #get new return values by running recursive function and return them to handler
            new_return_values = MakeAPICall(InURL, AccToken, RefToken, user_id, d2lid, ou)
            return new_return_values
        #Return that this didn't work, allowing the calling function to handle it
        return False, ErrorInAPI

#------------------------------- GOOGLE DRIVE API ACCESS FUNCTIONS --------------------------------
def get_drive_handle():
    gauth = GoogleAuth()
    gauth.credentials = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPES)
    drive = GoogleDrive(gauth)
    return drive

#-----------------------------FUNCTIONS FOR HANDLING SPECIFIC API DATA-----------------------------#

def add_activities_data_complete(d, response, d2lid):
    
    didItCount = True
        
    try:
        # Use this to troubleshoot individuals Full Responses
        usersToCheck = []
        if d2lid in usersToCheck:
            print("-------------------------------------1")
            print("Detailed Response Check for: " + d2lid)
            print(response)
            print("-------------------------------------1")

        # where activity was logged from
        logType = response['logType']
        d['LogType'] = logType

        # when activity was started in original string format
        originalStartTime = response['originalStartTime']
        d['Start Time'] = originalStartTime
                
        if response.get('pace') != None:
            pace = response['pace']
            d['Pace'] = '%0.2f' % pace # give pace to two places past decimal
        else:
            d['Pace'] = 'N/A'

        if response.get('distance') != None:
            distance = response['distance']
            d['Distance'] = '%0.2f' % distance # give distance to two places past decimal
        else:
            d['Distance'] = 'N/A'
                    
        if response.get('steps') != None:
            d['Steps'] = response['steps']
        else:
            d['Steps'] = 'N/A'

        if response.get('source') != None:
            d['Device/Source'] = response['source']['name']
        else:
            d['Device/Source'] = 'N/A'

        d['Duration (ms)'] = response['duration']

        if response.get('heartRateZones') != None:
            zones = response['heartRateZones']
            for z in zones:
                name = z['name']
                m = z['minutes']
                #print(type(m))
                if name == 'Fat Burn':
                    d['Fat Burn (min)'] = m
                elif name == 'Cardio':
                    d['Cardio (min)'] = m
                elif name == 'Peak':
                    d['Peak (min)'] = m
                elif name == 'Out of Range':
                    d['Out of Range (min)'] = m
                    #print(type(d['Out of Range (min)']))
        else:    
            d['Fat Burn (min)'] = 'N/A'
            d['Cardio (min)'] = 'N/A'
            d['Peak (min)'] = 'N/A'
            d['Out of Range (min)'] = 'N/A'
            didItCount = False
            d['Why?'] += ' No heart rate zone data detected. '
                            
        if logType == 'auto_detected': #do not count auto-detected activities
            didItCount = False
            d['Why?'] += ' Invalid logger type: auto-detected. '

        if d['Fat Burn (min)'] == 0 and d['Cardio (min)'] == 0 and d['Peak (min)'] == 0:
            didItCount = False
            d['Why?'] += ' Heart rate zone data out of range. '
                    
        if didItCount == True:
            d['Did it count?'] = 'Yes'
            d['Why?'] = 'N/A'
        elif didItCount == False:
            d['Did it count?'] = 'No'

    except KeyError as e:
        print(d2lid)
        print("key error in add_activities_data adding activity data for a single day; No Data(?) Activity added away from Fitbit Watch(?) Unsupported Fitbit Watch(?)")
        print(e)
        print(response)
        print("-----------------")

    return d

#----------------------------Alphabetize------------------------------

def reverseName(name):
    inputName = name.split(' ')
    reverseName = inputName[-1::-1]
    outputName = ', '.join(reverseName)
    return outputName

#-----------------------------MAIN LAMBDA HANDLER-------------------------------
def lambda_handler(event, context):
    
    activitiesURL = "https://api.fitbit.com/1/user/-/activities/list.json?afterDate=" + baseDate + "&sort=desc&limit=100&offset=0"
    profileURL = "https://api.fitbit.com/1/user/-/profile.json"

    result = []
    inactive_users = []

    for n in userTable["Items"]:
        user_id = n["user_id"]
        AccessToken = n["access_token"]
        RefreshToken = n["refresh_token"]
        d2lid = n["d2lid"]
        ou = n['ou']
    # -----------------------------FITBIT--------------------------------------
        
    #--------------------------------------Start Profile API call--------------------------------------
        if d2lid not in inactive_users:
            print(d2lid)
            APICallOK, APIResponse = MakeAPICall(profileURL, AccessToken, RefreshToken, user_id, d2lid, ou)
            if APICallOK:
                APIProfileResponse = json.loads(APIResponse)
                print(APIProfileResponse['user']['fullName'])
                #get name, age, and weight information from API call
                for entry in APIProfileResponse:
                    age = APIProfileResponse[entry]["age"]
                    weight = APIProfileResponse[entry]["weight"]
                    fullName = APIProfileResponse[entry]["fullName"]
                    name = reverseName(fullName)
            else:
                print('There was and error in the API. Skipping to next user.')
                pass
    #--------------------------------------Finish Profile API call--------------------------------------
    
    #--------------------------------------Start Activities API call--------------------------------------   
            APICallOK, APIResponse = MakeAPICall(activitiesURL, AccessToken, RefreshToken, user_id, d2lid, ou)
            if APICallOK:        
                APIActivitiesResponse = json.loads(APIResponse) #activity data for each profile
                response = APIActivitiesResponse['activities']
                print(APIActivitiesResponse)
                for activity in response:
                    #start with fresh dictionary each time
                    d = {"Name": name, "Username": d2lid, "Course ID": ou, "Age": age, "Weight": weight, "Device/Source": 0, "LogType": 0, 
                            "Start Time": 0, "Duration (ms)": 0, "Out of Range (min)": 0, "Fat Burn (min)": 0, 
                            "Cardio (min)": 0, "Peak (min)": 0, "Pace": 0, "Distance": 0, "Steps": 0, "Did it count?": 0, "Why?": ''}
                    d = add_activities_data_complete(d, activity, d2lid) #fill each activity into dictionary based on profile data
                    result.append(d) #append each activity to list
            else:            
                print('There was and error in the API. Skipping to next user.')
                pass
    #--------------------------------------Finish Activities API call--------------------------------------

    #--------------------------------------SET UP GOOGLE DRIVE ENVIRONMENT---------------------------------
    drive = get_drive_handle()

    folder_name = 'WalkingDataCompleteCSV'
    folder_metadata = {'title' : folder_name, 'mimeType' : 'application/vnd.google-apps.folder'}
    
    # call up list of files in service account drive
    file_list = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
    #if there are no files in the root, create one or else python will not recognize to run the proceeding for loop
    if len(file_list) == 0:
        metadata = {'title' : 'basis', 'mimeType' : 'application/vnd.google-apps.folder'}
        basis = drive.CreateFile(metadata)
        basis.Upload()
        file_list.append(basis)
    
    for folder in file_list:
        if folder['title']==folder_name:
            folderid = folder['id']
            #print("This folder exists.")
            #insert new permission to get access to folder saved in service account
            folder.InsertPermission({
                'type':  'user'
                ,'value': <'DEV ACCT EMAIL'>
                ,'role':  'writer'
                })  
            break
        else:
            new_folder = drive.CreateFile(folder_metadata)
            new_folder.Upload()
            folderid = new_folder['id']
            new_folder.InsertPermission({
                'type':  'user'
                ,'value': 'olfapps@online.uga.edu'
                ,'role':  'writer'
                })  
            #print("Done.")
            break

    #call list of files in folder
    file_folder_list = drive.ListFile({'q': "'%s' in parents and trashed=false" % folderid}).GetList()
    #-------------------------------END SET UP GOOGLE DRIVE ENVIRONMENT-------------------------------

    ouList = set([])
    for ou in result:    
        currentOU = ou["Course ID"]
        ouList.add(currentOU)   

#----------------------------------CREATE GOOGLE DRIVE CSV FILES---------------------------------------   
    for course in ouList:
        filename = 'complete' + course
        print("Creating CSV")
        metadata = {'title': filename + '.csv', 'mimeType': 'text/csv',
            "parents": [{"kind": "drive#fileLink", "id": folderid}]}
        itemList = []
        with open('/tmp/' + filename + '.csv', 'w') as infile:
            writer = csv.writer(infile)
            i = 0
            for d in result: # write each activity into row in file for course number
                if d['Course ID'] == course:
                    if i == 0:
                        headers = list(d.keys())                                
                        itemList.append(headers) #append headers to top of item list
                        i = i + 1
                    row = list(d.values())
                    writer.writerow(row)
            infile.close()
        
        #create sorted list of student data, alphabetized by name from temp csv file
        data = csv.reader(open('/tmp/' + filename + '.csv'), delimiter=',')
        sortedList = sorted(data, key=itemgetter(0))
        #add sorted data to item list under headers
        for x in sortedList:
            itemList.append(x)
        #write sorted items to csv file
        with open('/tmp/' + filename + '.csv', 'w') as outfile:
            writer = csv.writer(outfile, delimiter=',')
            for row in itemList:
                writer.writerow(row)
            outfile.close()
        #print(itemList)

        #get contents from file
        f = open('/tmp/' + filename + '.csv', 'r')
        contents = f.read()
        f.close()
            
        for dat_file in file_folder_list:
            if dat_file['title'] == filename + '.csv':
                timestamp = dat_file['createdDate']
                dat_file['title'] = filename + '-' + timestamp + '.csv' #add timestamp to existing file
                dat_file.Upload()
                #print('title: %s' % dat_file['title'])

        #upload to drive
        csvfile = drive.CreateFile(metadata)
        csvfile.SetContentString(contents)
        csvfile.Upload()            
#-----------------------------------------CREATE RUNTIME.TXT------------------------------------------
    filename = 'runtime.txt'
    for dat_file in file_folder_list:
            if dat_file['title'] == filename:
                dat_file.Delete()
            else:
                pass
    os.environ["TZ"]="US/Eastern"
    time.tzset()
    logTime = strftime("%a, %b %d, %Y - %H:%M:%S", time.localtime())
    runtime=open('/tmp/' + filename,'w+')
    runtime.write(logTime)
    runtime.close()

    f = open('/tmp/' + filename,'r')
    contents = f.read()
    f.close()
            
    metadata = {'title': filename, 'mimeType': 'text/csv',
            "parents": [{"kind": "drive#fileLink", "id": folderid}]}
    runtimefile = drive.CreateFile(metadata)
    runtimefile.SetContentString(contents)
    runtimefile.Upload()
