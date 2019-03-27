# Use an official Python runtime as a parent image
FROM python:3.6-slim

# Set the working directory to /app
WORKDIR /app

# Install needed packages 
RUN apt-get update && apt-get install -y wget unzip gcc cmake build-essential git
RUN pip install flask flask-restful pydicom numpy

# Install dcm2niix with Cloudflare zlib
RUN git clone https://github.com/rordenlab/dcm2niix.git
WORKDIR /app/dcm2niix
RUN mkdir build
WORKDIR /app/dcm2niix/build
RUN cmake -DZLIB_IMPLEMENTATION=Cloudflare -DUSE_JPEGLS=ON -DUSE_OPENJPEG=ON /app/dcm2niix
RUN make
RUN ln -s /app/dcm2niix/build/bin/dcm2niix /usr/local/bin/dcm2niix 

# Get BIDS Toolbox
WORKDIR /app
RUN git clone https://github.com/ulopeznovoa/bids-toolbox.git

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Run server.py when the container launches
WORKDIR /app/bids-toolbox
CMD ["python", "server.py"]
