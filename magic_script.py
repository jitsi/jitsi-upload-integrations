import json
import datetime
import pytz
import os
from pytz import timezone
from datetime import datetime
import logging
import boto3
from sys import argv
from botocore.exceptions import ClientError
import sys

CONFIGFILE = "config.json"
with open(CONFIGFILE) as data:
    config_v = json.load(data)

class Namer:
    def name(self, config_v, orig_name, timezone, name_format):
        dateTime = datetime.now(timezone)
        name_raw = name_format.format(H = dateTime.hour, 
                               M = dateTime.minute,
                               S = dateTime.second,
                               DD = dateTime.day,
                               MM = dateTime.month,
                               YY = dateTime.year)
        name = name_raw + os.path.splitext(orig_name)[1]
        return name
 
    #proposed use of mediainfo but as codecs are limited and not lot of variety so not sure.

class upload:
    def __init__(self, creds, filepath):
        self.creds = creds
        self.params = {}
        self.params['filepath'] = filepath
        self.params['object_name'] = None
        self.call_cloud()
    
    #def call_cloud(self):
    #if(config_v['options']['enable_rename']):
     #   self.new_file_name = Namer.name(config_v, self.file_name, config_v['options']['timezone'], config_v['options']['name_format'] )
    #else:
    #    self.new_file_name = None
    #disabled due to testing    
    #admin_upload = upload(config_v['cloud'], self.file_name) #self.new_file_name)
    #---Not-in-use-in-test--renaming---
        
        #FILTER FILE NAME AND PATH BEFORE SENDING
        #match self.creds['name']:
            #case s3:
            #self.s3()
            #case default:
            #    return "something"
        
    def call_cloud(self):
        #call s3 class and perform upload
        s3c = s3(self.creds, self.params)
        return s3c.start_upload()


class s3:
    def __init__(self, s3, params):
        if 'endpoint' in s3:
            #NON-AWS
            self.s3 = boto3.client('s3' ,aws_access_key_id = s3['access_key'] ,aws_secret_access_key = s3['secret_key'] ,endpoint_url = s3['endpoint'],
            region_name = s3['region'])
        else:
            #AWS
            self.s3 = boto3.resource('s3' ,aws_access_key_id = s3['access_key'] ,aws_secret_access_key = s3['secret_key'], region_name = s3['region'])

        self.bucket = s3['bucket']
        self.file_path = params['filepath']
        self.object_name = params['object_name']
                
    def start_upload(self):
        if self.object_name is None:
            self.object_name = os.path.basename(self.file_path)
        try:
            response = self.s3.upload_file(self.file_path, self.bucket, self.object_name)
        except ClientError as e:
            logging.error(e)
            return False
        return True
    
class call:
  def __init__(self, dir_name):
    #, type=user):
    self.dir_name = dir_name
    #self.type = type
    self.start()

  #def start(self):
#    if(self.type == s3):
#        self.admin()
#    if(self.type == user):
#        self.user()


  def start(self):
    walks = os.walk(self.dir_name)
    for source, dirs, files in walks:
        for filename in files:
            ext = os.path.splitext(filename)[1]
            ext_na = ['.py', '.exe']
            if ext not in ext_na:
                tname = source + '/' + filename
                start_upload = upload(config_v['s3'], tname) 
                # Invoke upload function
            
    if(start_upload == True):
        #Upload Done
        sys.exit(0)
    else:
        #Upload Failed
        sys.exit(2)
    
  #def user():
    #here upload paramers and creds call        
        
def main():
    n = len(sys.argv)
    if(n>=1):
        mycall = call(argv[1])
    
if __name__ == "__main__":
    main()

