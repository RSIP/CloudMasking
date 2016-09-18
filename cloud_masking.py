# -*- coding: utf-8 -*-
"""
/***************************************************************************
 CloudMasking
                                 A QGIS plugin
 Cloud masking using different process suck as fmask
                              -------------------
        copyright            : (C) 2016 by Xavier Corredor Llano, SMBYC
        email                : xcorredorl@ideam.gov.co
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from PyQt4.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QObject, SIGNAL
from PyQt4.QtGui import QAction, QIcon, QMenu
# Initialize Qt resources from file resources.py
import resources

# Import the code for the DockWidget
from cloud_masking_dockwidget import CloudMaskingDockWidget
import os.path


class CloudMasking:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        self.canvas = self.iface.mapCanvas()

        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'CloudMasking_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Cloud Masking')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'CloudMasking')
        self.toolbar.setObjectName(u'CloudMasking')

        #print "** INITIALIZING CloudMasking"

        self.pluginIsActive = False
        self.dockwidget = None


    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('CloudMasking', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            ## set the smbyc menu
            self.smbyc_menu = None
            # Check if the menu exists and get it
            for menu_item in self.iface.mainWindow().menuBar().children():
                if isinstance(menu_item, QMenu) and menu_item.title() == u"SMBYC":
                    self.smbyc_menu = menu_item
            # If the menu does not exist, create it!
            if not self.smbyc_menu:
                self.smbyc_menu = QMenu(self.iface.mainWindow().menuBar())
                self.smbyc_menu.setObjectName(u'Plugins for the project SMBYC')
                self.smbyc_menu.setTitle(u"SMBYC")

            ## set the item plugin in smbyc menu
            self.action = QAction(QIcon(icon_path), self.menu, self.iface.mainWindow())
            self.action.setObjectName(u'CloudMasking')
            self.action.setWhatsThis(self.tr(u'Cloud masking ...'))
            self.action.setStatusTip(self.tr(u'This is status tip'))
            QObject.connect(self.action, SIGNAL("triggered()"), self.run)
            self.smbyc_menu.addAction(self.action)

            self.menuBar = self.iface.mainWindow().menuBar()
            self.menuBar.insertMenu(self.iface.firstRightStandardMenu().menuAction(), self.smbyc_menu)

        self.actions.append(action)

        return action


    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/CloudMasking/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Cloud Masking'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # handle connect when the layers changed
        QObject.connect(self.canvas, SIGNAL("layersChanged ()"), self.updateLayersList)

    #--------------------------------------------------------------------------

    def onClosePlugin(self):
        """Cleanup necessary items here when plugin dockwidget is closed"""

        #print "** CLOSING CloudMasking"

        # disconnects
        self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)

        # remove this statement if dockwidget is to remain
        # for reuse if plugin is reopened
        # Commented next statement since it causes QGIS crashe
        # when closing the docked window:
        # self.dockwidget = None

        self.pluginIsActive = False


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""

        #print "** UNLOAD CloudMasking"

        for action in self.actions:
            for menu_item in self.iface.mainWindow().menuBar().children():
                if isinstance(menu_item, QMenu) and menu_item.title() == u"SMBYC":
                    menu_item.removeAction(self.action)
                    # TODO: remove menu_item "SMBYC" if this is empty (actions)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    #--------------------------------------------------------------------------

    def run(self):
        """Run method that loads and starts the plugin"""

        if not self.pluginIsActive:
            self.pluginIsActive = True

            #print "** STARTING CloudMasking"

            # dockwidget may not exist if:
            #    first run of plugin
            #    removed on close (see self.onClosePlugin method)
            if self.dockwidget == None:
                # Create the dockwidget (after translation) and keep reference
                self.dockwidget = CloudMaskingDockWidget()

            # connect to provide cleanup on closing of dockwidget
            self.dockwidget.closingPlugin.connect(self.onClosePlugin)

            # show the dockwidget
            # TODO: fix to allow choice of dock location
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

        # set initial input layers list
        self.updateLayersList()

    def updateLayersList(self):
        self.dockwidget.selectList_InputImage.clear()
        for layer in self.canvas.layers():
            self.dockwidget.selectList_InputImage.addItem(layer.name())


