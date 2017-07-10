# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Cloud Filters
                                 A QGIS plugin
 Cloud masking for landsat products using different process suck as fmask
                             -------------------
        copyright            : (C) 2016-2017 by Xavier Corredor Llano, SMBYC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 3 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
import qgis.core
from osgeo import gdal
from PyQt4 import QtGui
from PyQt4.QtCore import Qt
from numpy import intersect1d


def get_prefer_name(file_path):
    """Search the prefer name for band: band1 > B1"""
    path_dir, band_file = os.path.split(file_path)
    # prefer thermal b61/2 over band61/2 over B6_VCID_1/2 in Landsat 7
    if band_file.startswith("LE7") or band_file.startswith("LE07"):
        file_bandN = band_file.replace("_B6_VCID_", "_b6").replace(".TIF", ".tif")
        if os.path.isfile(os.path.join(path_dir, file_bandN)):
            return os.path.join(path_dir, file_bandN)
        file_bandN = band_file.replace("_B6_VCID_", "_band6").replace(".TIF", ".tif")
        if os.path.isfile(os.path.join(path_dir, file_bandN)):
            return os.path.join(path_dir, file_bandN)
    # prefer bN over bandN over BN (i.e. band1.tif over B1.TIF)
    file_bandN = band_file.replace("_B", "_b").replace(".TIF", ".tif")
    if os.path.isfile(os.path.join(path_dir, file_bandN)):
        return os.path.join(path_dir, file_bandN)
    file_bandN = band_file.replace("_B", "_band").replace(".TIF", ".tif")
    if os.path.isfile(os.path.join(path_dir, file_bandN)):
        return os.path.join(path_dir, file_bandN)
    # return original
    return file_path


def apply_symbology(rlayer, symbology, symbology_enabled, transparent=255):
    """ Apply classification symbology to raster layer """
    # See: QgsRasterRenderer* QgsSingleBandPseudoColorRendererWidget::renderer()
    # https://github.com/qgis/QGIS/blob/master/src/gui/raster/qgssinglebandpseudocolorrendererwidget.cpp
    # Get raster shader
    raster_shader = qgis.core.QgsRasterShader()
    # Color ramp shader
    color_ramp_shader = qgis.core.QgsColorRampShader()
    # Loop over Fmask values and add to color item list
    color_ramp_item_list = []
    for name, value, enable in zip(['Fmask Cloud', 'Fmask Shadow', 'Fmask Snow', 'Fmask Water',
                                    'Blue Band', 'Cloud QA', 'Aerosol', 'Pixel QA'],
                                   [2, 3, 4, 5, 6, 7, 8, 9], symbology_enabled):
        if enable is False:
            continue
        color = symbology[name]
        # Color ramp item - color, label, value
        color_ramp_item = qgis.core.QgsColorRampShader.ColorRampItem(
            value,
            QtGui.QColor(color[0], color[1], color[2], color[3]),
            name
        )
        color_ramp_item_list.append(color_ramp_item)

    # Add the NoData symbology
    color_ramp_item_list.append(qgis.core.QgsColorRampShader.ColorRampItem(255, QtGui.QColor(70, 70, 70, 255), "No Data"))
    # Add the valid data, no masked
    color_ramp_item_list.append(qgis.core.QgsColorRampShader.ColorRampItem(1, QtGui.QColor(0, 0, 0, 0), "No Masked"))
    # After getting list of color ramp items
    color_ramp_shader.setColorRampItemList(color_ramp_item_list)
    # Exact color ramp
    color_ramp_shader.setColorRampType('EXACT')
    # Add color ramp shader to raster shader
    raster_shader.setRasterShaderFunction(color_ramp_shader)
    # Create color renderer for raster layer
    renderer = qgis.core.QgsSingleBandPseudoColorRenderer(
        rlayer.dataProvider(),
        1,
        raster_shader)
    # Set renderer for raster layer
    rlayer.setRenderer(renderer)

    # Set NoData transparency to layer qgis (temporal)
    if not isinstance(transparent, list):
        transparent = [transparent]
    nodata = [qgis.core.QgsRasterRange(t, t) for t in transparent]
    if nodata:
        rlayer.dataProvider().setUserNoDataValue(1, nodata)
    # Set NoData transparency to file
    #for t in transparent:
    #    rlayer.dataProvider().setNoDataValue(1, t)

    # Repaint
    if hasattr(rlayer, 'setCacheImage'):
        rlayer.setCacheImage(None)
    rlayer.triggerRepaint()


def update_process_bar(bar_inst=None, bar=None, status_inst=None, status=None):

    if bar_inst is not None and bar is not None:
        # set bar value
        bar = int(bar)
        bar_inst.setValue(bar)
        QtGui.QApplication.processEvents()

    if status_inst is not None and status is not None:
        # set status
        status_inst.setText(str(status))
        QtGui.QApplication.processEvents()

    if bar is not None and 0 < bar < 100:
        # set mouse wait
        cursor = QtGui.QApplication.overrideCursor()
        if cursor is None or cursor == 0:
            QtGui.QApplication.setOverrideCursor(QtGui.QCursor(Qt.WaitCursor))
        QtGui.QApplication.processEvents()

    if bar is not None and (bar == 100 or bar == 0):
        # restore mouse
        QtGui.QApplication.restoreOverrideCursor()
        QtGui.QApplication.processEvents()


def binary_combination(binary, fix_bits=None):
    """
    Binary combination with fixed bit. For complete combination let
    fix_bits as []

    Example:
        input: binary=[0,1,1,0], fix_bits=[0,1]
        output: [0,0,1,0], [0,1,1,0], [1,0,1,0], [1,1,1,0] -> [2,6,10,14]
    """
    if fix_bits is None:
        fix_bits = []

    n = len(binary)
    fix_bits = [n-x-1 for x in fix_bits]
    for i in range(1 << n):
        s = bin(i)[2:]
        s = '0'*(n-len(s))+s
        bit_string = map(int, list(s))
        if all([bit_string[fb] == int(binary[fb]) for fb in fix_bits]):
            bit_string = [str(x) for x in bit_string]
            yield int("".join(bit_string), 2)


def check_values_in_image(img, values, band=1):
    """
    Return only the list values that is in the image
    """
    ds = gdal.Open(img)
    raster_array = ds.GetRasterBand(band).ReadAsArray().ravel()
    del ds
    return intersect1d(raster_array, values)


def get_extent(img_path):
    data = gdal.Open(img_path, gdal.GA_ReadOnly)
    geoTransform = data.GetGeoTransform()
    minx = geoTransform[0]
    maxy = geoTransform[3]
    maxx = minx + geoTransform[1] * data.RasterXSize
    miny = maxy + geoTransform[5] * data.RasterYSize
    del data

    return [round(minx), round(maxy), round(maxx), round(miny)]

