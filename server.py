from flask import Flask
from flask import request

app = Flask(__name__)

@app.route('/createBids', methods = ['POST'])
def postJsonHandler():

    if request.is_json == False:
        raise RuntimeError("Incorrect body message -- not a JSON file")

    content = request.get_json()
    
    ### Create DICOM folder structure

    # Create temporary folder to arrange DICOM files
    folder_name = 'bids_temp_'+str(time.time())
    try:
        os.mkdir('/tmp/'+folder_name)
    except FileExistsError:
        print("Directory ",folder_name, " already exists")



    ### Run bidskit 


    return 'Create BIDS finished'

if __name__ == '__main__':
    app.run(port=5000, host='0.0.0.0', debug=True)
