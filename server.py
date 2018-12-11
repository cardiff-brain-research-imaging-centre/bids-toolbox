from flask import Flask
from flask import request

from shutil import copytree
import os
import time

from dcm2bids import bidskit

app = Flask(__name__)

@app.route('/createBids', methods = ['POST'])
def postJsonHandler():

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
        os.mkdir(parent_folder+'/dicom/sub-'+sub)
        for ses in data['scans'][sub]:
            copytree(data['scans'][sub][ses], parent_folder+'/dicom/sub-'+sub+'/ses-'+ses)

    ### Run bidskit 1st pass 
    bidskit(parent_folder+'/dicom', parent_folder+'/output')

    ##FIX THE CONFIG YAML


    return 'CreateBIDS finished'

if __name__ == '__main__':
    app.run(port=5000, host='0.0.0.0', debug=True)
