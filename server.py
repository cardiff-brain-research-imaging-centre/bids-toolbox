from flask import Flask
from flask import request

app = Flask(__name__)

@app.route('/createBids', methods = ['POST'])
def postJsonHandler():
 
    print (request.is_json)
    content = request.get_json()
    print (content['message'])   

    # Create DICOM folder structure

    # Run bidskit 


    return 'JSON posted'

if __name__ == '__main__':
    app.run(port=5000, host='0.0.0.0', debug=True)
