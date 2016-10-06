# -*- coding: utf-8 -*-
"""
Created on Thu Sep 29 12:40:21 2016
@author: chinmay

The script makes use of TauDEM functionality to extract stream netwrok using the DEM.
This script has been tested on the Ubuntu 15.10 system with TauDEM version 5.3.5. 
"""
"""Import all the modules required to run the script"""

import urllib
import os
import zipfile
from osgeo import osr, gdal

"""The function downloads the DEM from the given url (In this case National Elevation Dataset, USGS.) """

def downloadDEM(url):
    # Translate url into a filename
    filename = url.rsplit('/', 1)[-1]
    if not os.path.exists(filename):
        outfile = urllib.URLopener()
        print "..............downloading dem.............."
        dem = outfile.retrieve(url, filename)
        print "..............done downloading.............."
        return(dem)
        
"""Function extracts the downloaded zipped file to a folder named dem """        

def unzip(filepath, dest_path):
    if os.path.isdir(dest_path):
        print "..............data has been already extracted.............."
    else:
        print "..............extracting data.............."        
        with zipfile.ZipFile(filepath) as zf:
            extractedfiles= zf.extractall(dest_path)
            print "..............done extraction....."
            return(extractedfiles)
        
url = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/IMG/USGS_NED_13_n41w076_IMG.zip"
downloadDEM(url)

unzip("/home/chinmay/TNC_task/test/USGS_NED_13_n41w076_IMG.zip","/home/chinmay/TNC_task/test/dem/")

"""reproject the DEM and the basin boundary shapefile to the UTM projection system"""

print "...............projecting basin boundary and DEM to NAD 83 UTM 18..............."
os.system("ogr2ogr -t_srs EPSG:26918 /home/chinmay/TNC_task/test/Lopatcong_watershed/LopatcongCreek_projected.shp \
		/home/chinmay/TNC_task/test/Lopatcong_watershed/LopatcongCreek.shp")
print "...............Done projecting basin boundary..............."

os.system("gdalwarp -t_srs '+proj=utm +zone=18 +datum=NAD83' /home/chinmay/TNC_task/test/dem/USGS_NED_13_n41w076_IMG.img \
		/home/chinmay/TNC_task/test/dem/USGS_NED_13_n41w076_IMG_projected.img")
print "...............Done projecting DEM..............."

"""Clip the raster to the basin extent. 
This is assuming that the raster and the mask file have same projection (In this case, NAD83/UTM18.)"""

print "...............masking out dem for LopatcongCreek..............."
os.system("gdalwarp -dstnodata -9999 -cutline \
/home/chinmay/TNC_task/test/Lopatcong_watershed/LopatcongCreek_projected.shp \
/home/chinmay/TNC_task/test/dem/USGS_NED_13_n41w076_IMG_projected.img masked_dem.tif")
print "...............Done masking..............."

"""Prepare hydrologically correct DEM by eliminating depressions in the DEM. 
   This is done to allow the flow of water from each cell towards the outlet and maintain the hydaulic connectivity"""

print "...............Preparing hydrologically correct DEM by filling sinks..............."
os.system("mpiexec -n 8 pitremove -z masked_dem.tif -fel hydro_correct_dem.tif")
print "...............Done filling sinks..............."

"""The flow direction and flow accumulation are computed based on eight direction (D8) flow model. The flow computation 
   from each cell to one of its neighbouring 8 cells is based on the direction of the steepest descent i.e. (drop/distance) """

print "...............creating flow direction..............."
os.system("mpiexec -n 8 d8flowdir -fel hydro_correct_dem.tif -p flow_directions_d8.tif -sd8 slopes_d8.tif")
print "...............Done creating flow direction..............."

print "...............creating flow accumulation..............."
os.system("mpiexec -n 8 aread8 -p flow_directions_d8.tif -ad8 flow_accumulation_d8.tif")
print "...............Done creating flow accumulation..............."

"""The streams are defined deterministically based on the threshold value"""

print "...............Defining streams using given threshold value..............."
os.system("mpiexec -n 8 threshold -ssa flow_accumulation_d8.tif -src stream_raster_grid.tif -thresh 100.0")
print "...............Done defining streams using threshold value..............."

"""Using the stream raster grid defined by thresholding, this function computes the longest 
   path and stream order (using strahler method)"""

print "...............analyzing grid network..............."
os.system("mpiexec -n 8 gridnet -p flow_directions_d8.tif -gord grid_of_strahler_order.tif -plen grid_of_longest_flow_length.tif \
		   -tlen grid_of_total_path_length.tif")
print "...............Done analyzing grid network..............."

"""Writes the thresholded stream grid to the shapefile. Also computres the stream order for each stream segment 
   using strahler method. The network topological connectivity is stored in the Stream Network Tree file,
   and coordinates and attributes from each grid cell along the network are stored in the Network Coordinates file. """

print "...............extracting stream network to shp..............."
os.system("mpiexec -n 8 streamnet -fel hydro_correct_dem.tif -p flow_directions_d8.tif -ad8 flow_accumulation_d8.tif \
          -src stream_raster_grid.tif -ord grid_of_strahler_order.tif -tree treefile.txt -coord coordinates_and_attribute_list.txt \
          -net channel_network_thresh100.shp -w watershedgrid.tif -o lopatcongoutlet_projected.shp")
print "...............Done extracting stream network..............."
