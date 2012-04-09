from PySide import QtGui


class MBWindow(QtGui.QMainWindow):
    def __init__(self, colours=None, biomes=None):
        QtGui.QMainWindow.__init__(self)
        
        self.colours = colours
        self.biomes = biomes
        
        self.init_ui()
        
        # init tools
        
        self.copybtn.triggered.connect(lambda: self.tabs.currentWidget().copy_chunks())
        self.mergebtn.triggered.connect(lambda: self.tabs.currentWidget().merge_chunks())
        self.cancelbtn.triggered.connect(lambda: self.tabs.currentWidget().cancel_merge())
        self.update_toolbar()

        # init tabs

        self.cliptab = None # the tab chunks have been copied from
        self.tabs.currentChanged.connect(self.update_toolbar)

        self.show()
        
        
    def init_ui(self):
        self.resize(800, 700)
        self.setContentsMargins(10, 10, 10, 10)
        self.setWindowTitle('Mine Bash')

        filemenu = self.menuBar().addMenu('File')
        self.open = filemenu.addAction('Open')
        self.save = filemenu.addAction('Save')
        
        self.tabs = QtGui.QTabWidget(self)
        self.setCentralWidget(self.tabs)
        
        self.tools = QtGui.QToolBar(self)
        self.addToolBar(self.tools)
        
        # selection tools
        
        self.seltools = QtGui.QActionGroup(self.tools)

        self.brush = self.tools.addAction('Brush')
        self.brush.setCheckable(1)
        self.seltools.addAction(self.brush)
        
        self.box = self.tools.addAction('Box')
        self.box.setCheckable(1)
        self.seltools.addAction(self.box)
        
        # clipboard tools
        
        self.tools.addSeparator()
        
        self.copybtn = self.tools.addAction('Copy')
        self.pastebtn = self.tools.addAction('Paste')
        self.mergebtn = self.tools.addAction('Merge')
        self.cancelbtn = self.tools.addAction('Cancel Merge')
        
        # status bar
        
        self.status = self.statusBar()
        self.status.setSizeGripEnabled(0)
        self.status.setContentsMargins(10, 0, 10, 0)
        
        self.copylabel = QtGui.QLabel('')
        self.status.addWidget(self.copylabel)
    

    def update_toolbar(self):
        """On switching to a new tab, enables and disables tools in the toolbar."""
        tab = self.tabs.currentWidget()
        if not tab:
            self.tools.setDisabled(1)
        else:
            self.tools.setEnabled(1)
            self.seltools.setEnabled(1 if not tab.paste else 0)
            self.copybtn.setEnabled(1 if tab.selected else 0)
            self.pastebtn.setEnabled(1 if self.cliptab and not tab.paste else 0)
            self.mergebtn.setEnabled(1 if tab.paste else 0)
            self.cancelbtn.setEnabled(1 if tab.paste else 0)
            
            

