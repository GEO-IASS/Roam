import os
import shutil
import random
import traceback

from datetime import datetime

from PyQt4.QtGui import QDialog, QFont, QColor, QIcon, QMessageBox, QStandardItem, QStandardItemModel, QInputDialog
from PyQt4.QtCore import QAbstractItemModel, QModelIndex, Qt


from configmanager.ui import ui_configmanager
from roam import resources_rc

import shutil
import roam.project
import roam.messagebaritems


templatefolder = os.path.join(os.path.dirname(__file__), "..", "templates")

def newfoldername(basetext, basefolder, formtype, alreadyexists=False):
    message = "Please enter a new folder name for the {}".format(formtype)
    if alreadyexists:
        message += "<br> {} folder already exists please select a new one.".format(formtype)

    name, ok = QInputDialog.getText(None, "New {} folder name".format(formtype), message)
    if not ok:
        raise ValueError

    if not name:
        return "{}_{}".format(basetext, datetime.today().strftime('%d%m%y%f'))
    else:
        name = name.replace(" ", "_")

    if os.path.exists(os.path.join(basefolder, name)):
        return newfoldername(basetext, basefolder, formtype, alreadyexists=True)

    return name

def newproject(projectfolder):
    """
    Create a new folder in the projects folder.
    :param projectfolder: The root project folder
    :return: The new project that was created
    """
    foldername = newfoldername("project", projectfolder, "Project")
    templateproject = os.path.join(templatefolder, "templateProject")
    newfolder = os.path.join(projectfolder, foldername)
    shutil.copytree(templateproject, newfolder)
    project = roam.project.Project.from_folder(newfolder)
    project.settings['title'] = foldername
    project.settings['forms'] = {}
    return project

def newform(project):

    folder = project.folder
    foldername = newfoldername("form", folder, "Form")

    formfolder = os.path.join(folder, foldername)
    templateform = os.path.join(templatefolder, "templateform")
    shutil.copytree(templateform, formfolder)

    config = dict(label=foldername, type='auto', widgets=[])
    form = project.addformconfig(foldername, config)
    return form


ProjectRole = Qt.UserRole + 20

class Treenode(QStandardItem):
    ProjectNode = QStandardItem.UserType + 0
    FormNode = QStandardItem.UserType + 1
    MapNode = QStandardItem.UserType + 2
    TreeNode = QStandardItem.UserType + 3
    RoamNode = QStandardItem.UserType + 4
    FormsNode = QStandardItem.UserType + 5
    ProjectsNode = QStandardItem.UserType + 6

    nodetype = TreeNode
    def __init__(self, text, icon, project=None):
        super(Treenode, self).__init__(QIcon(icon), text)
        self.project = project
        self.canadd = False
        self.canremove = False
        self.addtext = ''
        self.removetext = ''

    def data(self, role=None):
        if role == Qt.UserRole:
            return self
        if role == ProjectRole:
            return self.project

        return super(Treenode, self).data(role)

    def type(self):
        return self.nodetype

    @property
    def page(self):
        return self.type() - QStandardItem.UserType

    def additem(self):
        pass


class RoamNode(Treenode):
    nodetype = Treenode.RoamNode

    def __init__(self, text="Roam", project=None):
        super(RoamNode, self).__init__(text ,QIcon(":/icons/open"))


class MapNode(Treenode):
    nodetype = Treenode.MapNode

    def __init__(self, text, project):
        super(MapNode, self).__init__(text,QIcon(":/icons/map"), project=project)


class FormNode(Treenode):
    nodetype = Treenode.FormNode

    def __init__(self, form, project):
        super(FormNode, self).__init__(form.label, QIcon(form.icon), project=project)
        self.form = form
        self.canremove = True
        self.canadd = True
        self.addtext = 'Add new form'
        self.removetext = 'Remove selected form'

        configname = "{}.config".format(form.name)
        self.removemessage = ("Remove form?", ("<b>Do you want to delete this form from the project?</b> <br><br> "
                                               "Deleted forms will be moved to the _archive folder in {}<br><br>"
                                               "<i>Forms can be restored by moving the folder back to the project folder"
                                               " and restoring the content in {} to the settings.config</i>".format(self.project.folder, configname)))

    def data(self, role):
        if role == Qt.DisplayRole:
            return self.form.label

        return super(FormNode, self).data(role)

    def additem(self):
        return self.parent().additem()

class FormsNode(Treenode):
    nodetype = Treenode.FormsNode

    def __init__(self, text, project):
        super(FormsNode, self).__init__(text, QIcon(":/icons/dataentry"), project)
        self.forms = []
        self.canadd = True
        self._text = text
        self.addtext = 'Add new form'
        self.loadforms()

    def loadforms(self):
        forms = self.project.forms
        for form in forms:
            item = FormNode(form, self.project)
            self.appendRow(item)

    def data(self, role):
        if role == Qt.DisplayRole:
            return "{} ({})".format(self._text, self.rowCount())

        return super(FormsNode, self).data(role)

    def removeRow(self, index):
        """
        Removes the given form at the index from the project.
        """
        formnode = self.takeRow(index)[0]
        form = formnode.form

        archivefolder = os.path.join(self.project.folder, "_archive")
        formachivefolder = os.path.join(archivefolder, form.name)
        configname = "{}.config".format(form.name)
        config = {form.name : form.settings}
        try:
            shutil.move(form.folder, formachivefolder)
            configlocation = os.path.join(archivefolder, configname)

            with open(configlocation, 'w') as f:
                roam.yaml.dump(data=config, stream=f, default_flow_style=False)
            del self.project.settings['forms'][form.name]
            self.project.save()
        except Exception as ex:
            print ex
            return False

        return True

    def additem(self):
        form = newform(self.project)
        self.project.save()
        item = FormNode(form, self.project)
        self.appendRow(item)
        return item


class ProjectNode(Treenode):
    nodetype = Treenode.ProjectNode

    def __init__(self, project):
        super(ProjectNode, self).__init__(project.name,QIcon(":/icons/folder"))
        self.project = project
        self.formsnode = FormsNode("Forms", project=project)
        self.mapnode = MapNode("Map", project=project)
        self.appendRows([self.mapnode, self.formsnode])
        self.removemessage = ("Delete Project?", ("Do you want to delete this project? <br><br> "
                               "Deleted projects will be moved to the _archive folder in projects folder<br><br>"
                               "<i>Projects can be recovered by moving the folder back to the projects folder</i>"))
        self.canremove = True
        self.canadd = True
        self.removetext = 'Remove selected project'
        self.addtext = 'Add new project'

    def additem(self):
        return self.parent().additem()

    def data(self, role=None):
        if role == Qt.DisplayRole:
            return self.project.name
        return super(ProjectNode, self).data(role)


class ProjectsNode(Treenode):
    nodetype = Treenode.ProjectsNode

    def __init__(self, text="Projects", folder=None):
        super(ProjectsNode, self).__init__(text, None)
        self.projectfolder = folder
        self.canadd = True
        self.addtext = 'Add new project'
        self._text = text

    def removeRow(self, index):
        nodes = self.takeRow(index)
        if not nodes:
            return
        projectnode = nodes[0]
        project = projectnode.project
        try:
            archivefolder = os.path.join(project.basepath, "_archive")
            shutil.move(project.folder, archivefolder)
        except Exception as ex:
            print ex.message
            return False

        return True

    def additem(self):
        project = newproject(self.projectfolder)
        item = ProjectNode(project)
        self.appendRow(item)
        return item

    def data(self, role):
        if role == Qt.DisplayRole:
            return "{} ({})".format(self._text, self.rowCount())
        return super(ProjectsNode, self).data(role)


class ConfigManagerDialog(ui_configmanager.Ui_ProjectInstallerDialog, QDialog):
    def __init__(self, projectfolder, parent=None):
        super(ConfigManagerDialog, self).__init__(parent)
        self.setupUi(self)
        self.bar = roam.messagebaritems.MessageBar(self)

        self.treemodel = QStandardItemModel()
        self.projectList.setModel(self.treemodel)
        self.projectList.setHeaderHidden(True)

        self.projectList.selectionModel().currentChanged.connect(self.nodeselected)

        self.projectwidget.adjustSize()
        self.setWindowFlags(Qt.Window)
        self.projectfolder = projectfolder

        self.newProjectButton.pressed.connect(self.addbuttonpressed)
        self.removeProjectButton.pressed.connect(self.deletebuttonpressed)
        self.projectwidget.projectupdated.connect(self.projectupdated)
        self.projectwidget.projectsaved.connect(self.projectupdated)
        self.projectwidget.projectloaded.connect(self.updateformsnode)
        self.projectwidget.selectlayersupdated.connect(self.updateformsnode)

        self.projectwidget.setaboutinfo()

        self.setuprootitems()

    def updateformsnode(self, *args):
        haslayers = self.projectwidget.checkcapturelayers()
        index = self.projectList.currentIndex()
        node = index.data(Qt.UserRole)
        if node.nodetype == Treenode.FormsNode:
            self.newProjectButton.setEnabled(haslayers)

    def raiseerror(self, *exinfo):
        info = traceback.format_exception(*exinfo)
        self.bar.pushError('Seems something has gone wrong. Press for more details',
                                  info)

    def setuprootitems(self):
        self.roamnode = RoamNode()
        self.treemodel.invisibleRootItem().appendRow(self.roamnode)

    def addbuttonpressed(self):
        index = self.projectList.currentIndex()
        node = index.data(Qt.UserRole)
        if node and node.canadd:
            try:
                item = node.additem()
            except ValueError:
                return
            newindex = self.treemodel.indexFromItem(item)
            self.projectList.setCurrentIndex(newindex)

    def deletebuttonpressed(self):
        index = self.projectList.currentIndex()
        node = index.data(Qt.UserRole)
        if node.type() == Treenode.ProjectNode:
            self.projectwidget._closeqgisproject()

        title, removemessage = node.removemessage
        delete = node.canremove
        if node.canremove and removemessage:
            button = QMessageBox.warning(self, title, removemessage, QMessageBox.Yes | QMessageBox.No)
            delete = button == QMessageBox.Yes

        if delete:
            parentindex = index.parent()
            newindex = self.treemodel.index(index.row(), 0, parentindex)
            if parentindex.isValid():
                parent = parentindex.data(Qt.UserRole)
                parent.removeRow(index.row())

            self.projectList.setCurrentIndex(newindex)

    def loadprojects(self, projects):
        rootitem = self.treemodel.invisibleRootItem()
        projectsnode = ProjectsNode(folder=self.projectfolder)
        rootitem.appendRow(projectsnode)
        for project in projects:
            node = ProjectNode(project)
            projectsnode.appendRow(node)

        index = self.treemodel.index(0, 0, QModelIndex())
        self.projectList.setCurrentIndex(index)
        self.projectwidget.setprojectsfolder(self.projectfolder)
        index = self.treemodel.indexFromItem(projectsnode)
        self.projectList.expand(index)

    def nodeselected(self, index, _):
        node = index.data(Qt.UserRole)
        if node is None:
            return

        self.projectwidget.setpage(node.page)
        self.removeProjectButton.setEnabled(node.canremove)
        self.newProjectButton.setEnabled(node.canadd)
        #self.newProjectButton.setText(node.addtext)
        #self.removeProjectButton.setText(node.removetext)

        project = node.project
        if project and not self.projectwidget.project == project:
            # Only load the project if it's different the current one.
            self.projectwidget.setproject(project)

        if node.nodetype == Treenode.FormNode:
            self.projectwidget.setform(node.form)
        elif node.nodetype == Treenode.RoamNode:
            self.projectwidget.projectlabel.setText("IntraMaps Roam Config Manager")
        elif node.nodetype == Treenode.MapNode:
            self.projectwidget.loadmap()
        elif node.nodetype == Treenode.FormsNode:
            haslayers = self.projectwidget.checkcapturelayers()
            self.newProjectButton.setEnabled(haslayers)

        self.projectwidget.projectbuttonframe.setVisible(not project is None)

    def projectupdated(self):
        index = self.projectList.currentIndex()
        self.treemodel.dataChanged.emit(index, index)
