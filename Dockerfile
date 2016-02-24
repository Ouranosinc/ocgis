FROM continuumio/miniconda

MAINTAINER ben.koziol@gmail.com

RUN apt-get -y update
RUN apt-get -y upgrade
RUN apt-get -y install build-essential \
                       gfortran
RUN apt-get clean

RUN conda install -y -c nesii/channel/ocgis -c nesii ocgis esmpy nose

RUN conda remove -y ocgis
RUN git clone -b master --depth=10 https://github.com/NCPP/ocgis.git
RUN cd ocgis && python setup.py install
RUN rm -r /ocgis

ENV GDAL_DATA /opt/conda/share/gdal

RUN cd && nosetests -a '!slow,!remote,!data' /ocgis/src/ocgis/test

RUN rm -r /opt/conda/pkgs/*
