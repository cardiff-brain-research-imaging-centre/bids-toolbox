from flask import Flask
from flask import request

from shutil import copytree
from shutil import copyfile
import os
import json
import time

from dcm2bids import bidskit

app = Flask(__name__)

@app.route('/createBids', methods = ['POST'])
def createBidsHandler():

    if request.is_json == False:
        raise RuntimeError("Incorrect body message -- not a JSON file")

    data = request.get_json()
    
    ### Create DICOM folder structure

    # Create temporary folder to arrange DICOM files
    parent_folder = '/tmp/bids_temp_'+str(time.time())

    try:
        os.mkdir(parent_folder)
    except FileExistsError:
        print("Directory ",parent_folder, " already exists")

    # Create and populate DICOM subfolder
    os.mkdir(parent_folder+'/dicom')

    for sub in data['scans']:
        os.mkdir(parent_folder+'/dicom/'+sub)
        for ses in data['scans'][sub]:
            copytree(data['scans'][sub][ses], parent_folder+'/dicom/'+sub+'/'+ses)

    ### Run bidskit 1st pass 
    bidskit(parent_folder+'/dicom', parent_folder+'/output', data)

    ### Fill the bidskit configfile
    with open(parent_folder+'/derivatives/conversion/Protocol_Translator.json', 'r') as f:
        bidskit_config = json.load(f)

    for key in bidskit_config:
        for mod in data['metadata']['modalities']:
            if mod['tag'] in key:
                bidskit_config[key][0] = mod['type']
                bidskit_config[key][1] = mod['modality']
  
    with open(parent_folder+'/derivatives/conversion/Protocol_Translator.json', "w") as f:
        json.dump(bidskit_config, f)

    ## Run bidskit 2nd pass
    bidskit(parent_folder+'/dicom', parent_folder+'/output', data)

    ## Add participants.json
    copyfile('participants.json',  parent_folder+'/output/participants.json')

    ## Store metadata for BIDS toolbox in hidden file
    with open(parent_folder+'/.dataset.toolbox', "w") as f:
        json.dump(data, f)

    ## Copy local BIDS folder to ZFS
    # To-Do, read destination folder from config JSON

    ## Call the processing pipeline
    # To-Do, connect with SlurmD/pySlurm

    print('createBIDS finished')

    return 'CreateBIDS finished'

@app.route('/updateBids', methods = ['POST'])
def updateBidsHandler():

    if request.is_json == False:
        raise RuntimeError("Incorrect body message -- not a JSON file")

    data = request.get_json()

    parent_folder = data['output']

    # To-Do, load from ZFS

    with open(parent_folder+'/.dataset.toolbox', 'r') as f:
        dataset_props = json.load(f)

    ## Add DICOM files for new subjects/scans to /dicom
    for sub in data['scans']:
        if sub in dataset_props['scans']:
            for scan in data['scans'][sub]:
                if scan not in dataset_props['scans'][sub]:
                    copytree(data['scans'][sub][scan], parent_folder+'/dicom/'+sub+'/'+scan)
        else:
            os.mkdir(parent_folder+'/dicom/'+sub)
            for scan in data['scans'][sub]:
                copytree(data['scans'][sub][scan], parent_folder+'/dicom/'+sub+'/'+scan)

    ## Run bidskit 2nd pass
    bidskit(parent_folder+'/dicom', parent_folder+'/output', data)

    # To-Do: check if dataset_description is updated, if not, update it here

    ## Store metadata for BIDS toolbox in hidden file
    with open(parent_folder+'/.dataset.toolbox', "w") as f:
        json.dump(data, f)

    ## Copy local BIDS folder to ZFS
    # To-Do, read destination folder from config JSON

    ## Call the processing pipeline
    # To-Do, connect with SlurmD/pySlurm

    print('updateBIDS finished')

    return 'UpdateBIDS finished'

if __name__ == '__main__':
    app.run(port=5000, host='0.0.0.0', debug=True)
