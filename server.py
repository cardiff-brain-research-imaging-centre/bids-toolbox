from flask import Flask
from flask import request
from flask import send_from_directory
from flask import send_file
from flask import Response

from shutil import copytree
from shutil import copyfile
from shutil import rmtree
from distutils.dir_util import copy_tree
import os
import json
import time
import zipfile

from timeit import default_timer as timer

from dcm2bids import bidskit
from scanModality import inferScanModality

app = Flask(__name__)
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

    ## Run bidskit 1st pass 
    t = bidskit(parent_folder+'/dicom', parent_folder+'/output', data, config)
    dcm2niix_time += t

    ## Fill the bidskit configfile
    with open(parent_folder+'/derivatives/conversion/Protocol_Translator.json', 'r') as f:
        bidskit_config = json.load(f)

    any_unclassified = False #This variable will be used to flag potential undetected scan types 
    unclassified_list = []

    #For each scan tag/key, first check if the scan modality/type was provided,
    #if not, call the Toolbox heuristic to detect.
    for key in bidskit_config:
        found = False
        if 'modalities' in data['metadata']:
            for mod in data['metadata']['modalities']:
                if mod['tag'] in key:
                    bidskit_config[key][0] = mod['type']
                    bidskit_config[key][1] = mod['modality']
                    found = True
                    break

        if(found == False):
            scan_type = inferScanModality(key, parent_folder)
            if scan_type['modality'] == 'unclassified':
                any_unclassified = True
                unclassified_list.append(key)
            else:
                bidskit_config[key][0] = scan_type['type']
                bidskit_config[key][1] = scan_type['modality']

    #This if triggers is there has been any scan key with no user provided type/modality and 
    #and for which the Toolbox heuristic has not been able to classify. This stops the conversion.
    if any_unclassified:
        resp_data['status'] = 'error'
        resp_data['errorMessage'] = 'Scan modality not provided and not detected for the following tags: '
        resp_data['errorMessage'] += str(unclassified_list)

        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
	 
        return resp

    with open(parent_folder+'/derivatives/conversion/Protocol_Translator.json', "w") as f:
        json.dump(bidskit_config, f)

    ## Run bidskit 2nd pass
    t = bidskit(parent_folder+'/dicom', parent_folder+'/output', data, config)
    dcm2niix_time += t

    ## Add participants.json
    copyfile('participants.json',  parent_folder+'/output/participants.json')

    ## Store metadata for BIDS toolbox in hidden file
    with open(parent_folder+'/output/.dataset.toolbox', "w") as f:
        json.dump(data, f)

    ## Add hidden ProtocolTranslator as hidden file to dataset 
    copyfile(parent_folder+'/derivatives/conversion/Protocol_Translator.json', parent_folder+'/output/.Protocol_Translator.json')

    ## Copy local BIDS folder to output directory
    copy_tree(parent_folder+'/output', data['output'])

    ## Remove temporary working directory
    rmtree(parent_folder)

    ## Call the processing pipeline
    # To-Do, connect with SlurmD/pySlurm

    end_time = timer()

    print('createBIDS finished - dcm2niix time: '+str(round(dcm2niix_time,3))+' s, Total time: '+str(round(end_time - start_time,3))+' s')

    #Send successful conversion message
    resp_data['status'] = 'success'

    resp_js = json.dumps(resp_data)
    resp = Response(resp_js, status=200, mimetype='application/json')
 
    return resp

@app.route('/createUpload', methods = ['POST'])
def createUploadHandler():

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

    metadata = json.loads(request.values['metadata_json']) #Get JSON metadata object

    ## Create temporary working folder 
    parent_folder = '/tmp/bids_temp_'+str(time.time())

    try:
        os.mkdir(parent_folder)
    except FileExistsError:
        raise RuntimeError("BIDS Toolbox error -- Directory ",parent_folder, " already exists")

    ## Create and populate DICOM subfolder

    os.mkdir(parent_folder+'/dicom')
    print('Copying all the stuff into: '+parent_folder)

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

    ## Run bidskit 1st pass 
    t = bidskit(parent_folder+'/dicom', parent_folder+'/output', metadata, config)
    dcm2niix_time += t

    ## Fill the bidskit configfile
    with open(parent_folder+'/derivatives/conversion/Protocol_Translator.json', 'r') as f:
        bidskit_config = json.load(f)

    any_unclassified = False #This variable will be used to flag potential undetected scan types 
    unclassified_list = []

    #For each scan tag/key, first check if the scan modality/type was provided,
    #if not, call the Toolbox heuristic to detect.
    for key in bidskit_config:
        found = False
        if 'modalities' in data['metadata']:
            for mod in data['metadata']['modalities']:
                if mod['tag'] in key:
                    bidskit_config[key][0] = mod['type']
                    bidskit_config[key][1] = mod['modality']
                    found = True
                    break

        if(found == False):
            scan_type = inferScanModality(key, parent_folder)
            if scan_type['modality'] == 'unclassified':
                any_unclassified = True
                unclassified_list.append(key)
            else:
                bidskit_config[key][0] = scan_type['type']
                bidskit_config[key][1] = scan_type['modality']

    #This if triggers is there has been any scan key with no user provided type/modality and 
    #and for which the Toolbox heuristic has not been able to classify. This stops the conversion.
    if any_unclassified:
        resp_data['status'] = 'error'
        resp_data['errorMessage'] = 'Scan modality not provided and not detected for the following tags: '
        resp_data['errorMessage'] += str(unclassified_list)

        resp_js = json.dumps(resp_data)
        resp = Response(resp_js, status=200, mimetype='application/json')
	 
        return resp

    with open(parent_folder+'/derivatives/conversion/Protocol_Translator.json', "w") as f:
        json.dump(bidskit_config, f)

    ## Run bidskit 2nd pass
    t = bidskit(parent_folder+'/dicom', parent_folder+'/output', data, config)
    dcm2niix_time += t

    ## Add participants.json
    copyfile('participants.json',  parent_folder+'/output/participants.json')

    ## Store metadata for BIDS toolbox in hidden file
    with open(parent_folder+'/output/.dataset.toolbox', "w") as f:
        json.dump(data, f)

    ## Add hidden ProtocolTranslator as hidden file to dataset 
    copyfile(parent_folder+'/derivatives/conversion/Protocol_Translator.json', parent_folder+'/output/.Protocol_Translator.json')

    #Zip output folder 
    zipf = zipfile.ZipFile('download/BIDS_dataset.zip', 'w')
    for root, dirs, files in os.walk(parent_folder+'/output'):
        for file in files:
            zipf.write(os.path.join(root, file))
    zipf.close()

    #Try alternative to zipfile
    #shutil.make_archive('download/BIDS_dataset.zip', 'zip', parent_folder+'/output')

    ## Remove temporary working directory
    rmtree(parent_folder)
 
    resp_data['status'] = 'success'
    resp_js = json.dumps(resp_data)
    resp = Response(resp_js, status=200, mimetype='application/json')
 
    return resp
 

@app.route('/updateBids', methods = ['POST'])
def updateBidsHandler():

    start_time = timer()
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

    ## Run bidskit 2nd pass
    dcm2niix_time = bidskit(parent_folder+'/dicom', parent_folder+'/output', data, config)

    # Check for existence and add new items to add to dataset_description
    if len(data['metadata']['datasetDescription']) > 0:
        with open(parent_folder+'/output/dataset_description.json', 'r') as f:
            dataset_props = json.load(f)

        for item in data['metadata']['datasetDescription']:
            dataset_props[item] = data['metadata']['datasetDescription'][item]

        with open(parent_folder+'/output/dataset_description.json', "w") as f:
            json.dump(dataset_props, f)

    ## Store metadata for BIDS toolbox in hidden file
    with open(parent_folder+'/.dataset.toolbox', "w") as f:
        json.dump(data, f)

    ## Copy local BIDS folder to output directory
    copy_tree(parent_folder+'/output', data['output'])

    # Remove temporary working directory
    rmtree(parent_folder)

    ## Call the processing pipeline
    # To-Do, connect with SlurmD/pySlurm

    end_time = timer()

    print('updateBIDS finished - dcm2niix time: '+str(round(dcm2niix_time,3))+' s, Total time: '+str(round(end_time - start_time,3))+' s')
            
    #Send successful conversion message
    resp_data['status'] = 'success'

    resp_js = json.dumps(resp_data)
    resp = Response(resp_js, status=200, mimetype='application/json')
 
    return resp


@app.route('/checkDataset', methods = ['POST'])
def checkDatasetHandler():

    ## Read body message and check format
    if request.is_json == False:
        raise RuntimeError("Incorrect body message -- not a JSON file")

    message = request.get_json()
    folder = message["folder"] #Input folder to be validated 
    data = {'valid'  : 'no'} #Response message, not valid by default

    #Check if folder and hidden file exist, if so return # of subjects, if not error
    if(os.path.exists(folder)):
        if(os.path.exists(folder+'/.dataset.toolbox')):
            with open(folder+'/.dataset.toolbox', 'r') as f:
                dataset_props = json.load(f)
            data['valid'] = 'yes'
            data['subjects'] = len(dataset_props['scans'])
        else:
            data['error'] = 'Folder found but BIDS Toolbox history file not found'
    else:
        data['error'] = 'Folder not found'

    js = json.dumps(data)
    resp = Response(js, status=200, mimetype='application/json')
 
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
    return send_from_directory('download', path, as_attachment=True, attachment_filename='dataset.json')


if __name__ == '__main__':

    with open('config.json', 'r') as f:
        config = json.load(f)

    app.run(port=5000, host='0.0.0.0', debug=True)
