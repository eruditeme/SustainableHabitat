import arcpy
from arcpy import env
from arcpy import *
from arcpy.sa import *

# Sets the output to the specified environment
env.workspace = "C:\\Users\\EvangelineLam\\Documents"
# Allow overwrite
env.overwriteOutput = True

arcpy.CheckOutExtension("Spatial")

land_cover = GetParameterAsText(0)
dem = GetParameterAsText(1)
stream = GetParameterAsText(2)
output = GetParameterAsText(3)

# Create a list to store all files created except for the final raster and the streams clip
layers = []

# Reclassifies all the valid places for a bobcat to live
reclassField = "VALUE"
remap = RemapValue([[7, 3], [6, 1], [8, 2],[5, 4], [9, 5], [10, 6]])
land_reclass = Reclassify(land_cover, reclassField, remap, "NODATA")
land_reclass.save("Script Output\\land_reclass")
arcpy.AddMessage("Reclassification of land class done")

# Converts the land cover to a polygon
land_poly = "Script Output\\land_poly.shp"
arcpy.AddMessage("Starting conversion of Land Cover raster into a polygon, this will take some time")
RasterToPolygon_conversion(land_reclass, land_poly, "SIMPLIFY", reclassField)
arcpy.AddMessage("Land Cover converted to polygon")

# Conditional on the land cover where 1 is equal to the urban areas
whereClause = "CLASS_NAMES = 'Developed, High Intensity' OR CLASS_NAMES = 'Developed, Low Intensity' OR CLASS_NAMES = 'Developed, Medium Intensity'"
urban = Con(land_cover, 1, "", whereClause)
layers.append(urban)
arcpy.AddMessage("Urban area created from land cover")

# Converts the urban raster to a polygon
urban_poly = "Script Output\\urban_poly.shp"
RasterToPolygon_conversion(urban, urban_poly, "SIMPLIFY", reclassField)
arcpy.AddMessage("Urban area converted to polygon")

# Dissolve the urban poly
urban_diss = "Script Output\\urban_diss.shp"
Dissolve_management(urban_poly, urban_diss)
layers.append(urban_diss)
arcpy.AddMessage("Urban polygon dissolved")

# Buffer urban areas by 1km
urban_buf = "Script Output\\urban_buf.shp"
Buffer_analysis(urban_diss, urban_buf, "1 Kilometers")
layers.append(urban_buf)
arcpy.AddMessage("Urban buffer completed")

# Erases the urban buffer from the land class
land_noUrban = "Script Output\\land_noUrban.shp"
Erase_analysis(land_poly, urban_buf, land_noUrban)
layers.append(land_noUrban)
arcpy.AddMessage("Urban erased from the land cover class")

# Dissolve the newly created land cover polygon
land_dissolve = "Script Output\\land_dissolve.shp"
Dissolve_management(land_noUrban, land_dissolve, "", "", "SINGLE_PART", "UNSPLIT_LINES")
layers.append(land_dissolve)
arcpy.AddMessage("Land class polygon dissolved")

# Add area to land and make it a feature class
land_dissolve_layer = "Script Output\\land_dissolve_layer.shp"
temp = "Script Output\\temp"
AddGeometryAttributes_management(land_dissolve, "AREA")
whereClause = """ "POLY_AREA" >= 10000000 """
MakeFeatureLayer_management(land_dissolve, temp)
SelectLayerByAttribute_management(temp, "NEW_SELECTION", whereClause)
CopyFeatures_management(temp, land_dissolve_layer)
layers.append(land_dissolve_layer)
arcpy.AddMessage("Land class area has been added")

# Convert the polgon into a raster
noUrban_ras = "Script Output\\noUrban_ras"
PolygonToRaster_conversion(land_dissolve_layer, "FID", noUrban_ras, "CELL_CENTER", "NONE", 30)
layers.append(noUrban_ras)
arcpy.AddMessage("Land class no urban converted into raster")

# noUrban_ras con on "VALUE"<=30027
whereClause = """" VALUE" <= 30027 """
noUrban_con = Con(noUrban_ras, 0, "", whereClause)
noUrban_con.save("Script Output\\noUrban_con")
layers.append(noUrban_con)
arcpy.AddMessage("noUrban con completed")

# Clip streams to land_disolve_layer
streams_clip = "Script Output\\streams_clip"
Clip_analysis(stream, land_dissolve_layer, streams_clip)
arcpy.AddMessage("Stream clip completed")

# Create a slope file from the land class
slope = Slope(dem, "DEGREE")
slope.save("Script Output\\slope")
arcpy.AddMessage("Converting DEM into slope done")

# Reclassify the slope by ranking to the preferred slope of the bobcat, where 1 represents the best and 6 the worst
remap = RemapRange([[0, 9.548949, 6], [9.548949, 19.097898, 5], [19.097898, 28.646847, 4],
                    [28.646847, 38.195796, 3], [38.195796, 47.744745, 2], [47.744745, 57.293694, 1]])
slope_reclass = Reclassify(slope, reclassField, remap, "NODATA")
slope_reclass.save("Script Output\\slope_reclass")
layers.append(slope_reclass)
arcpy.AddMessage("Reclassification of slope done")

# Create a aspect file from the land class
aspect = Aspect(dem)
aspect.save("Script Output\\aspect")
arcpy.AddMessage("Converting DEM into aspect done")

# Reclassify the aspect by ranking to the preferred direct of the bobcat, where 1 represents the best and 6 the worst
remap = RemapRange([[-1, 0, 6], [0, 22.5, 5], [22.5, 67.5, 4], [67.5, 112.5, 3], [112.5, 157.5, 2],
                    [157.5, 202.5, 1], [202.5, 247.5, 2], [247.5, 292.5, 3],[292.5, 337.5, 4], [337.5, 360, 5]])
aspect_reclass = Reclassify(aspect, reclassField, remap, "NODATA")
aspect_reclass.save("Script Output\\asp_reclass")
layers.append(aspect_reclass)
arcpy.AddMessage("Reclassification of aspect done")

# Apply a weighted sum on the slope, aspect and land reclass
outWeightedSum = WeightedSum(WSTable([[land_reclass, "VALUE", 0.6], [slope_reclass, "VALUE", 0.3], [aspect_reclass, "VALUE", 0.1]]))
outWeightedSum.save("Script Output\\weight_land")
arcpy.AddMessage("Weighted sum complete")

# Get the suitability model by using the raster calculator to remove all urban areas
outRaster = outWeightedSum + noUrban_con
outRaster.save(output)

# Permanently deletes unrequired layers from disk 
for layer in layers:
    if arcpy.Exists(layer):
        arcpy.management.Delete(layer)
arcpy.AddMessage("Suitability Model Completed!")
