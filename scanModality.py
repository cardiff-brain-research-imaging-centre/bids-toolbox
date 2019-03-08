
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

    ## If bval and bvec files exist for a given tag, its a diffusion scan
    if((len(glob.glob(nifti_dir+'/*'+tag+'*.bvec')) > 0) and (len(glob.glob(nifti_dir+'/*'+tag+'*.bval')) > 0)):
        scan['type'] = 'dwi'
        scan['modality'] = 'dwi'
    else:
        sidecar_files = glob.glob(nifti_dir+'/*'+tag+'*.json')
        if(len(sidecar_files) > 0):
            sidecar_file = sidecar_files[0]
            with open(sidecar_file, 'r') as f:
                sidecar_data = json.load(f)

            SS = sidecar_data['ScanningSequence']
            FA = sidecar_data['FlipAngle']
            TE = sidecar_data['EchoTime']
            TR = sidecar_data['RepetitionTime']
					
            if 'GR' in SS:
                if TE < 30:
                    if FA == 90:
                        if TR < 800:
                            scan['type'] = 'anat'
                            scan['modality'] = 'T1w'                       
                        else:
                            scan['type'] = 'anat'
                            scan['modality'] = 'PD'
                    elif FA >= 5 and FA <= 20:
                        scan['type'] = 'anat'
                        scan['modality'] = 'T1w'   
                    else:
                        scan['type'] = 'anat'
                        scan['modality'] = 'T2star'     
                else:
                    scan['modality'] = 'unclassified'     

            elif 'EP' in SS:
                if TE >= 30 and TE <= 60:
                    scan['type'] = 'func'
                    scan['modality'] = 'BOLD'
                else:
                    scan['modality'] = 'unclassified'     

            elif 'SE' in SS:
                if 'IR' in SS:
                    if 'InversionTime' in sidecar_data:
                        TI = sidecar_data['InversionTime']				
                        if TI < 1:
                            scan['type'] = 'IR'
                            scan['modality'] = 'STIR'   
                        else:
                            scan['type'] = 'anat'
                            scan['modality'] = 'FLAIR'   		
                    else: 
                        scan['modality'] = 'unclassified'     
                else:
                    if TE >= 60:
                        scan['type'] = 'anat'
                        scan['modality'] = 'T2w'   
                    else:
                        scan['modality'] = 'unclassified'             
            else: # If not GR, EP or SE: unclassified
                scan['modality'] = 'unclassified' 

    return scan
