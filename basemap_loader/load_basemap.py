import os
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsRasterLayer, QgsProject

plugin_dir = os.path.dirname(__file__)


def make_xyz_layer(url, name, zmin=0, zmax=19, crs='EPSG:3857'):
    """XYZ tile raster layer (the URL may already contain %26-escaped ampersands)."""
    uri = f'type=xyz&url={url}&zmax={zmax}&zmin={zmin}&crs={crs}'
    return QgsRasterLayer(uri, name, 'wms')


def insert_at_bottom(layer, project=None):
    """Add the layer to the project and put it at the bottom of the layer tree."""
    project = project or QgsProject.instance()
    project.addMapLayer(layer, False)
    root = project.layerTreeRoot()
    root.insertLayer(len(root.children()), layer)


class BasemapLoaderPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None

    def initProcessing(self):
        # also called headless by qgis_process (hasProcessingProvider=yes)
        if self.provider is not None:
            return
        from qgis.core import QgsApplication
        from .processing_provider import BasemapLoaderProvider
        self.provider = BasemapLoaderProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        icon = os.path.join(os.path.join(plugin_dir, 'logo.png'))
        self.action = QAction(QIcon(icon), 'Load Basemap', self.iface.mainWindow())
        self.iface.addToolBarIcon(self.action)
        self.action.triggered.connect(self.run)

    def unload(self):
        if self.provider is not None:
            from qgis.core import QgsApplication
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
        self.iface.removeToolBarIcon(self.action)
        del self.action

    def run(self):
        rlayer = make_xyz_layer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                                'OpenStreetMap')
        if rlayer.isValid():
            # Set project CRS to the layer's CRS
            QgsProject.instance().setCrs(rlayer.crs())

            # Add the layer to the project but not to the legend directly,
            # then insert it at the bottom of the layer tree
            insert_at_bottom(rlayer)

            self.iface.messageBar().pushSuccess('Success', 'Basemap Layer Loaded and CRS Set')
        else:
            self.iface.messageBar().pushCritical('Error', 'Invalid Basemap Layer')
