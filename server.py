from flask import Flask
from flask import request
from flask import send_from_directory
from flask import Response

from shutil import copytree
from shutil import copyfile
from shutil import rmtree
from shutil import make_archive
from shutil import unpack_archive
from distutils.dir_util import copy_tree

import os
import json
import time

from timeit import default_timer as timer

from dcm2bids import bidskit
from scanModality import inferScanModality
from toolbox import *

app = Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 #Disable file caching

config = {}

@app.route('/createBids', methods = ['POST'])
def createBidsHandler():

    start_time = timer()
    dcm2niix_time = 0.0
    resp_data = {} #Object to return status at the end of function

    ## Read body message and check format
    if request.is_json == False:
        resp_data['status'] = 'error'
        resp_data['errorMessage'] = 'Incorrect body message: not a JSON file'

        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')	 
        return resp

    data = request.get_json()
    json_missing_data = False #To flag is there is some information missing in JSON message

    if 'scans' not in data:
        json_missing_data = True
        resp_data['errorMessage'] = 'Incorrect JSON message: Scans key not found'
    if 'metadata' not in data:
        json_missing_data = True
        resp_data['errorMessage'] = 'Incorrect JSON message: Metadata key not found'
    if 'output' not in data:
        json_missing_data = True
        resp_data['errorMessage'] = 'Incorrect JSON message: Output key not found'

    if json_missing_data:
        resp_data['status'] = 'error'
        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
        return resp

    ## Create temporary working folder 
    parent_folder = '/tmp/bids_temp_'+str(time.time())

    try:
        os.mkdir(parent_folder)
    except FileExistsError:
        raise RuntimeError("BIDS Toolbox error -- Directory ",parent_folder, " already exists")

    ## Create and populate DICOM subfolder

    os.mkdir(parent_folder+'/dicom')

    for sub in data['scans']:
        os.mkdir(parent_folder+'/dicom/'+sub)
        for ses in data['scans'][sub]:
            try:
                copytree(data['scans'][sub][ses], parent_folder+'/dicom/'+sub+'/'+ses)
            except:
                raise RuntimeError("BIDS Toolbox error -- Error trying to copy subject "+sub+" scan "+ses+" data in folder "+parent_folder+'/dicom/'+sub+'/'+ses)

    ## Create BIDS dataset from DICOM files
    error, dcm2niix_time = createDataset(parent_folder, data, config, resp_data)
    if error == True:
        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
        return resp        

    ## Copy local BIDS folder to output directory
    copy_tree(parent_folder+'/output', data['output'])

    ## Remove temporary working directory
    rmtree(parent_folder)

    end_time = timer()

    print('createBIDS finished - dcm2niix time: '+str(round(dcm2niix_time,3))+' s, Total time: '+str(round(end_time - start_time,3))+' s')

    #Send successful conversion message
    resp_data['status'] = 'success'

    resp_js = json.dumps(resp_data)
    resp = Response(resp_js, status=200, mimetype='application/json')
 
    return resp


@app.route('/createBidsGUI', methods = ['POST'])
def createBidsGUIHandler():

    start_time = timer()
    dcm2niix_time = 0.0
    resp_data = {} #Object to return status at the end of function

    #Check that DICOM files are provided
    if len(request.files) == 0:
        resp_data['status'] = 'error'
        resp_data['errorMessage'] = 'No DICOM files provided for creation of dataset'
        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
        return resp

    #Load JSON with metadata from POST data
    data = json.loads(request.values['metadata_json']) 

    ## Create temporary working folder 
    parent_folder = '/tmp/bids_temp_'+str(time.time())

    try:
        os.mkdir(parent_folder)
    except FileExistsError:
        raise RuntimeError("BIDS Toolbox error -- Directory ",parent_folder, " already exists")

    ## Create and populate DICOM subfolder
    os.mkdir(parent_folder+'/dicom')
    
    for f in request.files:
        #The file object is named 'file_X_Y_Z'
        sub = f.split("_")[1] # where X is the subject ID
        ses = f.split("_")[2] # and Y is the session ID
        
        if not os.path.isdir(parent_folder+'/dicom/'+sub):
            os.mkdir(parent_folder+'/dicom/'+sub)
        if not os.path.isdir(parent_folder+'/dicom/'+sub+'/'+ses):
            os.mkdir(parent_folder+'/dicom/'+sub+'/'+ses)

        fobj = request.files[f]
        filename = fobj.filename
        fobj.save(os.path.join(parent_folder+'/dicom/'+sub+'/'+ses ,filename)) 

    ## Create BIDS dataset from DICOM files
    error, dcm2niix_time = createDataset(parent_folder, data, config, resp_data)
    if error == True:
        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
        return resp        

    #Zip output folder 
    dataset_name = ''
    if 'Name' in data['metadata']['datasetDescription']:
        dataset_name = data['metadata']['datasetDescription']['Name']
    else:
        dataset_name = time.strftime("%Y-%m-%d_%H:%M:%S")
    make_archive('download/BIDS_'+dataset_name, 'zip', parent_folder+'/output')

    ## Remove temporary working directory
    rmtree(parent_folder)
 
    resp_data['status'] = 'success'
    resp_data['zipfile'] = 'BIDS_'+dataset_name+'.zip' 
    resp_js = json.dumps(resp_data)
    resp = Response(resp_js, status=200, mimetype='application/json')
 
    return resp
 

@app.route('/updateBids', methods = ['POST'])
def updateBidsHandler():

    start_time = timer()
    dcm2niix_time = 0.0
    resp_data = {} #Object to return status at the end of function

    ## Read body message and check format
    if request.is_json == False:
        resp_data['status'] = 'error'
        resp_data['errorMessage'] = 'Incorrect body message: not a JSON file'

        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')	 
        return resp

    data = request.get_json()
    json_missing_data = False #To flag is there is some information missing in JSON message

    if 'scans' not in data:
        json_missing_data = True
        resp_data['errorMessage'] = 'Incorrect JSON message: Scans key not found'
    if 'metadata' not in data:
        json_missing_data = True
        resp_data['errorMessage'] = 'Incorrect JSON message: Metadata key not found'
    if 'output' not in data:
        json_missing_data = True
        resp_data['errorMessage'] = 'Incorrect JSON message: Output key not found'

    if json_missing_data:
        resp_data['status'] = 'error'
        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
        return resp

    ## Create temporary working folder 
    parent_folder = '/tmp/bids_temp_'+str(time.time())
    try:
        os.mkdir(parent_folder)
    except FileExistsError:
        raise RuntimeError("BIDS Toolbox error -- Directory ",parent_folder, " already exists")

    ## Populate working folder
    os.mkdir(parent_folder+'/output')
    copy_tree(data['output'], parent_folder+'/output')

    os.mkdir(parent_folder+'/derivatives')
    os.mkdir(parent_folder+'/derivatives/conversion')
    copyfile(parent_folder+'/output/.Protocol_Translator.json', parent_folder+'/derivatives/conversion/Protocol_Translator.json')

    os.mkdir(parent_folder+'/work')
    os.mkdir(parent_folder+'/work/conversion')
    os.mkdir(parent_folder+'/dicom')

    with open(parent_folder+'/output/.dataset.toolbox', 'r') as f:
        dataset_props = json.load(f)

    ## Add DICOM files for new subjects/scans to /dicom
    for sub in data['scans']:
        if sub in dataset_props['scans']:
            for scan in data['scans'][sub]:
                if scan not in dataset_props['scans'][sub]:
                    try:
                        copytree(data['scans'][sub][scan], parent_folder+'/dicom/'+sub+'/'+scan)
                    except:
                        raise RuntimeError("BIDS Toolbox error -- Error trying to copy subject "+sub+" scan "+scan+" data in folder "+parent_folder+'/dicom/'+sub+'/'+scan)
        else:
            os.mkdir(parent_folder+'/dicom/'+sub)
            for scan in data['scans'][sub]:
                try:
                    copytree(data['scans'][sub][scan], parent_folder+'/dicom/'+sub+'/'+scan)
                except:
                    raise RuntimeError("BIDS Toolbox error -- Error trying to copy subject "+sub+" scan "+scan+" data in folder "+parent_folder+'/dicom/'+sub+'/'+scan)
    
    ## Update dataset with new information 
    dcm2niix_time = updateDataset(parent_folder, data, config)   

    ## Copy local BIDS folder to output directory
    copy_tree(parent_folder+'/output', data['output'])

    # Remove temporary working directory
    rmtree(parent_folder)

    end_time = timer()

    print('updateBIDS finished - dcm2niix time: '+str(round(dcm2niix_time,3))+' s, Total time: '+str(round(end_time - start_time,3))+' s')
            
    #Send successful conversion message
    resp_data['status'] = 'success'

    resp_js = json.dumps(resp_data)
    resp = Response(resp_js, status=200, mimetype='application/json')
 
    return resp


@app.route('/updateBidsGUI', methods = ['POST'])
def updateBidsGUIHandler():

    start_time = timer()
    dcm2niix_time = 0.0 
    resp_data = {} #Object to return status at the end of function

    ## Create temporary working folder 
    parent_folder = '/tmp/bids_temp_'+str(time.time())
    try:
        os.mkdir(parent_folder)
    except FileExistsError:
        raise RuntimeError("BIDS Toolbox error -- Directory ",parent_folder, " already exists")

    ## Get dataset from POST data and unzip
    fobj = request.files['dataset_zip']
    fobj.save(os.path.join(parent_folder, 'original.zip')) 
    unpack_archive(os.path.join(parent_folder, 'original.zip'), parent_folder+'/output' , 'zip')
    os.remove(os.path.join(parent_folder, 'original.zip'))

    ## Check if dataset contains hidden toolbox file
    if not (os.path.exists(parent_folder+'/output/.dataset.toolbox')):
        resp_data['status'] = 'error'  
        resp_data['errorMessage'] = 'Malformed BIDS dataset in zipfile: .dataset.toolbox file not found'
        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
        return resp

    #Load JSON with metadata from POST data
    data = json.loads(request.values['metadata_json']) 

    #Populate working folder
    os.mkdir(parent_folder+'/derivatives')
    os.mkdir(parent_folder+'/derivatives/conversion')
    copyfile(parent_folder+'/output/.Protocol_Translator.json', parent_folder+'/derivatives/conversion/Protocol_Translator.json')

    os.mkdir(parent_folder+'/work')
    os.mkdir(parent_folder+'/work/conversion')
    os.mkdir(parent_folder+'/dicom')

    with open(parent_folder+'/output/.dataset.toolbox', 'r') as f:
        dataset_props = json.load(f)

    for f in request.files:
        if 'file' in f: #Avoid 'dataset_zip' file
            #The file object is named 'file_X_Y_Z'
            sub = f.split("_")[1] # where X is the subject ID
            ses = f.split("_")[2] # and Y is the session ID
            
            if not os.path.isdir(parent_folder+'/dicom/'+sub):
                os.mkdir(parent_folder+'/dicom/'+sub)
            if not os.path.isdir(parent_folder+'/dicom/'+sub+'/'+ses):
                os.mkdir(parent_folder+'/dicom/'+sub+'/'+ses)

            fobj = request.files[f]
            filename = fobj.filename
            fobj.save(os.path.join(parent_folder+'/dicom/'+sub+'/'+ses ,filename)) 
    
    ## Update dataset with new information 
    dcm2niix_time = updateDataset(parent_folder, data, config)

    # Zip output folder 
    dataset_name = ''
    if 'Name' in dataset_props:
        dataset_name = dataset_props['Name']
    else:
        dataset_name = time.strftime("%Y-%m-%d_%H:%M:%S")

    if os.path.exists('download/BIDS_'+dataset_name+'.zip'):
        os.remove('download/BIDS_'+dataset_name+'.zip')

    make_archive('download/BIDS_'+dataset_name, 'zip', parent_folder+'/output')

    # Remove temporary working directory
    rmtree(parent_folder)

    end_time = timer()

    print('updateBIDS finished - dcm2niix time: '+str(round(dcm2niix_time,3))+' s, Total time: '+str(round(end_time - start_time,3))+' s')
    
    # Respond with OK and name of dataset
    resp_data['status'] = 'success'
    resp_data['zipfile'] = 'BIDS_'+dataset_name+'.zip' 
    resp_js = json.dumps(resp_data)
    resp = Response(resp_js, status=200, mimetype='application/json')
 
    return resp


@app.route('/')
def home():
    file = open('gui/index.html','r')
    html_string = file.read()
    file.close()
    return html_string

@app.route('/gui/<path:path>')
def send_gui_files(path):
    return send_from_directory('gui', path)

@app.route('/download/<path:path>')
def send_zip_files(path):
    return send_from_directory('download', path, as_attachment=True)


if __name__ == '__main__':

    with open('config.json', 'r') as f:
        config = json.load(f)

    app.run(port=5000, host='0.0.0.0', debug=True)
