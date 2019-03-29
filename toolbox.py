import os
import json
from shutil import copyfile

from dcm2bids import bidskit
from scanModality import inferScanModality

def createDataset(parent_folder, data, config, resp_data):

    ## Run bidskit 1st pass 
    dcm2niix_time = bidskit(parent_folder+'/dicom', parent_folder+'/output', data, config)

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

    # This 'if' is triggered if the Toolbox heuristic has not been to infer the modality/type of scan
    # for any of the series. This stops the conversion.
    if any_unclassified:
        resp_data['status'] = 'error'
        resp_data['errorMessage'] = 'Scan modality not provided and not detected for the following tags: '
        resp_data['errorMessage'] += str(unclassified_list)
        return True, dcm2niix_time #Return True for error

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

    return False, dcm2niix_time #Return False for no error

def updateDataset(parent_folder, data, config):
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

    return dcm2niix_time
