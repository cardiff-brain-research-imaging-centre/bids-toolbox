
import glob
import json

def inferScanModality(tag, parent_folder):

    scan = {}

    ## Check if working directory is empty
    if(len(glob.glob(parent_folder+'/work/conversion/sub*/ses*')) < 1):
        ## To-Do: Handle empty working directory error
        print('ERROR: Empty working directory')
        return scan 

    ## Take first session, first subject as reference
    nifti_dir = glob.glob(parent_folder+'/work/conversion/sub*/ses*')[0]    

    ## If bval and bvec files exist for a given tag, its a difussion scan
    if((len(glob.glob(nifti_dir+'/*'+tag+'*.bvec')) > 0) and (len(glob.glob(nifti_dir+'/*'+tag+'*.bval')) > 0)):
        scan['type'] = 'dwi'
        scan['modality'] = 'dwi'
    else:
        sidecar_files = glob.glob(nifti_dir+'/*'+tag+'*.json')
        if(len(sidecar_files) > 0):
            sidecar_file = sidecar_files[0]
            with open(sidecar_file, 'r') as f:
                sidecar_data = json.load(f)

            ## To-Do: Process sidecar data to detect anat or func
            scan['type'] = 'anat'
            scan['modality'] = 'T1w'
        
        else: # Branch to default
            scan['type'] = 'anat'
            scan['modality'] = 'T2w'

    return scan
