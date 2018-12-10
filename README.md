# CUBRIC BIDS Toolbox

This repository hold the code for The BIDS Toolbox, a web service for the creation and manipulation of BIDS datasets. This development is part of MiDac, a STFC-funded project.

### Software pre-requisites

Flask: can be installed using pip as: `pip install flask flask-restful`

Dcm2Niix: install latest version from official repository https://github.com/rordenlab/dcm2niix

This software uses parts of [bidskit](https://github.com/jmtyszka/bidskit), but it doesn't need to be installed.

### Running the service

Clone repository and run from parent directory: `python server.py`

### API

The following methods are provided:

createBids(): create a BIDS dataset from  a set of DICOM images.
