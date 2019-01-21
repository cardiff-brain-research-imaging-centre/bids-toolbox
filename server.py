from flask import Flask
from flask import request

from shutil import copytree
from shutil import copyfile
from shutil import rmtree
from distutils.dir_util import copy_tree
import os
import json
import time

from timeit import default_timer as timer

from dcm2bids import bidskit
from scanModality import inferScanModality

app = Flask(__name__)
config = {}

@app.route('/createBids', methods = ['POST'])
def createBidsHandler():

    start_time = timer()
    dcm2niix_time = 0.0

    ## Read body message and check format
    if request.is_json == False:
        raise RuntimeError("Incorrect body message -- not a JSON file")

    data = request.get_json()

    if 'scans' not in data:
        raise RuntimeError("Incorrect body message -- Scans key not found")
    if 'metadata' not in data:
        raise RuntimeError("Incorrect body message -- Metadata key not found")
    if 'output' not in data:
        raise RuntimeError("Incorrect body message -- Output key not found")

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

    for key in bidskit_config:
        found = False
        for mod in data['metadata']['modalities']:
            if mod['tag'] in key:
                bidskit_config[key][0] = mod['type']
                bidskit_config[key][1] = mod['modality']
                found = True

        if(found == False):
                scan_type = inferScanModality(key, parent_folder)
                bidskit_config[key][0] = scan_type['type']
                bidskit_config[key][1] = scan_type['modality']

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

    return 'CreateBIDS finished'

@app.route('/updateBids', methods = ['POST'])
def updateBidsHandler():

    start_time = timer()

    ## Read body message and check format
    if request.is_json == False:
        raise RuntimeError("Incorrect body message -- not a JSON file")

    data = request.get_json()

    if 'scans' not in data:
        raise RuntimeError("Incorrect body message -- Scans key not found")
    if 'metadata' not in data:
        raise RuntimeError("Incorrect body message -- Metadata key not found")
    if 'output' not in data:
        raise RuntimeError("Incorrect body message -- Output key not found")

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

    # To-Do: check if dataset_description is updated, if not, update it here

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
            
    return 'UpdateBIDS finished'

if __name__ == '__main__':

    with open('config.json', 'r') as f:
        config = json.load(f)

    app.run(port=5000, host='0.0.0.0', debug=True)
