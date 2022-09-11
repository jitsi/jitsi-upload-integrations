import json
import datetime
#import pytz
import os
#from pytz import timezone
from datetime import datetime
import logging
import boto3
from sys import argv
from botocore.exceptions import ClientError
import sys
import dropbox
from boxsdk import OAuth2, Client


CONFIGFILE = "/mnt/gsoc/test/s3/config.json"
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

class s3_remote:
    def __init__(self, creds, params):
        if 'endpoint' in creds:
            #NON-AWS
            self.s3 = boto3.client('s3' ,aws_access_key_id = creds['access_key'] ,aws_secret_access_key = creds['secret_key'] ,endpoint_url = creds['endpoint'], region_name = creds['region'])
        else:
            #AWS
            self.s3 = boto3.resource('s3' ,aws_access_key_id = creds['access_key'] ,aws_secret_access_key = creds['secret_key'], region_name = creds['region'])
        self.bucket = creds['bucket']
        self.file_path = params['filepath']
        try:
            self.object_name = params['object_name']
        except KeyError:
            self.object_name = os.path.basename(self.file_path)

        #self.object_name = params['object_name']
                
    def upload(self):
        #if self.object_name is None:
        #    self.object_name = os.path.basename(self.file_path)
        try:
            response = self.s3.upload_file(self.file_path, self.bucket, self.object_name)
            return True
        except Exception as err:
            logging.error(err)
            return False
        

class dropbox_remote:
    def __init__(self, creds, params):
        self.creds = creds
        self.params = params
    def upload(self, timeout=900, chunk_size=25 * 1024 * 1024,):
        dbx = dropbox.Dropbox(self.creds['access_token'], timeout=timeout)
        with open(self.params['filepath'], "rb") as f:
            file_size = os.path.getsize(self.params['filepath'])
            if file_size <= chunk_size:
                try:
                    result = dbx.files_upload(f.read(), self.params['remotepath'])
                except Exception as err:
                    if (type(err).__name__ == 'AuthError'):
                        #AUTH TOKEN ERROR
                        logging.error(err)
                    result = False
                if(result != False):
                    result = True
                return result
                #---------
            else:
                try:
                    upload_session_start_result = dbx.files_upload_session_start(f.read(chunk_size))
                    cursor = dropbox.files.UploadSessionCursor(session_id=upload_session_start_result.session_id, offset=f.tell(),)
                    commit = dropbox.files.CommitInfo(path=self.params['remotepath'])
                    return result
                except Exception as err:
                    logging.error(err)
                    #if (type(err).__name__ == 'AuthError'):
                        #AUTH TOKEN ERROR
                    result = False
                while f.tell() < file_size:
                    if (file_size - f.tell()) <= chunk_size:
                        try:
                            result = dbx.files_upload_session_finish(
                                f.read(chunk_size), cursor, commit
                            )
                        except Exception as err:
                            logging.error(err)
                            result = False
                        if(result != False):
                            result = True
                        #---------
                    else:
                        try:
                            dbx.files_upload_session_append(
                            f.read(chunk_size),
                            cursor.session_id,
                            cursor.offset,
                            )
                        except Exception as err:
                            logging.error(err)
                            result = False
                            return result
                        cursor.offset = f.tell()

class box_remote:
    def __init__(self, box, params): 
        self.auth = OAuth2(
            client_id= box['client_id'],
            client_secret= box['client_secret'],
            access_token= box['access_token'],
        )
        self.client = Client(self.auth)
        self.filepath = params['filepath']
        self.remotepath = params['remotepath']

    def navigate_folder(self, name, id=0):
        folder = self.client.folder(id).get_items()
        done = False
        for i in folder:
            if(i['type'] == 'folder' and i['name'] == name):
                #is a folder and need to get this folder id and return it.
                folder_id = i['id']
                done = True
        if not done:
            #create new folder now
            folder_id = self.client.folder(id).create_subfolder(name)['id']
        return folder_id

    def process_path(self, dir):
        allparts = []
        while 1:
            parts = os.path.split(dir)
            if parts[0] == dir:
                allparts.insert(0, parts[0])
                break
            elif parts[1] == dir:
                allparts.insert(0, parts[1])
                break
            else:
                dir = parts[0]
                allparts.insert(0, parts[1])
        id = 0
        for dir_i in allparts:
            file_ext = os.path.splitext(dir_i)[1]
            if len(file_ext) == 0:
                if not dir_i == '/' and not len(dir_i) == 0:
                    id = self.navigate_folder(dir_i, id)
        return id

    def upload_file(self):
        file_size = os.path.getsize(self.filepath)
        if (file_size < 20000000):
            try:
                new_file = self.client.folder(self.process_path(self.remotepath)).upload(self.filepath)
                return True
            except Exception as err:
                if(err.code == 'item_name_in_use'):
                    print("Change the name")
                logging.error(err)
                return False
        else:
            try:
                chunked_uploader = self.client.folder(self.process_path(self.remotepath)).get_chunked_uploader(self.filepath)
                uploaded_file = chunked_uploader.start()
                return True
            except Exception as err:
                if(err.code == 'item_name_in_use'):
                    print("Change the name")
                logging.error(err)
                return False

class upload:
    def __init__(self, mname, filepath):
        with open(mname) as data:
            self.metadata = json.load(data)
        self.params = {}
        self.params['filepath'] = filepath
        #self.params['remotepath'] = None
        #self.call_cloud()
    
    def call_cloud(self):
        #if(config_v['options']['enable_rename']):
     #   self.new_file_name = Namer.name(config_v, self.file_name, config_v['options']['timezone'], config_v['options']['name_format'] )
    #else:
    #    self.new_file_name = None
    #disabled due to testing    
    #admin_upload = upload(config_v['cloud'], self.file_name) #self.new_file_name)
    #---Not-in-use-in-test--renaming---
        
        #FILTER FILE NAME AND PATH BEFORE SENDING
        remote = self.metadata['upload_credentials']['service_name']
        try:
            self.params['remotepath'] = self.metadata['upload_credentials']['remotepath']    
        except KeyError:
            self.params['remotepath'] = 'Jitsi/'
        
        if(remote == 's3'):
            return self.s3()
        if(remote == 'box'):
            return self.boxs()
        if(remote == 'dropbox'):
            return self.dropb()
        
    def s3(self):
        self.creds = config_v['s3']        
        s3r = s3_remote(self.creds, self.params)
        return s3r.upload()
    
    def dropb(self):
        self.creds = self.metadata['upload_credentials']
        dpr = dropbox_remote(self.creds, self.params)
        return dpr.upload()

    def boxs(self):
        self.creds = self.metadata['upload_credentials']
        box = box_remote(self.creds, self.params)
        return box.upload_file()

class call:
  def __init__(self, dir_name):
    self.dir_name = dir_name
    self.start()

  def start(self):
    walks = os.walk(self.dir_name)
    for source, dirs, files in walks:
        if(source.endswith('/')):
            mname = source + 'metadata.json'
        else:
            mname = source + '/metadata.json'
        for filename in files:
            ext = os.path.splitext(filename)[1]
            ext_allowed = ['.jpg', '.mp4']
            if ext in ext_allowed:
                if(source.endswith('/')):
                    tname = source + filename
                else:
                    tname = source + '/' + filename
                start_upload = upload(mname, tname).call_cloud()  
                if(start_upload == True):
                    #Upload Done
                    sys.exit(0)
                else:
                    #Upload Failed
                    sys.exit(2)
        
def main():
    n = len(sys.argv)
    if(n>=1):
        mycall = call(argv[1])

if __name__ == "__main__":
    main()

