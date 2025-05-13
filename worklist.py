from QCL_interface import *
from PEM_interface import *
from mercurygui.main import *
from mercuryitc.mercury_driver import MercuryITC
from Keithley_test import Keithley
from BrukerControlPanel import BrukerControlPanel
from Pylon import Pylon
import time
from datetime import datetime
import socket
from PyQt5.QtTest import *
from ctypes import *
import ctypes
import arrow_rc
import sys
import win32com.client
import psutil
import os
import glob
import numpy as np
from scipy import optimize
import matplotlib.pyplot as plt
import shutil
import pandas as pd
from numpy.polynomial import polynomial as P
import pythoncom
from SourceMeter import SourceMeter
from get_project_path import cwd_path

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # set the size and title of the window
        self.setGeometry(100, 50, 1550, 1100)
        self.setWindowTitle('Hyperlist Interface')
        self.show()

        splitter = QSplitter(Qt.Horizontal)
        #left splittor for temperature controller
        left_splitter = QSplitter(Qt.Vertical)
        # right splitter for control widget and data recording widget
        right_splitter = QSplitter(Qt.Vertical)
        self.setCentralWidget(splitter)

        global temp_widget
        global temp_widget2
        global bruker_control_widget
        global control_widget
        # global data_recording_widget

        """
        Notes for installing Mercury ITC on new computer:
        1. Connect Mercury to the computer with USB-B
        2. Update OI_Mercury_USB_Driver to the respective port (change Windows setting if the update process is rejected due to invalid electronic signature)
        3. If the COM port number is large, change it to a small one (1-4 suggested)
        4. Make sure the setting on Mercury is changed to "USB" "SCPI" "Baud rate = 11520"
        5. Use tera term or the official connection checking software by Mercury to check connection
        6. Reboot the computer and Mercury
        7. If it still doesn't work, copy the usbser.sys file in OI_Mercury_USB_Driver and replace the file with same name in C:/System32/drivers
        """

        polarizor_widget_show = False
        analyzer_widget_show = False
        bruker_widget_show = False
        translator_widget_show = False
        keithley_widget_show = False
        camera_widget_show = False

        mercury_address = "ASRL1::INSTR"
        visa_library = CONF.get("Connection", "VISA_LIBRARY")
        mercury = MercuryITC(mercury_address, visa_library, open_timeout=1)
        # temp_widget refers to the GUI of mercuryITC from mercurygui
        temp_widget = MercuryMonitorApp(mercury)
        temp_widget2 = MercuryMonitorApp(mercury)  # replace this to the Lakeshore GUI in future
        left_splitter.addWidget(temp_widget)
        left_splitter.addWidget(temp_widget2)
        temp_widget2.hide()

        bruker_control_widget = BrukerControlPanel()
        bruker_control_widget.setFrameStyle(QFrame.Panel | QFrame.Raised)
        control_widget = ControlWidget(self)
        control_widget.setFrameStyle(QFrame.Panel | QFrame.Raised)
        # data_recording_widget = DataRecordingWidget(self)
        # data_recording_widget.setFrameStyle(QFrame.Panel | QFrame.Raised)
        right_splitter.addWidget(bruker_control_widget)
        right_splitter.addWidget(control_widget)
        # right_splitter.addWidget(data_recording_widget)

        temp_widget.lockin.keithley = keithley_widget

        splitter.addWidget(left_splitter)
        splitter.addWidget(right_splitter)

        bruker_control_widget.temp_sensor_cb.currentTextChanged.connect(self.change_temp_widget)

        if polarizor_widget_show:
            pol_new_widget.show()
            pol_thor_widget.show()
        else:
            pol_new_widget.hide()
            pol_thor_widget.hide()
        if analyzer_widget_show:
            ana_new_widget.show()
            ana_thor_widget.show()
        else:
            ana_new_widget.hide()
            ana_thor_widget.hide()
        if bruker_widget_show:
            bruker_widget.show()
        else:
            bruker_widget.hide()
        if translator_widget_show:
            tran_widget.show()
        else:
            tran_widget.hide()
        if keithley_widget_show:
            keithley_widget.show()
        else:
            keithley_widget.hide()
        if camera_widget_show:
            camera_widget.show()
        else:
            camera_widget.hide()

    def change_temp_widget(self):
        if bruker_control_widget.temp_sensor_cb.currentText() == "MercuryITC":
            # temp_widget2.hide()
            temp_widget.show()
        elif bruker_control_widget.temp_sensor_cb.currentText() == "Lakeshore":
            temp_widget.hide()
            # temp_widget2.show()
        elif bruker_control_widget.temp_sensor_cb.currentText() == "None":
            temp_widget.hide()
            temp_widget2.hide()


class Newport(QFrame):
    def __init__(self):
        super().__init__()
        self.setGeometry(700, 400, 500, 300)
        #self.show()
        self.initUI()
        self.angle_data = []
        self.connected = False

    def initUI(self):
        # create main grid to organize layout
        main_grid = QGridLayout()
        main_grid.setSpacing(10)
        self.setLayout(main_grid)
        self.setWindowTitle("Newport")

        # create resource manager to connect to the instrument and store resources in a list
        instruments.rm = visa.ResourceManager()
        resources = instruments.rm.list_resources()

        # create a combo box to allow the user to connect with a given instrument then add all resources
        self.connection_box = QComboBox()
        self.connection_box.addItem('Connect to rotator...')
        self.connection_box.addItems(resources)
        self.connection_box.currentIndexChanged.connect(self.connectInstrument)
        main_grid.addWidget(self.connection_box, 0, 0)

        # create a label to show connection of the instrument with check or cross mark
        self.connection_indicator = QLabel(u'\u274c ')  # cross mark by default because not connected yet
        main_grid.addWidget(self.connection_indicator, 0, 1)

        # position labels
        curr_pos = QLabel('Current Position')  # above the slider
        rel_pos = QLabel('Relative Position')  # below slider
        main_grid.addWidget(curr_pos, 1, 0)
        main_grid.addWidget(rel_pos, 3, 0, 1, 1, Qt.AlignBottom)

        # enable/disable button
        self.enable_btn = QPushButton('Enable/Disable')
        self.enable_btn.setEnabled(False)
        self.enable_btn.clicked.connect(self.toggleEnabled)
        main_grid.addWidget(self.enable_btn, 1, 1, 1, 2, Qt.AlignCenter)

        # absolute position slider
        self.abs_pos_sld = QDoubleSlider(Qt.Horizontal)
        self.abs_pos_sld.setTickPosition(QSlider.TicksBelow)
        self.abs_pos_sld.setEnabled(False)
        self.abs_pos_sld.sliderReleased.connect(self.setSliderPos)
        self.abs_pos_sld.setTickInterval(500)
        self.min_pos = QLabel('Min')  # bottom left of slider
        self.max_pos = QLabel('Max')  # bottom right of slider
        slider_vbox = QVBoxLayout()
        slider_vbox.addWidget(self.abs_pos_sld)
        min_max_hbox = QHBoxLayout()
        min_max_hbox.addWidget(self.min_pos)
        min_max_hbox.addStretch()
        min_max_hbox.addWidget(self.max_pos)
        slider_vbox.addLayout(min_max_hbox)
        main_grid.addLayout(slider_vbox, 2, 0)

        # absolute position spin box
        self.abs_pos_sb = QDoubleSpinBox()  # right of slider
        self.abs_pos_sb.setDecimals(4)
        self.abs_pos_sb.setSingleStep(0.0001)
        self.abs_pos_sb.setEnabled(False)
        self.abs_pos_sb.editingFinished.connect(self.setSpinboxPos)
        main_grid.addWidget(self.abs_pos_sb, 2, 1)

        # led indicator
        self.rotr_ind = QLedIndicator('orange')
        main_grid.addWidget(self.rotr_ind, 2, 2)

        # relative position buttons and spinbox
        self.rel_left = QPushButton(u'\u25C0')  # left of relative position spinbox
        self.rel_left.setFixedWidth(20)
        self.rel_left.clicked.connect(self.moveRelLeft)
        self.rel_right = QPushButton(u'\u25B6')  # right of relative position spinbox
        self.rel_right.setFixedWidth(20)
        self.rel_right.clicked.connect(self.moveRelRight)
        self.rel_left.setEnabled(False)
        self.rel_right.setEnabled(False)
        self.rel_pos_sb = QDoubleSpinBox()  # below slider
        self.rel_pos_sb.setDecimals(4)
        self.rel_pos_sb.setSingleStep(0.0001)
        self.rel_pos_sb.setAlignment(Qt.AlignHCenter)
        rel_pos_hbox = QHBoxLayout()
        rel_pos_hbox.addWidget(self.rel_left)
        rel_pos_hbox.addWidget(self.rel_pos_sb)
        rel_pos_hbox.addWidget(self.rel_right)
        main_grid.addLayout(rel_pos_hbox, 4, 0, 2, 1)

        # led indicator and current state labels
        curr_state_head = QLabel('Current State')
        self.curr_state = QLineEdit('')
        self.curr_state.setAlignment(Qt.AlignHCenter)
        self.curr_state.setReadOnly(True)
        main_grid.addWidget(curr_state_head, 4, 1, 1, 2, Qt.AlignBottom | Qt.AlignHCenter)
        main_grid.addWidget(self.curr_state, 5, 1, 1, 2, Qt.AlignTop | Qt.AlignHCenter)

    def connectInstrument(self):
        # if a selection is chosen that is not just the default prompt
        if (self.connection_box.currentText() != 'Connect to rotator...'):
            # get the chopper name and connect the chopper
            rotr_name = self.connection_box.currentText()

            # store controller states to tell when rotator is moving, disabled, ready, etc.
            self.controller_states = {'a': 'NOT REFERENCED',
                                      '0a': 'NOT REFERENCED from reset',
                                      '0b': 'NOT REFERENCED from HOMING',
                                      '0c': 'NOT REFERENCED from CONFIGURATION',
                                      '0d': 'NOT REFERENCED from DISABLE',
                                      '0e': 'NOT REFERENCED from READY',
                                      '0f': 'NOT REFERENCED from MOVING',
                                      '10': 'NOT REFERENCED no parameters',
                                      '14': 'CONFIGURATION',
                                      '1e': 'HOMING',
                                      '28': 'MOVING',
                                      '32': 'READY from HOMING',
                                      '33': 'READY from MOVING',
                                      '34': 'READY from DISABLE',
                                      '3c': 'DISABLE from READY',
                                      '3d': 'DISABLE from MOVING'}

            if rotr_name[:4] == 'GPIB':
                return  # rotator can't be a GPIB port, so exit function

            instruments.rotr = instruments.rm.open_resource(rotr_name)

            # set baud rate to 921600 by default
            instruments.rotr.baud_rate = 921600

            ctrl_state = self.controller_states[instruments.rotr.query('1mm?')[3:].strip()]
            if ctrl_state.split(' ')[0] != 'READY':
                instruments.rotr.write('1OR')

            left_lim = float(instruments.rotr.query('1SL?')[3:])
            right_lim = float(instruments.rotr.query('1SR?')[3:])

            self.abs_pos_sb.setRange(left_lim, right_lim)
            self.rel_pos_sb.setRange(left_lim, right_lim)
            self.abs_pos_sld.setRange(left_lim, right_lim)

            self.min_pos.setText(str(left_lim))
            self.max_pos.setText(str(right_lim))

            self.updatePosDisplay()

            # change connection indicator to a check mark from a cross mark
            self.connection_indicator.setText(u'\u2705')
            self.connected = True

            # turn led indicator on and set appropriate color based on state
            ctrl_state = self.controller_states[instruments.rotr.query('1mm?')[3:].strip()]
            self.ready = (ctrl_state.split(' ')[0] == 'READY')

            if (self.ready):
                self.rotr_ind.changeColor('green')
                # enable position spinbox, slider, and buttons
                self.abs_pos_sb.setEnabled(True)
                self.abs_pos_sld.setEnabled(True)
                self.rel_left.setEnabled(True)
                self.rel_right.setEnabled(True)
                self.enable_btn.setText('Disable')
            else:
                self.enable_btn.setText('Enable')

            self.rotr_ind.setChecked(True)
            self.enable_btn.setEnabled(True)

            # update controller state every second (1000 ms)
            self.timer = QTimer()
            self.timer.timeout.connect(self.updateState)
            self.timer.start(1000)

    def moveRelLeft(self):
        val = self.rel_pos_sb.value() * (-1)
        instruments.rotr.write('1PR{}'.format(val))
        self.updatePosDisplay()

    def moveRelRight(self):
        val = self.rel_pos_sb.value()
        instruments.rotr.write('1PR{}'.format(val))
        self.updatePosDisplay()

    def setSpinboxPos(self):
        val = self.abs_pos_sb.value()
        self.abs_pos_sld.setValue(val)
        self.angle_data.append(val)
        instruments.rotr.write('1PA{}'.format(val))

    def setSliderPos(self):
        val = self.abs_pos_sld.value()
        self.abs_pos_sb.setValue(val)
        self.angle_data.append(val)
        instruments.rotr.write('1PA{}'.format(val))

    def updateState(self):
        try:
            ctrl_state = self.controller_states[instruments.rotr.query('1mm?')[3:].strip()]
            self.curr_state.setText(ctrl_state)
            self.ready = (ctrl_state.split(' ')[0] == 'READY')

            if (self.ready):
                # enable position spinbox, slider, and buttons
                self.abs_pos_sb.setEnabled(True)
                self.abs_pos_sld.setEnabled(True)
                self.rel_left.setEnabled(True)
                self.rel_right.setEnabled(True)
            else:
                # disable position spinbox, slider, and buttons
                self.abs_pos_sb.setEnabled(False)
                self.abs_pos_sld.setEnabled(False)
                self.rel_left.setEnabled(False)
                self.rel_right.setEnabled(False)
        except:
            print(1)
            self.connected = False
            self.initUI()
    def updatePosDisplay(self):
        abs_pos = float(instruments.rotr.query('1PA?')[3:])
        self.abs_pos_sb.setValue(abs_pos)
        self.abs_pos_sld.setValue(abs_pos)

    def toggleEnabled(self):
        ctrl_state = self.controller_states[instruments.rotr.query('1mm?')[3:].strip()]

        if (self.ready or ctrl_state == 'MOVING'):  # disable, then change text to enable
            instruments.rotr.write('1mm0')
            self.enable_btn.setText('Enable')
            self.rotr_ind.changeColor('orange')
        else:  # enable, then change text to disable
            instruments.rotr.write('1mm1')
            self.enable_btn.setText('Disable')
            self.rotr_ind.changeColor('green')

class Thorlabs(QFrame):
    def __init__(self):
        super().__init__()
        self.setGeometry(700, 400, 350, 450)
        #self.show()
        self.initUI()
        self.setWindowTitle("Thorlabs")
        self.enabled = False
        self.angle_data = []
        self.connected = False
        self.scale = 409600/3
        #os.chdir(r"C:\Program Files (x86)\Thorlabs\Kinesis")
        # Dynamically construct the absolute path to the DLL

        #old code that was breaking 
        #self.lib = ctypes.CDLL(r"Thorlabs.MotionControl.IntegratedStepperMotors.dll")

        #temp catch for loading the DLL if it doesnt work...
        dll_path = os.path.abspath(os.path.join(cwd_path, "Thorlabs.MotionControl.IntegratedStepperMotors.dll"))
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL not found at {dll_path}. Ensure the file exists and the path is correct.")
        try:
            self.lib = ctypes.CDLL(dll_path)
        except OSError as e:
            raise OSError(f"Failed to load DLL at {dll_path}. Ensure all dependencies are installed and the architecture matches. Error: {e}")
        

        # set up serial number variable
        self.serialNumber = c_char_p(b"55507524")  # S/N number on the mount
        self.deviceUnit = c_int()
        self.ins_pos = float()  # Variable to chase the current pos
        self.moveTimeout = 60.0
        self.moved = True  # Global flag to identify whether stage is moved
        self.homed = False  # Global flag to identify whether stage is homed
        # Device state data
        self.messageType = c_ushort()
        self.messageID = c_ushort()
        self.messageData = c_ulong()
        self.hold = 0

    def initUI(self):
        # create main grid to organize layout
        main_grid = QGridLayout()
        main_grid.setSpacing(10)
        self.setLayout(main_grid)

        note = QLabel("Serial Number")
        main_grid.addWidget(note, 0, 0)

        self.serial = QLineEdit("55507524")
        self.serial.setFixedWidth(100)
        main_grid.addWidget(self.serial, 1, 0)

        self.connection_btn = QPushButton("Connnect")
        self.connection_btn.clicked.connect(self.connectInstrument)
        main_grid.addWidget(self.connection_btn, 1, 1)

        # create a label to show connection of the instrument with check or cross mark
        self.connection_indicator = QLabel(u'\u274c ')  # cross mark by default because not connected yet
        main_grid.addWidget(self.connection_indicator, 1, 2)

        # position labels
        curr_pos = QLabel('Current Position')  # above the slider
        rel_pos = QLabel('Relative Position')  # below slider
        main_grid.addWidget(curr_pos, 2, 0)
        main_grid.addWidget(rel_pos, 4, 0, 1, 1, Qt.AlignBottom)

        # enable/disable button
        self.enable_btn = QPushButton('Enable/Disable')
        self.enable_btn.setEnabled(False)
        self.enable_btn.clicked.connect(self.toggleEnabled)
        main_grid.addWidget(self.enable_btn, 2, 1, 1, 2, Qt.AlignCenter)

        # absolute position slider
        self.abs_pos_sld = QDoubleSlider(Qt.Horizontal)
        self.abs_pos_sld.setTickPosition(QSlider.TicksBelow)
        self.abs_pos_sld.setEnabled(False)
        self.abs_pos_sld.sliderReleased.connect(self.setSliderPos)
        self.abs_pos_sld.setTickInterval(500)
        self.min_pos = QLabel('Min')  # bottom left of slider
        self.max_pos = QLabel('Max')  # bottom right of slider
        slider_vbox = QVBoxLayout()
        slider_vbox.addWidget(self.abs_pos_sld)
        min_max_hbox = QHBoxLayout()
        min_max_hbox.addWidget(self.min_pos)
        min_max_hbox.addStretch()
        min_max_hbox.addWidget(self.max_pos)
        slider_vbox.addLayout(min_max_hbox)
        main_grid.addLayout(slider_vbox, 3, 0)

        # absolute position spin box
        self.abs_pos_sb = QDoubleSpinBox()  # right of slider
        self.abs_pos_sb.setDecimals(4)
        self.abs_pos_sb.setSingleStep(0.0001)
        self.abs_pos_sb.setEnabled(False)
        self.abs_pos_sb.editingFinished.connect(self.setSpinboxPos)
        main_grid.addWidget(self.abs_pos_sb, 3, 1)

        # led indicator
        self.rotr_ind = QLedIndicator('orange')
        main_grid.addWidget(self.rotr_ind, 3, 2)

        # relative position buttons and spinbox
        self.rel_left = QPushButton(u'\u25C0')  # left of relative position spinbox
        self.rel_left.setFixedWidth(20)
        self.rel_left.clicked.connect(self.moveRelLeft)
        self.rel_right = QPushButton(u'\u25B6')  # right of relative position spinbox
        self.rel_right.setFixedWidth(20)
        self.rel_right.clicked.connect(self.moveRelRight)
        self.rel_left.setEnabled(False)
        self.rel_right.setEnabled(False)
        self.rel_pos_sb = QDoubleSpinBox()  # below slider
        self.rel_pos_sb.setDecimals(4)
        self.rel_pos_sb.setSingleStep(0.0001)
        self.rel_pos_sb.setAlignment(Qt.AlignHCenter)
        rel_pos_hbox = QHBoxLayout()
        rel_pos_hbox.addWidget(self.rel_left)
        rel_pos_hbox.addWidget(self.rel_pos_sb)
        rel_pos_hbox.addWidget(self.rel_right)
        main_grid.addLayout(rel_pos_hbox, 5, 0, 2, 1)

        # led indicator and current state labels
        curr_state_head = QLabel('Current State')
        self.curr_state = QLineEdit('')
        self.curr_state.setAlignment(Qt.AlignHCenter)
        self.curr_state.setReadOnly(True)
        main_grid.addWidget(curr_state_head, 5, 1, 1, 2, Qt.AlignBottom | Qt.AlignHCenter)
        main_grid.addWidget(self.curr_state, 6, 1, 1, 2, Qt.AlignTop | Qt.AlignHCenter)

    def connectInstrument(self):
        # if a selection is chosen that is not just the default prompt
        if (self.serial.text() != ""):
            # get the chopper name and connect the chopper
            serial_number = self.serial.text()
            if len(serial_number) != 8:
                QMessageBox.warning(self, "Serial Number", "Serial number is a 8 digit number!")
                return  # serial number is a 8 digit number

            self.serialNumber = c_char_p(serial_number.encode())
            # Build device list
            self.lib.TLI_BuildDeviceList()

            # constants for the K10CR1
            stepsPerRev = 200
            gearBoxRatio = 120
            pitch = 360.0

            # set up device
            self.lib.ISC_Open(self.serialNumber)
            self.lib.ISC_StartPolling(self.serialNumber, c_int(200))

            #time.sleep(3)

            self.lib.ISC_EnableChannel(self.serialNumber)
            self.lib.ISC_ClearMessageQueue(self.serialNumber)

            self.lib.ISC_SetMotorParamsExt(self.serialNumber, c_double(stepsPerRev), c_double(gearBoxRatio), c_double(pitch))
            self.lib.ISC_LoadSettings(self.serialNumber)

            left_lim = 0.0
            right_lim = 360.0

            self.abs_pos_sb.setRange(left_lim, right_lim)
            self.rel_pos_sb.setRange(left_lim, right_lim)
            self.abs_pos_sld.setRange(left_lim, right_lim)

            self.min_pos.setText(str(left_lim))
            self.max_pos.setText(str(right_lim))

            self.updatePosDisplay()
            self.enabled = True

            # change connection indicator to a check mark from a cross mark
            self.connection_indicator.setText(u'\u2705')
            self.connected = True

            # turn led indicator on and set appropriate color based on state
            if not self.moved:
                ctrl_state = "MOVING"
            else:
                ctrl_state = "READY"
            self.ready = (ctrl_state == "READY")

            if (self.ready and self.enabled == True):
                self.rotr_ind.changeColor('green')
                # enable position spinbox, slider, and buttons
                self.abs_pos_sb.setEnabled(True)
                self.abs_pos_sld.setEnabled(True)
                self.rel_left.setEnabled(True)
                self.rel_right.setEnabled(True)
                self.enable_btn.setText('Disable')
            else:
                self.enable_btn.setText('Enable')

            self.rotr_ind.setChecked(True)
            self.enable_btn.setEnabled(True)

            # update controller state every second (1000 ms)
            self.timer = QTimer()
            self.timer.timeout.connect(self.updateState)
            self.timer.start(1000)

    def moveRelLeft(self):
        val = self.rel_pos_sb.value() * (-1)
        realUnit = c_double(val)
        self.lib.ISC_GetDeviceUnitFromRealValue(self.serialNumber, realUnit, byref(self.deviceUnit), 0)
        self.lib.ISC_MoveRelativeDistance(self.serialNumber, self.deviceUnit)

        # Self check: whether the moving command is finished
        self.moved = False

    def moveRelRight(self):
        val = self.rel_pos_sb.value()
        realUnit = c_double(val)
        self.lib.ISC_GetDeviceUnitFromRealValue(self.serialNumber, realUnit, byref(self.deviceUnit), 0)
        self.lib.ISC_MoveRelativeDistance(self.serialNumber, self.deviceUnit)

        # Self check: whether the moving command is finished
        self.moved = False

    def setSpinboxPos(self):
        val = self.abs_pos_sb.value()
        self.abs_pos_sld.setValue(val)
        self.angle_data.append(val)
        realUnit = c_double(val)
        self.lib.ISC_GetDeviceUnitFromRealValue(self.serialNumber, realUnit, byref(self.deviceUnit), 0)
        self.lib.ISC_MoveToPosition(self.serialNumber, self.deviceUnit)

        # Self check: whether the moving command is finished
        self.moved = False

    def setSliderPos(self):
        val = self.abs_pos_sld.value()
        self.abs_pos_sb.setValue(val)
        self.angle_data.append(val)
        realUnit = c_double(val)
        self.lib.ISC_GetDeviceUnitFromRealValue(self.serialNumber, realUnit, byref(self.deviceUnit), 0)
        self.lib.ISC_MoveToPosition(self.serialNumber, self.deviceUnit)

        # Self check: whether the moving command is finished
        self.moved = False

    def updateState(self):
        if self.moved:
            ctrl_state = "READY"
        else:
            ctrl_state = "MOVING"
            self.hold += 1

        self.curr_state.setText(ctrl_state)
        self.ready = (ctrl_state == 'READY')

        if (self.ready and self.enabled == True):
            # enable position spinbox, slider, and buttons
            self.abs_pos_sb.setEnabled(True)
            self.abs_pos_sld.setEnabled(True)
            self.rel_left.setEnabled(True)
            self.rel_right.setEnabled(True)
        else:
            # disable position spinbox, slider, and buttons
            self.abs_pos_sb.setEnabled(False)
            self.abs_pos_sld.setEnabled(False)
            self.rel_left.setEnabled(False)
            self.rel_right.setEnabled(False)

        while self.moved == False and self.hold == 2:
            self.lib.ISC_GetNextMessage(self.serialNumber, byref(self.messageType), byref(self.messageID), byref(self.messageData))
            if (self.messageID.value == 1 and self.messageType.value == 2):
                self.moved = True
                self.hold = 0

    def updatePosDisplay(self):
        abs_pos = self.lib.ISC_GetPosition(self.serialNumber) / self.scale
        self.abs_pos_sb.setValue(abs_pos)
        self.abs_pos_sld.setValue(abs_pos)

    def toggleEnabled(self):
        if (self.enabled == True):  # disable, then change text to enable
            self.lib.ISC_DisableChannel()
            self.enable_btn.setText('Enable')
            self.rotr_ind.changeColor('orange')
            self.enabled = False
        else:  # enable, then change text to disable
            self.lib.ISC_EnableChannel()
            self.enable_btn.setText('Disable')
            self.rotr_ind.changeColor('green')
            self.enabled = True

class Translator(QFrame):
    def __init__(self):
        super().__init__()
        self.setGeometry(700, 350, 500, 550)
        self.Tango = windll.LoadLibrary(r"{}\Tango_DLL.dll".format(cwd_path))  # give location of dll (current directory)
        self.LSID = c_int()
        self.trans_name = ""
        self.in_Opus = False
        self.show()
        self.initUI()
        self.x = self.get_x_pos()
        self.y = self.get_y_pos()
        self.z = self.get_z_pos()
        self.x_home = self.get_x_pos()
        self.y_home = self.get_y_pos()
        self.z_home = self.get_z_pos()
        self.connected = False

    def initUI(self):
        # create main grid to organize layout
        main_grid = QGridLayout()
        main_grid.setSpacing(5)
        self.setLayout(main_grid)
        self.setWindowTitle("Tango")

        # create resource manager to connect to the instrument and store resources in a list
        instruments.rm = visa.ResourceManager()
        resources = instruments.rm.list_resources()
        resource = []
        for i in range(len(resources)):
            resource.append(resources[i])
            if resource[i] == "ASRL4::INSTR":
                resource[i] += " (default)"

        # create a combo box to allow the user to connect with a given instrument then add all resources
        self.connection_box = QComboBox()
        self.connection_box.addItem('Connect to translator...')
        self.connection_box.addItems(resource)
        self.connection_box.currentIndexChanged.connect(self.connectInstrument)
        main_grid.addWidget(self.connection_box, 0, 2)

        # create a label to show connection of the instrument with check or cross mark
        self.connection_indicator = QLabel(u'\u274c ')  # cross mark by default because not connected yet
        main_grid.addWidget(self.connection_indicator, 0, 3)

        # reconnect/disconnect button
        self.connect_btn = QPushButton('Reconnect/Disconnect')
        self.connect_btn.setEnabled(False)
        self.connect_btn.clicked.connect(self.swicthConnection)
        main_grid.addWidget(self.connect_btn, 2, 2, Qt.AlignCenter)

        # set position label
        enter_pos = QLabel('Active / Position')  # above the slider
        main_grid.addWidget(enter_pos, 0, 0)

        # set xyz check boxes
        self.x_check_box = QCheckBox()
        self.x_check_box.setText(f"X ({chr(956)}m)")
        self.x_check_box.setEnabled(False)
        main_grid.addWidget(self.x_check_box, 1, 0, 1, 1, Qt.AlignCenter)
        self.y_check_box = QCheckBox()
        self.y_check_box.setText(f"Y ({chr(956)}m)")
        self.y_check_box.setEnabled(False)
        main_grid.addWidget(self.y_check_box, 2, 0, 1, 1, Qt.AlignCenter)
        self.z_check_box = QCheckBox()
        self.z_check_box.setText(f"Z ({chr(956)}m)")
        self.z_check_box.setEnabled(False)
        main_grid.addWidget(self.z_check_box, 3, 0, 1, 1, Qt.AlignCenter)

        # set xyz spin boxes
        self.x_sb = QDoubleSpinBox()
        self.x_sb.setDecimals(2)
        self.x_sb.setValue(0.00)
        self.x_sb.setEnabled(False)
        main_grid.addWidget(self.x_sb, 1, 1, Qt.AlignCenter)
        self.y_sb = QDoubleSpinBox()
        self.y_sb.setDecimals(2)
        self.y_sb.setValue(0.00)
        self.y_sb.setEnabled(False)
        main_grid.addWidget(self.y_sb, 2, 1, Qt.AlignCenter)
        self.z_sb = QDoubleSpinBox()
        self.z_sb.setDecimals(2)
        self.z_sb.setValue(0.00)
        self.z_sb.setEnabled(False)
        main_grid.addWidget(self.z_sb, 3, 1, Qt.AlignCenter)

        # enable/disable button
        self.enable_btn = QPushButton('Enable/Disable')
        self.enable_btn.setEnabled(False)
        self.enable_btn.clicked.connect(self.toggleEnabled)
        main_grid.addWidget(self.enable_btn, 3, 2, Qt.AlignCenter)

        # led indicator
        self.trans_ind = QLedIndicator('orange')
        main_grid.addWidget(self.trans_ind, 3, 3)

        # Move and Set / Get labels
        move = QLabel('Move')
        main_grid.addWidget(move, 4, 0)
        setget = QLabel('Set / Get')
        main_grid.addWidget(setget, 4, 1)

        # buttons under Move
        self.absolute_btn = QPushButton('Absolute')
        self.absolute_btn.setEnabled(False)
        self.absolute_btn.clicked.connect(self.absolute)
        main_grid.addWidget(self.absolute_btn, 5, 0, Qt.AlignCenter)
        self.relative_btn = QPushButton('Relative')
        self.relative_btn.setEnabled(False)
        self.relative_btn.clicked.connect(self.relative)
        main_grid.addWidget(self.relative_btn, 6, 0, Qt.AlignCenter)
        self.center_btn = QPushButton('Center')
        self.center_btn.setEnabled(False)
        self.center_btn.clicked.connect(self.center)
        main_grid.addWidget(self.center_btn, 7, 0, Qt.AlignCenter)
        self.home_btn = QPushButton('Home')
        self.home_btn.setEnabled(False)
        self.home_btn.clicked.connect(self.home)
        main_grid.addWidget(self.home_btn, 8, 0, Qt.AlignCenter)

        # buttons under Set/Get
        self.set_pos_btn = QPushButton('Set Pos')
        self.set_pos_btn.setEnabled(False)
        self.set_pos_btn.clicked.connect(self.set_pos)
        main_grid.addWidget(self.set_pos_btn, 5, 1, Qt.AlignCenter)
        self.set_zero_btn = QPushButton('Set Zero')
        self.set_zero_btn.setEnabled(False)
        self.set_zero_btn.clicked.connect(self.set_zero)
        main_grid.addWidget(self.set_zero_btn, 6, 1, Qt.AlignCenter)
        self.edit_home_btn = QPushButton('Edit Home')
        self.edit_home_btn.setEnabled(False)
        self.edit_home_btn.clicked.connect(self.edit_home)
        main_grid.addWidget(self.edit_home_btn, 7, 1, Qt.AlignCenter)
        self.edit_vel_btn = QPushButton('Edit Velocity')
        self.edit_vel_btn.setEnabled(False)
        self.edit_vel_btn.clicked.connect(self.edit_vel)
        main_grid.addWidget(self.edit_vel_btn, 8, 1, Qt.AlignCenter)

        # Joystick control label
        joystick_control = QLabel('Joystick Control')
        main_grid.addWidget(joystick_control, 9, 0)

        # X/Y label and buttons
        xy_grid = QGridLayout()
        xy_grid.setSpacing(5)
        x_y = QLabel('X/Y')
        xy_grid.addWidget(x_y, 1, 1, Qt.AlignCenter)
        self.y_up_btn = QPushButton()
        self.y_up_btn.setEnabled(False)
        self.y_up_btn.pressed.connect(self.y_up)
        self.y_up_btn.released.connect(self.joystick_stop)
        self.y_up_btn.setStyleSheet("image: url(:/arrow/Up.png);")
        xy_grid.addWidget(self.y_up_btn, 0, 1, Qt.AlignCenter)
        self.y_down_btn = QPushButton()
        self.y_down_btn.setEnabled(False)
        self.y_down_btn.pressed.connect(self.y_down)
        self.y_down_btn.released.connect(self.joystick_stop)
        self.y_down_btn.setStyleSheet("image: url(:/arrow/Down.png);")
        xy_grid.addWidget(self.y_down_btn, 2, 1, Qt.AlignCenter)
        self.x_left_btn = QPushButton()
        self.x_left_btn.setEnabled(False)
        self.x_left_btn.pressed.connect(self.x_left)
        self.x_left_btn.released.connect(self.joystick_stop)
        self.x_left_btn.setStyleSheet("image: url(:/arrow/Left.png);")
        xy_grid.addWidget(self.x_left_btn, 1, 0, Qt.AlignCenter)
        self.x_right_btn = QPushButton()
        self.x_right_btn.setEnabled(False)
        self.x_right_btn.pressed.connect(self.x_right)
        self.x_right_btn.released.connect(self.joystick_stop)
        self.x_right_btn.setStyleSheet("image: url(:/arrow/Right.png);")
        xy_grid.addWidget(self.x_right_btn, 1, 2, Qt.AlignCenter)
        main_grid.addLayout(xy_grid, 10, 0, 2, 1)

        # Z label and buttons
        z_grid = QGridLayout()
        z_grid.setSpacing(5)
        z = QLabel('Z')
        z_grid.addWidget(z, 1, 0, Qt.AlignCenter)
        self.z_up_btn = QPushButton()
        self.z_up_btn.setEnabled(False)
        self.z_up_btn.pressed.connect(self.z_up)
        self.z_up_btn.released.connect(self.joystick_stop)
        self.z_up_btn.setStyleSheet("image: url(:/arrow/Up.png);")
        z_grid.addWidget(self.z_up_btn, 0, 0, Qt.AlignCenter)
        self.z_down_btn = QPushButton()
        self.z_down_btn.setEnabled(False)
        self.z_down_btn.pressed.connect(self.z_down)
        self.z_down_btn.released.connect(self.joystick_stop)
        self.z_down_btn.setStyleSheet("image: url(:/arrow/Down.png);")
        z_grid.addWidget(self.z_down_btn, 2, 0, Qt.AlignCenter)
        main_grid.addLayout(z_grid, 10, 1, 2, 1)

        # Current Position labels
        current_pos = QLabel('Current Position')
        main_grid.addWidget(current_pos, 4, 2)
        x_pos = QLabel(f"X ({chr(956)}m)")
        main_grid.addWidget(x_pos, 5, 2)
        y_pos = QLabel(f"Y ({chr(956)}m)")
        main_grid.addWidget(y_pos, 6, 2)
        z_pos = QLabel(f"Z ({chr(956)}m)")
        main_grid.addWidget(z_pos, 7, 2)

        # Actual position readings of xyz
        self.x_current_pos = QLabel("0.00")
        main_grid.addWidget(self.x_current_pos, 5, 3, Qt.AlignCenter)
        self.y_current_pos = QLabel("0.00")
        main_grid.addWidget(self.y_current_pos, 6, 3, Qt.AlignCenter)
        self.z_current_pos = QLabel("0.00")
        main_grid.addWidget(self.z_current_pos, 7, 3, Qt.AlignCenter)

        # Current state label and reading
        curr_state_head = QLabel('Current State')
        self.curr_state = QLineEdit('')
        self.curr_state.setAlignment(Qt.AlignHCenter)
        self.curr_state.setReadOnly(True)
        main_grid.addWidget(curr_state_head, 8, 2, 1, 2, Qt.AlignBottom | Qt.AlignHCenter)
        main_grid.addWidget(self.curr_state, 9, 2, 1, 2, Qt.AlignTop | Qt.AlignHCenter)

        # stop button
        self.stop_btn = QPushButton('Stop')
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop)
        main_grid.addWidget(self.stop_btn, 10, 3, 1, 1, Qt.AlignTop | Qt.AlignCenter)

        # start OPUS button
        self.start_OPUS_btn = QPushButton('Start OPUS')
        self.start_OPUS_btn.setEnabled(False)
        self.start_OPUS_btn.clicked.connect(self.start_OPUS)
        main_grid.addWidget(self.start_OPUS_btn, 10, 2, 1, 1, Qt.AlignTop | Qt.AlignCenter)

        self.enable_real_joystick_btn = QPushButton("Enable real joystick")
        self.enable_real_joystick_btn.setEnabled(False)
        self.enable_real_joystick_btn.clicked.connect(self.enable_disable_joystick)
        main_grid.addWidget(self.enable_real_joystick_btn, 11, 2, 1, 1, Qt.AlignCenter)

    def connectInstrument(self):

        if self.Tango == 0:
            print("Error: failed to load DLL")
            sys.exit(0)

        # Tango_DLL.dll loaded successfully

        if self.Tango.LSX_CreateLSID == 0:
            print("unexpected error. required DLL function CreateLSID() missing")
            sys.exit(0)
        # continue only if required function exists

        error = int     #value is either DLL or Tango error number if not zero
        error = self.Tango.LSX_CreateLSID(byref(self.LSID))
        if error > 0:
            print("Error: " + str(error))
            sys.exit(0)

        # OK: got communication ID from DLL (usually 1. may vary with multiple connections)
        # keep this LSID in mind during the whole session

        if self.Tango.LSX_ConnectSimple == 0:
            print("unexepcted error. required DLL function ConnectSimple() missing")
            sys.exit(0)
        # continue only if required function exists

        # if a selection is chosen that is not just the default prompt
        if (self.connection_box.currentText() != 'Connect to translator...'):
            # get the translator name and connect to the translator
            if self.connection_box.currentText()[5] == ":":
                self.trans_name = "COM" + self.connection_box.currentText()[4]
            else:
                self.trans_name = "COM" + self.connection_box.currentText()[4:6]

            # set baud rate to 57600 by default
            baud_rate = 57600

            trans_name = ctypes.c_char_p(self.trans_name.encode())
            error = self.Tango.LSX_ConnectSimple(self.LSID, 1, trans_name, baud_rate, 0)
            if error > 0:
                print("Error: LSX_ConnectSimple " + str(error))
                if self.trans_name == "COM4":
                    QMessageBox.warning(self, "Tango and Opus conflict", "Please turn off the Video Wizard in OPUS and change to Measurement Mode in the software or manually on front panel of Hyperion")
                    self.connected = False
                return
            print("TANGO is now successfully connected to DLL")
            self.connected = True

            # store controller states to tell when rotator is moving, disabled, ready, etc.
            self.controller_states = {'@': 'Axis stands still',
                                      'M': 'Axis is in motion',
                                      ' ': 'Axis is not enabled',
                                      'J': 'Joystick switched on',
                                      'C': 'Axis is in closed loop',
                                      'A': 'Return message after calibration',
                                      'E': 'Error when calibration',
                                      'D': 'Return message after measuring stage travel range (m)',
                                      'U': 'Setup mode',
                                      'T': 'Timeout'}
            # change connection indicator to a check mark from a cross mark
            self.connection_indicator.setText(u'\u2705')
            self.connect_btn.setEnabled(True)
            self.connect_btn.setText("Disconnect")

            # turn led indicator on and set appropriate color based on state
            self.Tango.LSX_SetActiveAxes(self.LSID, 7)
            ctrl_state = c_char()
            self.Tango.LSX_GetStatusAxis(self.LSID, byref(ctrl_state), 16)
            ctrl_state = str(ctrl_state.value)[2]
            self.ready = (ctrl_state != 'M')

            if (self.ready):
                self.trans_ind.changeColor('green')
                # enable every buttons
                self.x_check_box.setEnabled(True)
                self.y_check_box.setEnabled(True)
                self.z_check_box.setEnabled(True)
                self.absolute_btn.setEnabled(True)
                self.relative_btn.setEnabled(True)
                self.center_btn.setEnabled(True)
                self.home_btn.setEnabled(True)
                self.set_pos_btn.setEnabled(True)
                self.set_zero_btn.setEnabled(True)
                self.edit_home_btn.setEnabled(True)
                self.edit_vel_btn.setEnabled(True)
                self.stop_btn.setEnabled(True)
                self.start_OPUS_btn.setEnabled(True)
                self.enable_btn.setText('Disable')
            else:
                self.enable_btn.setText('Enable')

            self.trans_ind.setChecked(True)
            self.enable_btn.setEnabled(True)

            # update controller state every second (1000 ms)
            self.timer = QTimer()
            self.timer.timeout.connect(self.updateState)
            self.timer.start(1000)

            self.set_limit()

    def disconnect(self):
        self.Tango.LSX_Disconnect(self.LSID)
        self.connection_indicator.setText(u'\u274c')
        self.connected = False
        self.connect_btn.setText('Reconnect')
        self.timer.stop()

    def reconnect(self):
        baud_rate = 57600
        trans_name = ctypes.c_char_p(self.trans_name.encode())
        error = self.Tango.LSX_ConnectSimple(self.LSID, 1, trans_name, baud_rate, 0)
        if error > 0:
            QMessageBox.warning(self, "Tango Connection", "Tango fails to reconnect!")
            return
        self.connection_indicator.setText(u'\u2705')
        self.connected = True
        self.connect_btn.setText('Disconnect')
        self.timer.start(1000)

    def updateState(self):
        if not self.in_Opus:
            ctrl_state = c_char()
            self.Tango.LSX_GetStatusAxis(self.LSID, byref(ctrl_state), 16)
            ctrl_state = str(ctrl_state.value)[2]
            try:
                self.curr_state.setText(self.controller_states[ctrl_state])
            except:
                self.curr_state.setText("Invalid index")
            flag = c_int()
            self.Tango.LSX_GetActiveAxes(self.LSID, byref(flag))
            self.ready = (ctrl_state != 'M' and flag.value != 0)

            if (self.ready):
                # enable position spinbox, slider, and buttons
                self.x_check_box.setEnabled(True)
                self.y_check_box.setEnabled(True)
                self.z_check_box.setEnabled(True)
                self.x_sb.setEnabled(self.x_check_box.isChecked())
                self.y_sb.setEnabled(self.y_check_box.isChecked())
                self.z_sb.setEnabled(self.z_check_box.isChecked())
                self.absolute_btn.setEnabled(True)
                self.relative_btn.setEnabled(True)
                self.center_btn.setEnabled(True)
                self.home_btn.setEnabled(True)
                self.set_pos_btn.setEnabled(True)
                self.set_zero_btn.setEnabled(True)
                self.edit_home_btn.setEnabled(True)
                self.edit_vel_btn.setEnabled(True)
                self.y_up_btn.setEnabled(self.y_check_box.isChecked())
                self.y_down_btn.setEnabled(self.y_check_box.isChecked())
                self.x_left_btn.setEnabled(self.x_check_box.isChecked())
                self.x_right_btn.setEnabled(self.x_check_box.isChecked())
                self.z_up_btn.setEnabled(self.z_check_box.isChecked())
                self.z_down_btn.setEnabled(self.z_check_box.isChecked())
                self.start_OPUS_btn.setEnabled(True)
                self.enable_real_joystick_btn.setEnabled(True)
            else:
                # disable position spinbox, slider, and buttons
                self.x_check_box.setEnabled(False)
                self.y_check_box.setEnabled(False)
                self.z_check_box.setEnabled(False)
                self.x_sb.setEnabled(False)
                self.y_sb.setEnabled(False)
                self.z_sb.setEnabled(False)
                self.absolute_btn.setEnabled(False)
                self.relative_btn.setEnabled(False)
                self.center_btn.setEnabled(False)
                self.home_btn.setEnabled(False)
                self.set_pos_btn.setEnabled(False)
                self.set_zero_btn.setEnabled(False)
                self.edit_home_btn.setEnabled(False)
                self.edit_vel_btn.setEnabled(False)
                self.start_OPUS_btn.setEnabled(False)
                self.enable_real_joystick_btn.setEnabled(False)

        self.x = self.get_x_pos()
        self.y = self.get_y_pos()
        self.z = self.get_z_pos()
        self.x_current_pos.setText(f"{self.x}")
        self.y_current_pos.setText(f"{self.y}")
        self.z_current_pos.setText(f"{self.z}")

    def toggleEnabled(self):

        flag = c_int()
        self.Tango.LSX_GetActiveAxes(self.LSID, byref(flag))

        if (flag.value != 0):  # disable, then change text to enable
            buttonReply = QMessageBox.question(self, 'Disable', "Are you sure to disable Tango?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if buttonReply == QMessageBox.No:
                return
            self.Tango.LSX_SetActiveAxes(self.LSID, 0)
            self.enable_btn.setText('Enable')
            self.trans_ind.changeColor('orange')
        else:  # enable, then change text to disable
            self.Tango.LSX_SetActiveAxes(self.LSID, 7)
            self.enable_btn.setText('Disable')
            self.trans_ind.changeColor('green')

    def swicthConnection(self):
        if self.connected:
            self.disconnect()
        else:  # enable, then change text to disable
            self.reconnect()

    def get_pos(self):
        x = c_double()
        y = c_double()
        z = c_double()
        a = c_double()
        self.Tango.LSX_GetPos(self.LSID, byref(x), byref(y), byref(z), byref(a))
        return x.value, y.value, z.value

    def get_x_pos(self):
        x, _, _ = self.get_pos()
        return x

    def get_y_pos(self):
        _, y, _ = self.get_pos()
        return y

    def get_z_pos(self):
        _, _, z = self.get_pos()
        return z

    def absolute(self):
        x = c_double(self.x)
        y = c_double(self.y)
        z = c_double(self.z)
        if self.x_check_box.checkState() != 0:
            x = c_double(self.x_sb.value())
        if self.y_check_box.checkState() != 0:
            y = c_double(self.y_sb.value())
        if self.z_check_box.checkState() != 0:
            z = c_double(self.z_sb.value())
        self.Tango.LSX_MoveAbs(self.LSID, x, y, z, c_double(0), c_bool(False))

    def relative(self):
        x = c_double(0)
        y = c_double(0)
        z = c_double(0)
        if self.x_check_box.checkState() != 0:
            x = c_double(self.x_sb.value())
        if self.y_check_box.checkState() != 0:
            y = c_double(self.y_sb.value())
        if self.z_check_box.checkState() != 0:
            z = c_double(self.z_sb.value())
        self.Tango.LSX_MoveRel(self.LSID, x, y, z, c_double(0), c_bool(False))

    def center(self):
        self.Tango.LSX_MoveAbs(self.LSID, c_double(0), c_double(0), c_double(0), c_double(0), c_bool(False))

    def set_pos(self):
        x = c_double(self.x)
        y = c_double(self.y)
        z = c_double(self.z)
        if self.x_check_box.checkState() != 0:
            x = c_double(self.x_sb.value())
        if self.y_check_box.checkState() != 0:
            y = c_double(self.y_sb.value())
        if self.z_check_box.checkState() != 0:
            z = c_double(self.z_sb.value())
        self.Tango.LSX_SetPos(self.LSID, x, y, z, c_double(0))

    def set_zero(self):
        self.Tango.LSX_SetPos(self.LSID, c_double(0), c_double(0), c_double(0), c_double(0))

    def home(self):
        self.Tango.LSX_MoveAbs(self.LSID, c_double(self.x_home), c_double(self.y_home), c_double(self.z_home), c_double(0), c_bool(False))

    def edit_home(self):
        self.Home = Home(self)

    """
    def pos_home(self):
        if self.x_check_box.checkState() != 0:
            self.x_home = self.x_sb.value()
        if self.y_check_box.checkState() != 0:
            self.y_home = self.y_sb.value()
        if self.z_check_box.checkState() != 0:
            self.z_home = self.z_sb.value()
    """
    def edit_vel(self):
        self.Velocity = Velocity(self)


    def y_up(self):
        self.Tango.LSX_SetDigJoySpeed(self.LSID, c_double(0), c_double(5.0), c_double(0), c_double(0))

    def y_down(self):
        self.Tango.LSX_SetDigJoySpeed(self.LSID, c_double(0), c_double(-5.0), c_double(0), c_double(0))

    def x_left(self):
        self.Tango.LSX_SetDigJoySpeed(self.LSID, c_double(5.0), c_double(0), c_double(0), c_double(0))

    def x_right(self):
        self.Tango.LSX_SetDigJoySpeed(self.LSID, c_double(-5.0), c_double(0), c_double(0), c_double(0))

    def z_up(self):
        self.Tango.LSX_SetDigJoySpeed(self.LSID, c_double(0), c_double(0), c_double(5.0), c_double(0))

    def z_down(self):
        self.Tango.LSX_SetDigJoySpeed(self.LSID, c_double(0), c_double(0), c_double(-5.0), c_double(0))

    def joystick_stop(self):
        self.Tango.LSX_SetDigJoySpeed(self.LSID, c_double(0), c_double(0), c_double(0), c_double(0))

    def enable_disable_joystick(self):
        if self.enable_real_joystick_btn.text() == "Enable real joystick":
            self.Tango.LSX_SetJoystickOn(self.LSID, c_bool(False), c_bool(True))
            self.enable_real_joystick_btn.setText("Disable real joystick")
        else:
            self.Tango.LSX_SetJoystickOff(self.LSID)
            self.enable_real_joystick_btn.setText("Enable real joystick")

    def set_limit(self):
        min = c_double()
        max = c_double()
        self.Tango.LSX_GetLimit(self.LSID, 1, byref(min), byref(max))
        self.x_sb.setMinimum(min.value)
        self.x_sb.setMaximum(max.value)
        self.x_min = min.value
        self.x_max = max.value
        self.Tango.LSX_GetLimit(self.LSID, 2, byref(min), byref(max))
        self.y_sb.setMinimum(min.value)
        self.y_sb.setMaximum(max.value)
        self.y_min = min.value
        self.y_max = max.value
        self.Tango.LSX_GetLimit(self.LSID, 3, byref(min), byref(max))
        self.z_sb.setMinimum(min.value)
        self.z_sb.setMaximum(max.value)
        self.z_min = min.value
        self.z_max = max.value

    def wait_until(self, period=0.25):
        timeout = 3000   # 50 minutes
        mustend = time.time() + timeout
        while time.time() < mustend:
            in_Opus = False
            for proc in psutil.process_iter(["pid", "name", "username"]):
                if proc.info["name"] == "opus.exe":
                    in_Opus = True
                    time.sleep(period)
            if not in_Opus:
                return True
        return False

    # Wait until OPUS is off, cannot hold for too long
    def start_OPUS(self):
        self.in_Opus = True
        self.disconnect()
        start = win32com.client.Dispatch("OpusCMD334.StartOpus")
        exePath = r"C:\Program Files\Bruker\OPUS_8.5.29\opus.exe"
        password = "OPUS"
        start.StartOpus(exePath, password)
        self.wait_until()
        self.reconnect()
        self.in_Opus = False

    # Stop the movement of axes immediately, without calibrating the axes
    def stop(self):
        self.Tango.LSX_StopAxes(self.LSID)

class Home(QFrame):
    def __init__(self, Translator):
        super().__init__()
        self.setGeometry(600, 350, 300, 200)
        self.trans = Translator
        self.LSID = Translator.LSID
        self.x_home = Translator.x_home
        self.y_home = Translator.y_home
        self.z_home = Translator.z_home
        self.x_min = Translator.x_min
        self.x_max = Translator.x_max
        self.y_min = Translator.y_min
        self.y_max = Translator.y_max
        self.z_min = Translator.z_min
        self.z_max = Translator.z_max
        self.show()
        self.initUI()

    def initUI(self):
        main_grid = QGridLayout()
        main_grid.setSpacing(5)
        self.setLayout(main_grid)
        self.setWindowTitle("Home")

         # set position label
        enter_pos = QLabel('Set Home Position')  # above the slider
        main_grid.addWidget(enter_pos, 0, 0)

        # set xyz check boxes
        self.x_label = QLabel(f"X ({chr(956)}m)")
        main_grid.addWidget(self.x_label, 1, 0, 1, 1, Qt.AlignCenter)
        self.y_label = QLabel(f"Y ({chr(956)}m)")
        main_grid.addWidget(self.y_label, 2, 0, 1, 1, Qt.AlignCenter)
        self.z_label = QLabel(f"Z ({chr(956)}m)")
        main_grid.addWidget(self.z_label, 3, 0, 1, 1, Qt.AlignCenter)

        # set xyz spin boxes
        self.x_sb = QDoubleSpinBox()
        self.x_sb.setDecimals(2)
        self.x_sb.setValue(self.x_home)
        self.x_sb.setEnabled(True)
        self.x_sb.setMinimum(self.x_min)
        self.x_sb.setMaximum(self.x_max)
        main_grid.addWidget(self.x_sb, 1, 1, Qt.AlignCenter)
        self.y_sb = QDoubleSpinBox()
        self.y_sb.setDecimals(2)
        self.y_sb.setValue(self.y_home)
        self.y_sb.setEnabled(True)
        self.y_sb.setMinimum(self.y_min)
        self.y_sb.setMaximum(self.y_max)
        main_grid.addWidget(self.y_sb, 2, 1, Qt.AlignCenter)
        self.z_sb = QDoubleSpinBox()
        self.z_sb.setDecimals(2)
        self.z_sb.setValue(self.z_home)
        self.z_sb.setEnabled(True)
        self.z_sb.setMinimum(self.z_min)
        self.z_sb.setMaximum(self.z_max)
        main_grid.addWidget(self.z_sb, 3, 1, Qt.AlignCenter)

        self.submit_btn = QPushButton('Submit')
        self.submit_btn.clicked.connect(self.submit)
        main_grid.addWidget(self.submit_btn, 4, 1, Qt.AlignCenter)

    def submit(self):
        self.trans.x_home = self.x_sb.value()
        self.trans.y_home = self.y_sb.value()
        self.trans.z_home = self.z_sb.value()
        self.close()

class Velocity(QFrame):
    def __init__(self, Translator):
        super().__init__()
        self.setGeometry(600, 350, 500, 200)
        self.trans = Translator
        self.LSID = Translator.LSID
        x = c_double()
        y = c_double()
        z = c_double()
        a = c_double()
        Translator.Tango.LSX_GetVel(Translator.LSID, byref(x), byref(y), byref(z), byref(a))
        self.vx_max = x.value
        self.vy_max = y.value
        self.vz_max = z.value
        Translator.Tango.LSX_GetVelFac(Translator.LSID, byref(x), byref(y), byref(z), byref(a))
        self.vx_real = self.vx_max * x.value
        self.vy_real = self.vy_max * y.value
        self.vz_real = self.vz_max * z.value
        self.show()
        self.initUI()

    def initUI(self):
        main_grid = QGridLayout()
        main_grid.setSpacing(5)
        self.setLayout(main_grid)
        self.setWindowTitle("Velocity")

         # set position label
        enter_pos = QLabel('Set max and actual velocity')  # above the slider
        main_grid.addWidget(enter_pos, 0, 0)

        # set xyz check boxes
        self.x_label = QLabel(f"V_X Max ({chr(956)}m/s)")
        main_grid.addWidget(self.x_label, 1, 0, 1, 1, Qt.AlignCenter)
        self.y_label = QLabel(f"V_Y Max ({chr(956)}m/s)")
        main_grid.addWidget(self.y_label, 2, 0, 1, 1, Qt.AlignCenter)
        self.z_label = QLabel(f"V_Z Max ({chr(956)}m/s)")
        main_grid.addWidget(self.z_label, 3, 0, 1, 1, Qt.AlignCenter)

        # set xyz spin boxes
        self.x_sb = QDoubleSpinBox()
        self.x_sb.setDecimals(2)
        self.x_sb.setValue(self.vx_max)
        self.x_sb.setEnabled(True)
        main_grid.addWidget(self.x_sb, 1, 1, Qt.AlignCenter)
        self.y_sb = QDoubleSpinBox()
        self.y_sb.setDecimals(2)
        self.y_sb.setValue(self.vy_max)
        self.y_sb.setEnabled(True)
        main_grid.addWidget(self.y_sb, 2, 1, Qt.AlignCenter)
        self.z_sb = QDoubleSpinBox()
        self.z_sb.setDecimals(2)
        self.z_sb.setValue(self.vz_max)
        self.z_sb.setEnabled(True)
        main_grid.addWidget(self.z_sb, 3, 1, Qt.AlignCenter)

        # set xyz check boxes
        self.x_label2 = QLabel(f"V_X after fractionize ({chr(956)}m/s)")
        main_grid.addWidget(self.x_label2, 1, 2, 1, 1, Qt.AlignCenter)
        self.y_label2 = QLabel(f"V_Y after fractionize ({chr(956)}m/s)")
        main_grid.addWidget(self.y_label2, 2, 2, 1, 1, Qt.AlignCenter)
        self.z_label2 = QLabel(f"V_Z after fractionize ({chr(956)}m/s)")
        main_grid.addWidget(self.z_label2, 3, 2, 1, 1, Qt.AlignCenter)

        # set xyz spin boxes
        self.x_sb2 = QDoubleSpinBox()
        self.x_sb2.setDecimals(2)
        self.x_sb2.setValue(self.vx_real)
        self.x_sb2.setEnabled(True)
        main_grid.addWidget(self.x_sb2, 1, 3, Qt.AlignCenter)
        self.y_sb2 = QDoubleSpinBox()
        self.y_sb2.setDecimals(2)
        self.y_sb2.setValue(self.vy_real)
        self.y_sb2.setEnabled(True)
        main_grid.addWidget(self.y_sb2, 2, 3, Qt.AlignCenter)
        self.z_sb2 = QDoubleSpinBox()
        self.z_sb2.setDecimals(2)
        self.z_sb2.setValue(self.vz_real)
        self.z_sb2.setEnabled(True)
        main_grid.addWidget(self.z_sb2, 3, 3, Qt.AlignCenter)

        self.submit_btn = QPushButton('Submit')
        self.submit_btn.clicked.connect(self.submit)
        main_grid.addWidget(self.submit_btn, 4, 3, Qt.AlignCenter)

    def submit(self):
        self.trans.Tango.LSX_SetVel(self.LSID, c_double(self.x_sb.value()), c_double(self.y_sb.value()), c_double(self.z_sb.value()), c_double(0))
        self.trans.Tango.LSX_SetVelFac(self.LSID, c_double(self.x_sb2.value()/self.x_sb.value()), c_double(self.y_sb2.value()/self.y_sb.value()), c_double(self.z_sb2.value()/self.z_sb.value()), c_double(0))
        self.close()

class FittingResult(QFrame):
    def __init__(self, fig):
        super().__init__()
        self.setGeometry(600, 250, 400, 200)
        self.fig = fig
        self.show()
        self.initUI()

    def initUI(self):
        main_grid = QGridLayout()
        main_grid.setSpacing(5)
        self.setLayout(main_grid)
        self.setWindowTitle("Fitting Result")

        self.canvas = FigureCanvas(self.fig)


class Bruker(QFrame):
    def __init__(self):
        super().__init__()
        self.setGeometry(600, 250, 600, 800)
        self.temp_based_pos = False
        self.temp_XPM = ""
        self.XPM = ""
        self.data = ""
        self.data_name = "Sample"
        self.temp_XPM2 = ""
        self.XPM2 = ""
        self.data_name2 = "Sample2"
        self.sample_pos = [[0, 0, 0]]
        self.background_pos = [[0, 0, 0]]
        self.show()
        self.initUI()

    def initUI(self):
        main_grid = QGridLayout()
        main_grid.setSpacing(5)
        self.setLayout(main_grid)
        self.setWindowTitle("Bruker")

         # set position
        background_pos = QLabel('Background position:')  # above the slider
        main_grid.addWidget(background_pos, 0, 0)

        self.background_mode = QComboBox()
        self.background_mode.addItem("Single position")
        self.background_mode.addItem("Temp-based positions")
        self.background_mode.currentIndexChanged.connect(self.background_mode_selection)
        main_grid.addWidget(self.background_mode, 1, 0, Qt.AlignCenter)

        self.background_pos_btn = QPushButton('Import background position from .txt')
        self.background_pos_btn.clicked.connect(self.open_background_pos)
        main_grid.addWidget(self.background_pos_btn, 1, 1, Qt.AlignCenter)

        self.save_background_btn = QPushButton('Save background position')
        self.save_background_btn.clicked.connect(self.save_background)
        main_grid.addWidget(self.save_background_btn, 1, 2, Qt.AlignCenter)

        self.x_label = QLabel(f"X ({chr(956)}m)")
        main_grid.addWidget(self.x_label, 2, 0, 1, 1, Qt.AlignCenter)
        self.y_label = QLabel(f"Y ({chr(956)}m)")
        main_grid.addWidget(self.y_label, 2, 1, 1, 1, Qt.AlignCenter)
        self.z_label = QLabel(f"Z ({chr(956)}m)")
        main_grid.addWidget(self.z_label, 2, 2, 1, 1, Qt.AlignCenter)

        self.x_sb = QDoubleSpinBox()
        self.x_sb.setDecimals(2)
        self.x_sb.setMinimum(-1e8)
        self.x_sb.setMaximum(1e8)
        self.x_sb.setValue(self.background_pos[0][0])
        self.x_sb.setEnabled(True)
        main_grid.addWidget(self.x_sb, 3, 0, Qt.AlignCenter)
        self.y_sb = QDoubleSpinBox()
        self.y_sb.setDecimals(2)
        self.y_sb.setMinimum(-1e8)
        self.y_sb.setMaximum(1e8)
        self.y_sb.setValue(self.background_pos[0][1])
        self.y_sb.setEnabled(True)
        main_grid.addWidget(self.y_sb, 3, 1, Qt.AlignCenter)
        self.z_sb = QDoubleSpinBox()
        self.z_sb.setDecimals(2)
        self.z_sb.setMinimum(-1e8)
        self.z_sb.setMaximum(1e8)
        self.z_sb.setValue(self.background_pos[0][2])
        self.z_sb.setEnabled(True)
        main_grid.addWidget(self.z_sb, 3, 2, Qt.AlignCenter)

        self.background_pos_path = QLabel('')  # above the slider
        main_grid.addWidget(self.background_pos_path, 4, 0, 1, 3)

        self.background_temp_pos_btn = QPushButton('Import temp-based background positions from .txt')
        self.background_temp_pos_btn.clicked.connect(self.open_background_temp_pos_file)
        self.background_temp_pos_btn.setEnabled(False)
        main_grid.addWidget(self.background_temp_pos_btn, 5, 1, Qt.AlignCenter)

         # set position
        sample_pos = QLabel('Sample position or positions:')
        main_grid.addWidget(sample_pos, 6, 0)

        self.position_mode = QComboBox()
        self.position_mode.addItem("Single position")
        self.position_mode.addItem("Multiple positions")
        self.position_mode.addItem("Temp-based positions")
        self.position_mode.currentIndexChanged.connect(self.sample_mode_selection)
        main_grid.addWidget(self.position_mode, 7, 0)

        self.sample_pos_btn2 = QPushButton('Import single sample position from .txt')
        self.sample_pos_btn2.clicked.connect(self.open_sample_pos)
        self.sample_pos_btn2.setEnabled(True)
        main_grid.addWidget(self.sample_pos_btn2, 7, 1, Qt.AlignCenter)

        self.save_sample_btn = QPushButton('Save sample position')
        self.save_sample_btn.clicked.connect(self.save_sample)
        self.save_sample_btn.setEnabled(True)
        main_grid.addWidget(self.save_sample_btn, 7, 2, Qt.AlignCenter)

        self.x_label2 = QLabel(f"X ({chr(956)}m)")
        main_grid.addWidget(self.x_label2, 8, 0, 1, 1, Qt.AlignCenter)
        self.y_label2 = QLabel(f"Y ({chr(956)}m)")
        main_grid.addWidget(self.y_label2, 8, 1, 1, 1, Qt.AlignCenter)
        self.z_label2 = QLabel(f"Z ({chr(956)}m)")
        main_grid.addWidget(self.z_label2, 8, 2, 1, 1, Qt.AlignCenter)

        self.x_sb2 = QDoubleSpinBox()
        self.x_sb2.setDecimals(2)
        self.x_sb2.setMinimum(-1e8)
        self.x_sb2.setMaximum(1e8)
        self.x_sb2.setValue(self.sample_pos[0][0])
        self.x_sb2.setEnabled(True)
        main_grid.addWidget(self.x_sb2, 9, 0, Qt.AlignCenter)
        self.y_sb2 = QDoubleSpinBox()
        self.y_sb2.setDecimals(2)
        self.y_sb2.setMinimum(-1e8)
        self.y_sb2.setMaximum(1e8)
        self.y_sb2.setValue(self.sample_pos[0][1])
        self.y_sb2.setEnabled(True)
        main_grid.addWidget(self.y_sb2, 9, 1, Qt.AlignCenter)
        self.z_sb2 = QDoubleSpinBox()
        self.z_sb2.setDecimals(2)
        self.z_sb2.setMinimum(-1e8)
        self.z_sb2.setMaximum(1e8)
        self.z_sb2.setValue(self.sample_pos[0][2])
        self.z_sb2.setEnabled(True)
        main_grid.addWidget(self.z_sb2, 9, 2, Qt.AlignCenter)

        self.sample_pos_path = QLabel('')  # above the slider
        main_grid.addWidget(self.sample_pos_path, 10, 0, 1, 3)

        sample_pos_hbox = QHBoxLayout()
        self.sample_pos_btn = QPushButton('Import multiple sample positions from .ompc')
        self.sample_pos_btn.clicked.connect(self.open_sample_pos_file)
        self.sample_pos_btn.setEnabled(False)
        sample_pos_hbox.addWidget(self.sample_pos_btn)

        self.sample_temp_pos_btn = QPushButton('Import temp-based sample positions from .txt')
        self.sample_temp_pos_btn.clicked.connect(self.open_sample_temp_pos_file)
        self.sample_temp_pos_btn.setEnabled(False)
        sample_pos_hbox.addWidget(self.sample_temp_pos_btn)
        main_grid.addLayout(sample_pos_hbox, 11, 0, 1, 3, Qt.AlignCenter)

         # set XPM
        XPM = QLabel('Choose the XPM file:')
        main_grid.addWidget(XPM, 12, 0, 1, 2, Qt.AlignLeft)

        self.XPM2_cb = QCheckBox("Second XPM file")
        self.XPM2_cb.toggled.connect(self.second_XPM)
        main_grid.addWidget(self.XPM2_cb, 12, 2, 1, 1, Qt.AlignCenter)

        self.XPM_path = QLabel('')
        main_grid.addWidget(self.XPM_path, 13, 0, 1, 2, Qt.AlignCenter)

        self.XPM_path2 = QLabel("")
        self.XPM_path2.setEnabled(False)
        main_grid.addWidget(self.XPM_path2, 13, 2, 1, 1, Qt.AlignCenter)

        self.XPM_btn = QPushButton('Select a file')
        self.XPM_btn.clicked.connect(lambda: self.open_XPM(1))
        main_grid.addWidget(self.XPM_btn, 14, 0, 1, 2, Qt.AlignCenter)

        self.XPM_btn2 = QPushButton('Select a file')
        self.XPM_btn2.clicked.connect(lambda: self.open_XPM(2))
        self.XPM_btn2.setEnabled(False)
        main_grid.addWidget(self.XPM_btn2, 14, 2, 1, 1, Qt.AlignCenter)

        # set data
        data = QLabel('Choose the directory to save data:')
        main_grid.addWidget(data, 15, 0)

        self.data_path = QLabel('')  # above the slider
        main_grid.addWidget(self.data_path, 16, 0, 1, 3)

        self.data_btn = QPushButton('Select a folder')
        self.data_btn.clicked.connect(self.save_data)
        main_grid.addWidget(self.data_btn, 17, 1, Qt.AlignCenter)

        data_name = QLabel('File name:')
        main_grid.addWidget(data_name, 18, 0, Qt.AlignCenter)

        self.data_name_text = QLineEdit("Sample")
        self.data_name_text.setFixedWidth(320)
        main_grid.addWidget(self.data_name_text, 19, 1, Qt.AlignCenter)

        self.data_name_text2 = QLineEdit("Sample2")
        self.data_name_text2.setFixedWidth(320)
        self.data_name_text2.setEnabled(False)
        main_grid.addWidget(self.data_name_text2, 19, 2, Qt.AlignCenter)

        self.save_btn = QPushButton('Save')
        self.save_btn.clicked.connect(self.save)
        main_grid.addWidget(self.save_btn, 20, 1, Qt.AlignRight)

        self.save_update_btn = QPushButton('Save and update')
        self.save_update_btn.clicked.connect(self.save_and_update)
        main_grid.addWidget(self.save_update_btn, 20, 2, Qt.AlignCenter)

    def background_mode_selection(self):
        if self.background_mode.currentText() == "Single position":
            self.background_pos_btn.setEnabled(True)
            self.save_background_btn.setEnabled(True)
            self.x_sb.setEnabled(True)
            self.y_sb.setEnabled(True)
            self.z_sb.setEnabled(True)
            self.background_temp_pos_btn.setEnabled(False)
            self.x_sb.setValue(0)
            self.y_sb.setValue(0)
            self.z_sb.setValue(0)
            self.background_pos_path.setText("")
        elif self.background_mode.currentText() == "Temp-based positions":
            self.background_pos_btn.setEnabled(False)
            self.save_background_btn.setEnabled(False)
            self.x_sb.setEnabled(False)
            self.y_sb.setEnabled(False)
            self.z_sb.setEnabled(False)
            self.background_temp_pos_btn.setEnabled(True)
            self.x_sb.setValue(0)
            self.y_sb.setValue(0)
            self.z_sb.setValue(0)
            self.background_pos_path.setText("")

    def sample_mode_selection(self):
        if self.position_mode.currentText() == "Single position":
            self.sample_pos_btn2.setEnabled(True)
            self.save_sample_btn.setEnabled(True)
            self.x_sb2.setEnabled(True)
            self.y_sb2.setEnabled(True)
            self.z_sb2.setEnabled(True)
            self.sample_pos_btn.setEnabled(False)
            self.sample_temp_pos_btn.setEnabled(False)
            self.x_sb2.setValue(0)
            self.y_sb2.setValue(0)
            self.z_sb2.setValue(0)
            self.sample_pos_path.setText("")
        elif self.position_mode.currentText() == "Multiple positions":
            self.sample_pos_btn2.setEnabled(False)
            self.save_sample_btn.setEnabled(False)
            self.x_sb2.setEnabled(False)
            self.y_sb2.setEnabled(False)
            self.z_sb2.setEnabled(False)
            self.sample_pos_btn.setEnabled(True)
            self.sample_temp_pos_btn.setEnabled(False)
            self.x_sb2.setValue(0)
            self.y_sb2.setValue(0)
            self.z_sb2.setValue(0)
            self.sample_pos_path.setText("")
        elif self.position_mode.currentText() == "Temp-based positions":
            self.sample_pos_btn2.setEnabled(False)
            self.save_sample_btn.setEnabled(False)
            self.x_sb2.setEnabled(False)
            self.y_sb2.setEnabled(False)
            self.z_sb2.setEnabled(False)
            self.sample_pos_btn.setEnabled(False)
            self.sample_temp_pos_btn.setEnabled(True)
            self.x_sb2.setValue(0)
            self.y_sb2.setValue(0)
            self.z_sb2.setValue(0)
            self.sample_pos_path.setText("")

    def getTdependentPosition(self, pospath, names, Trange=[], polyorder=2):

        """
        input a position vs Temperature coarse measurement (T(K), x(um), y(um), z(um))
        Fit the x,y,z positions and calcualte a finer position vs T data.
        Plot the result and save fitted result as txt with a '_fine' label
        Trange: if True, fit only over selected T range, e.g. Trange = [50,160]
        Note input Trange is from low to high
        """

        pos = pd.read_csv(pospath,sep='\t')

        posx = []
        posy = []
        posz = []

        moreT = np.arange(pos['T'].values[0],pos['T'].values[-1],-0.1)#/10
        # 0.1K step from highest to lowest temperature measured

        for i in range(len(names)):
            pos = pd.read_csv(pospath,sep='\t')
            name = names[i]
            fig,(ax1,ax2,ax3) = plt.subplots(1,3,constrained_layout=1,figsize=(9,4))
            ax1.scatter(pos['T'],pos[name + ' x(um)'],s=50,color='k')
            ax2.scatter(pos['T'],pos[name + ' y(um)'],s=50,color='k')
            ax3.scatter(pos['T'],pos[name + ' z(um)'],s=50,color='k')
            for ax,lb in zip([ax1,ax2,ax3],['x ($mu m$)','y ($mu m$)','z ($mu m$)']):
                ax.legend(['Data','Fit'], title=name)
                ax.set(xlabel='T (K)',ylabel=lb)

            # fit with linear or quadratic functions
            deg=polyorder  # or 2 for quadratic polynomial
            if len(Trange) > 0:
                Tmin = Trange[0]
                Tmax = Trange[1]
                pos.query('@Tmin < T < @Tmax',inplace=True)
            coeffx = P.polyfit(pos['T'],pos[name + ' x(um)'],deg=deg)
            coeffy = P.polyfit(pos['T'],pos[name + ' y(um)'],deg=deg)
            coeffz = P.polyfit(pos['T'],pos[name + ' z(um)'],deg=deg)
            posx.append(P.Polynomial(coeffx)(moreT))
            posy.append(P.Polynomial(coeffy)(moreT))
            posz.append(P.Polynomial(coeffz)(moreT))
            ax1.plot(moreT,posx[i],'b--')
            ax2.plot(moreT,posy[i],'b--')
            ax3.plot(moreT,posz[i],'b--')
        index = [moreT]
        for i in range(len(names)):
            index.append(posx[i])
            index.append(posy[i])
            index.append(posz[i])
        pos_fitted = np.array(index).T
        fname = pospath.replace('.txt','_fitted.txt')
        np.savetxt(fname,pos_fitted,fmt='%.3f',delimiter='\t')
        plt.show()
        return pos_fitted

    def open_background_pos(self):
        path = QFileDialog.getOpenFileName(self, "Select a file", r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Positions", "TXT Files (*.txt)")
        if path == "":
            return
        file = open(path[0], 'r')
        for line_index, line_str in enumerate(file):
            if line_index == 0:
                self.x_sb.setValue(float(self.split_string_to_data(line_str)))
            elif line_index == 1:
                self.y_sb.setValue(float(self.split_string_to_data(line_str)))
            else:
                self.z_sb.setValue(float(self.split_string_to_data(line_str)))
        file.close()

    def open_background_temp_pos_file(self):
        path = QFileDialog.getOpenFileName(self, "Select a file", r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Positions", "TXT Files (*.txt)")[0]
        if path == "":
            return
        try:
            pos_fitted = self.getTdependentPosition(path, ["sapphire"], [140, 250], 1)
        except:
            QMessageBox.warning(self, "TXT", "Your TXT file is corrupted and cannot be read correctly!")
            return
        reply = QMessageBox.question(self, "Fitting result", "Are you satisfied with the fitting result?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        background_pos = self.create_dict(pos_fitted)
        self.background_pos = background_pos
        self.x_sb.setValue(list(background_pos.values())[0][0][0])
        self.y_sb.setValue(list(background_pos.values())[0][0][1])
        self.z_sb.setValue(list(background_pos.values())[0][0][2])
        self.background_pos_path.setText(path)

    def open_sample_pos(self):
        path = QFileDialog.getOpenFileName(self, "Select a file", r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Positions", "TXT Files (*.txt)")
        file = open(path[0], 'r')
        for line_index, line_str in enumerate(file):
            if line_index == 0:
                self.x_sb2.setValue(float(self.split_string_to_data(line_str)))
            elif line_index == 1:
                self.y_sb2.setValue(float(self.split_string_to_data(line_str)))
            else:
                self.z_sb2.setValue(float(self.split_string_to_data(line_str)))
        file.close()

    def open_sample_pos_file(self):
        path = QFileDialog.getOpenFileName(self, "Select a file", r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Positions", "OMPC Files (*.ompc)")
        self.sample_pos_path.setText(path[0])
        sample_pos = self.read_pos(self.sample_pos_path.text())
        self.x_sb2.setValue(sample_pos[0][0])
        self.y_sb2.setValue(sample_pos[0][1])
        self.z_sb2.setValue(sample_pos[0][2])

    def open_sample_temp_pos_file(self):
        path = QFileDialog.getOpenFileName(self, "Select a file", r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Positions", "TXT Files (*.txt)")[0]
        if path == "":
            return
        try:
            pos_fitted = self.getTdependentPosition(path, ["250nm", "50nm"], [140, 250], polyorder=2)
        except:
            QMessageBox.warning(self, "TXT", "Your TXT file is corrupted and cannot be read correctly!")
            return
        reply = QMessageBox.question(self, "Fitting result", "Are you satisfied with the fitting result?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        sample_pos = self.create_dict(pos_fitted)
        self.sample_pos = sample_pos
        self.x_sb2.setValue(list(sample_pos.values())[0][0][0])
        self.y_sb2.setValue(list(sample_pos.values())[0][0][1])
        self.z_sb2.setValue(list(sample_pos.values())[0][0][2])
        self.sample_pos_path.setText(path)

    def open_XPM(self, num):
        path = QFileDialog.getOpenFileName(self, "Select a file", r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\XPM", "XPM Files (*.xpm)")[0]
        if num == 1:
            self.XPM_path.setText(os.path.basename(path))
            self.temp_XPM = path
        else:
            self.XPM_path2.setText(os.path.basename(path))
            self.temp_XPM2 = path

    def second_XPM(self):
        if self.XPM2_cb.isChecked():
            self.XPM_path2.setEnabled(True)
            self.XPM_btn2.setEnabled(True)
            self.data_name_text2.setEnabled(True)
        else:
            self.XPM_path2.setEnabled(False)
            self.XPM_btn2.setEnabled(False)
            self.data_name_text2.setEnabled(False)

    def save_data(self):
        path = QFileDialog.getExistingDirectory(self, "Select a folder", r"D:\Data")
        self.data_path.setText(path)

    def read_pos(self, path):
        if path == "":
            return []
        file = open(path, 'r')
        x = []
        y = []
        z = []
        try:
            for line_index, line_str in enumerate(file):
                if line_index % 47 == 8:
                    x.append(float(self.split_string_to_data(line_str)))
                elif line_index % 47 == 9:
                    y.append(float(self.split_string_to_data(line_str)))
                elif line_index % 47 == 10:
                    z.append(float(self.split_string_to_data(line_str)))
            file.close()
        except:
            QMessageBox.warning(self, "Sample", "Your OCMP file is corrupted and cannot be read correctly!")
        result = []
        for i in range(len(x)):
            result.append([x[i], y[i], z[i]])
        return result

    def create_dict(self, pos_fitted):
        dict = {}
        for T in range(len(pos_fitted)):
            line_list = pos_fitted[T]
            num = int((len(line_list) - 1) / 3)
            result = []
            for i in range(num):
                result.append([line_list[i*3+1], line_list[i*3+2], line_list[i*3+3]])
            dict[str(round(line_list[0], 1))] = result
        return dict

    def save_background(self):
        path = r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Positions\Background.txt"
        file = open(path, 'w')
        file.write(f"{self.x_sb.value()}\n")
        file.write(f"{self.y_sb.value()}\n")
        file.write(f"{self.z_sb.value()}")
        file.close()
        QMessageBox.information(self, "Save", "Background position is saved successfully!")

    def save_sample(self):
        path = r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Positions\Sample.txt"
        file = open(path, 'w')
        file.write(f"{self.x_sb2.value()}\n")
        file.write(f"{self.y_sb2.value()}\n")
        file.write(f"{self.z_sb2.value()}")
        file.close()
        QMessageBox.information(self, "Save", "Sample position is saved successfully!")

    def position_alert(self, background, sample):
        if self.temp_based_pos:
            for background2 in list(background.values()):
                for sample2 in list(sample.values()):
                    z_background = background2[0][2]
                    for s in sample2:
                        z_s = s[2]
                        if abs(z_background - z_s) > 10000:
                            return False
        else:
            z_background = background[0][2]
            for s in sample:
                z_s = s[2]
                if abs(z_background - z_s) > 10000:
                    return False
        return True

    def save(self):
        if (self.background_mode.currentText() == "Temp-based positions" and self.position_mode.currentText() != "Temp-based positions") or (self.background_mode.currentText() != "Temp-based positions" and self.position_mode.currentText() == "Temp-based positions"):
            QMessageBox.warning(self, "Temp-based Positions", "If you want to use temp-based positions, you have to set for both background and sample!")
            return
        if self.background_mode.currentText() == "Single position":
            self.background_pos = [[self.x_sb.value(), self.y_sb.value(), self.z_sb.value()]]
            self.temp_based_pos = False
        elif self.position_mode.currentText() == "Temp-based positions":
            self.temp_based_pos = True
        if self.position_mode.currentText() == "Multiple positions":
            self.sample_pos = self.read_pos(self.sample_pos_path.text())
            self.temp_based_pos = False
        elif self.position_mode.currentText() == "Single position":
            self.sample_pos = [[self.x_sb2.value(), self.y_sb2.value(), self.z_sb2.value()]]
            self.temp_based_pos = False
        elif self.position_mode.currentText() == "Temp-based positions":
            self.temp_based_pos = True
        control_widget.note_temp_sb.setEnabled(self.temp_based_pos)
        self.XPM = self.temp_XPM
        self.data = self.data_path.text()
        self.data_name = self.data_name_text.text()
        if self.XPM2_cb.isChecked():
            self.XPM2 = self.temp_XPM2
            self.data_name2 = self.data_name_text2.text()
        if self.position_alert(self.background_pos, self.sample_pos):
            self.close()
        else:
            QMessageBox.warning(self, "Translator motion in z direction", "The translator will be shifted by more than 10 mm vertically. Please make sure it does not collide with the lens below!")
        QMessageBox.information(self, "Save", "Directories are saved successfully!")

    def save_and_update(self):
        if (self.background_mode.currentText() == "Temp-based positions" and self.position_mode.currentText() != "Temp-based positions") or (self.background_mode.currentText() != "Temp-based positions" and self.position_mode.currentText() == "Temp-based positions"):
            QMessageBox.warning(self, "Temp-based Positions", "If you want to use temp-based positions, you have to set for both background and sample!")
            return
        commands = control_widget.commands.copy()
        text = control_widget.command_display.text()
        self.save()
        if len(commands) > 0:
            record = control_widget.recordCommandsList()
            success = control_widget.rewriteCommandsList(record)
            if not success:
                control_widget.commands = commands
                control_widget.command_display.setText(text)
                QMessageBox.warning(self, "Update failed", "Failed to update the worklist!")

    def split_string_to_data(self, str):
        str = str.replace("\t", "")
        str = str.replace("\n", "")
        str = str.replace("<fX>", "")
        str = str.replace("<fY>", "")
        str = str.replace("<fZ>", "")
        str = str.replace(r"</fX>", "")
        str = str.replace(r"</fY>", "")
        str = str.replace(r"</fZ>", "")
        return str

class ControlWidget(QFrame):
    '''Allows user to list commands and control the other widgets'''
    command_started = pyqtSignal()

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setMinimumWidth(450)
        self.error = False
        self.initUI()

    def initUI(self):

        global tran_widget
        global pol_new_widget
        global pol_thor_widget
        global ana_new_widget
        global ana_thor_widget
        global bruker_widget
        global combo_widget
        global keithley_widget
        global camera_widget

        # rotr_widget = Newport()
        # thor_widget = Thorlabs()
        pol_new_widget = Newport()
        pol_thor_widget = Thorlabs()
        ana_new_widget = Newport()
        ana_thor_widget = Thorlabs()
        tran_widget = Translator()
        bruker_widget = Bruker()
        keithley_widget = SourceMeter()
        camera_widget = Pylon(tran_widget)

        # create main grid to organize layout
        main_vbox = QVBoxLayout()
        main_vbox.setSpacing(10)
        self.setLayout(main_vbox)

        main_grid = QGridLayout()
        main_grid.setSpacing(10)

        #create the setting buttons for the four equipment
        self.polarizer_cb = QComboBox()
        self.polarizer_cb.addItem("Thorlabs")
        self.polarizer_cb.addItem("Newport")
        self.polarizer_cb.setFixedHeight(25)
        self.polarizer_cb.setFixedWidth(100)
        self.polarizer_setting_btn = QPushButton('Polarizer Setting')
        self.polarizer_setting_btn.setEnabled(True)
        self.polarizer_setting_btn.setFixedWidth(200)
        self.polarizer_setting_btn.setFixedHeight(50)
        self.polarizer_setting_btn.clicked.connect(self.show_polarizer)
        main_grid.addWidget(self.polarizer_cb, 0, 0, Qt.AlignCenter)
        main_grid.addWidget(self.polarizer_setting_btn, 1, 0, Qt.AlignCenter)
        self.analyzer_cb = QComboBox()
        self.analyzer_cb.addItem("Thorlabs")
        self.analyzer_cb.addItem("Newport")
        self.analyzer_cb.setFixedHeight(25)
        self.analyzer_cb.setFixedWidth(100)
        self.analyzer_setting_btn = QPushButton("Analyzer Setting")
        self.analyzer_setting_btn.setEnabled(True)
        self.analyzer_setting_btn.setFixedWidth(200)
        self.analyzer_setting_btn.setFixedHeight(50)
        self.analyzer_setting_btn.clicked.connect(self.show_analyzer)
        main_grid.addWidget(self.analyzer_cb, 0, 1, Qt.AlignCenter)
        main_grid.addWidget(self.analyzer_setting_btn, 1, 1, Qt.AlignCenter)
        self.keithley_setting_btn = QPushButton('Keithley Setting')
        self.keithley_setting_btn.setEnabled(True)
        self.keithley_setting_btn.setFixedWidth(200)
        self.keithley_setting_btn.setFixedHeight(50)
        self.keithley_setting_btn.clicked.connect(keithley_widget.show)
        main_grid.addWidget(self.keithley_setting_btn, 1, 2, Qt.AlignCenter)
        self.tango_setting_btn = QPushButton('Tango XYZ Setting')
        self.tango_setting_btn.setEnabled(True)
        self.tango_setting_btn.setFixedWidth(200)
        self.tango_setting_btn.setFixedHeight(50)
        self.tango_setting_btn.clicked.connect(tran_widget.show)
        main_grid.addWidget(self.tango_setting_btn, 2, 0, Qt.AlignCenter)
        self.bruker_setting_btn = QPushButton('Bruker Setting')
        self.bruker_setting_btn.setEnabled(True)
        self.bruker_setting_btn.setFixedWidth(200)
        self.bruker_setting_btn.setFixedHeight(50)
        self.bruker_setting_btn.clicked.connect(bruker_widget.show)
        main_grid.addWidget(self.bruker_setting_btn, 2, 1, Qt.AlignCenter)
        self.camera_control_btn = QPushButton('Camera Control')
        self.camera_control_btn.setEnabled(True)
        self.camera_control_btn.setFixedWidth(200)
        self.camera_control_btn.setFixedHeight(50)
        self.camera_control_btn.clicked.connect(camera_widget.show)
        main_grid.addWidget(self.camera_control_btn, 2, 2, Qt.AlignCenter)
        main_vbox.addLayout(main_grid)

        # create list of commands
        self.commands = []

        # create tab screen
        self.tabs = QTabWidget()
        self.tabs.setMaximumHeight(500)
        main_vbox.addWidget(self.tabs)

        # create display for list of commands
        commands_scroll = QScrollArea()
        commands_scroll.setWidgetResizable(True)
        commands_scroll.setAlignment(Qt.AlignTop)
        self.command_display = QLabel('<b>Commands:</b><ol style="margin:0px;"></ol>')
        self.command_display.setAlignment(Qt.AlignTop)
        self.command_display.setWordWrap(True)
        commands_scroll.setWidget(self.command_display)
        main_vbox.addWidget(commands_scroll)

        # initalize all tabs
        self.initTempTab()
        self.initRotatorTab()
        self.initThorTab()
        self.initTranTab()
        self.initBrukerTab()
        self.initComboTab()
        self.initTempSweepTab()
        self.initVISweepTab()

        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        main_vbox.addWidget(self.progressBar)
        self.timer = QBasicTimer()

        # make hbox layout for buttons to run all commands, remove last command, and clear all
        commands_hb = QHBoxLayout()

        # add button to run all commands
        run_commands_btn = QPushButton('Run Commands')
        # run_commands_btn.setFixedWidth(90)
        run_commands_btn.clicked.connect(self.runCommands)
        commands_hb.addWidget(run_commands_btn)

        # add button to remove last
        remove_last_btn = QPushButton('Remove Last')
        # remove_last_btn.setFixedWidth(90)
        remove_last_btn.clicked.connect(self.removeLast)
        commands_hb.addWidget(remove_last_btn)

        # add button to clear all
        clear_all_btn = QPushButton('Clear All')
        # clear_all_btn.setFixedWidth(90)
        clear_all_btn.clicked.connect(self.clearAll)
        commands_hb.addWidget(clear_all_btn)

        # allow user to save commands list
        save_commands_btn = QPushButton('Save List')
        # save_commands_btn.setFixedWidth(70)
        save_commands_btn.clicked.connect(self.saveCommandsList)
        commands_hb.addWidget(save_commands_btn)

        # allow user to load commands list
        load_commands_btn = QPushButton('Load List')
        # load_commands_btn.setFixedWidth(70)
        load_commands_btn.clicked.connect(self.loadCommandsList)
        commands_hb.addWidget(load_commands_btn)

        # allow user to stop the command list
        stop_btn = QPushButton('Stop')
        # stop_btn.setFixedWidth(70)
        stop_btn.clicked.connect(self.stop_commands)
        commands_hb.addWidget(stop_btn)

        # allow user to log the command list
        self.log_cb = QCheckBox("Log")
        commands_hb.addWidget(self.log_cb)

        # create list of buttons to disable when in the middle of running commands
        self.buttons = [run_commands_btn, remove_last_btn, clear_all_btn, self.log_cb]

        commands_hb.addStretch()
        main_vbox.addLayout(commands_hb)

        self.reminder = False

    def show_polarizer(self):
        if self.polarizer_cb.currentText() == "Newport":
            pol_new_widget.show()
        else:
            pol_thor_widget.show()

    def show_analyzer(self):
        if self.analyzer_cb.currentText() == "Newport":
            ana_new_widget.show()
        else:
            ana_thor_widget.show()

    def saveCommandsList(self):
        path, ok = QFileDialog.getSaveFileName(self, "Select a file", r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Worklist", "TXT Files (*.txt)")
        if ok:
            f = open(path, 'w+')

            commands = self.command_display.text()
            commands = commands.lstrip('<b>Commands:</b><ol style="margin:0px;">').rstrip('</ol>')
            commands = commands.replace('<li>', '')
            commands = commands.replace(f"{chr(956)}m", '')

            commands = commands.split('</li>')
            commands[-1] = commands[-1].replace('</li', '')
            f.write('Commands:\n')

            for i in range(len(commands)):
                f.write('{}. {}\n'.format(i + 1, commands[i]))

            f.close()

    def loadCommandsList(self):
        file_info = QFileDialog.getOpenFileName(self, 'Open File', r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\instruments\VERTEX_80v\Worklist")
        filename = file_info[0]
        f = open(filename, 'r+')

        for line in f.readlines():
            period_ind = line.find('.')
            command = line[period_ind + 2:]

            colon_ind = command.find(':')
            command_type = command[:colon_ind]
            command = command[colon_ind + 2:]

            vals = command.split(', ')

            if command_type == 'Polarizer':
                rotr = vals[0]
                angle = float(vals[1][:-3])
                pause = int(vals[2].rstrip()[:-1])

                self.addPolarizerCommand(angle, pause)

            elif command_type == 'Analyzer':
                rotr = vals[0]
                angle = float(vals[1][:-3])
                pause = int(vals[2].rstrip()[:-1])

                self.addAnalyzerCommand(angle, pause)

            elif command_type == 'Set Temperature':
                temp = float(vals[0][:-1])
                un = float(vals[1][:-1])
                duration = int(vals[2][:-1])
                pause = int(vals[3].rstrip()[:-1])
                if len(vals) >= 5:
                    auto_xyz = bool(vals[4])
                    illumination = int(vals[5].rstrip())

                self.temp_pause_sb.setValue(pause)
                if len(vals) < 5:
                    self.addTempCommand(temp, un, duration)
                else:
                    self.addTempCommand(temp, un, duration, auto_xyz, illumination)

            elif command_type[:10] == 'Translator':
                x = float(vals[0])
                y = float(vals[1])
                z = float(vals[2])
                auto_xyz = (vals[3] == "True") or (vals[3] == "ReferencePointTrue")
                pause = int(vals[4].rstrip()[:-1])
                self.tran_pause_sb.setValue(pause)
                if command_type[12:15] == 'Abs':
                    if len(vals) >= 6:
                        if vals[5][0:6] == "sample":
                            num = int(vals[5][6:7])
                            self.addBrukerTranCommand(bruker_widget.sample_pos, num-1, auto_xyz, self.tran_pause_sb.value(), self.note_temp_sb.value())
                        elif vals[5][0:10] == "background":
                            self.addBrukerTranCommand(bruker_widget.background_pos, -1, auto_xyz, self.tran_pause_sb.value(), self.note_temp_sb.value())
                        elif vals[5][0:9] == "reference":
                            self.addPylonTranCommand(camera_widget.x_reference, camera_widget.y_reference, camera_widget.z_reference, auto_xyz, self.tran_pause_sb.value())
                    else:
                        self.addTranCommand1(x, y, z, False, pause)
                if command_type[12:15] == 'Rel':
                    self.addTranCommand2(x, y, z, False, pause)

            elif command_type == 'Bruker':
                if vals[0] == "Scan background":
                    XPM1 = vals[1] == "XPM1"
                    pause = int(vals[2].rstrip()[:-1])
                    self.bruker_pause_sb.setValue(pause)
                    self.addBrukerCommand(1, XPM1, pause)
                elif vals[0] == "Scan sample":
                    XPM1 = vals[1] == "XPM1"
                    pause = int(vals[2].rstrip()[:-1])
                    self.bruker_pause_sb.setValue(pause)
                    self.addBrukerCommand(2, XPM1, pause)
                elif vals[0] == "Save result as txt and png":
                    self.addBrukerSaveCommand(self.XPM1_rb.isChecked(), self.add_macro.currentText(), (self.title_lbl.text()+self.title_text.text()), self.vmin.value(), self.vmax.value(), self.raw_cb.isChecked(), self.csv_cb.isChecked(), self.bruker_freq_sb.value(), self.bruker_freq_cb.isChecked())

            elif command_type == "Keithley":
                if vals[0] == "current ramp":
                    mode = "Current"
                elif vals[0] == "voltage ramp":
                    mode = "Voltage"
                vi = float(vals[1][:-1])
                ramp_speed = int(vals[2][:-7])
                step = float(vals[3][:-1])
                VI_pause = int(vals[4].rstrip()[:-1])
                self.addKeithleyCommand(mode, ramp_speed, step, vi, VI_pause)

        f.close()

    def recordCommandsList(self):
        record = ""
        commands = self.command_display.text()
        commands = commands.lstrip('<b>Commands:</b><ol style="margin:0px;">').rstrip('</ol>')
        commands = commands.replace('<li>', '')
        commands = commands.replace(f"{chr(956)}m", '')

        commands = commands.split('</li>')
        commands[-1] = commands[-1].replace('</li', '')
        record += 'Commands:\n'

        for i in range(len(commands)):
            record += '{}. {}\n'.format(i + 1, commands[i])

        return record

    def rewriteCommandsList(self, record):
        self.clearAll()
        for line in record.split("\n"):
            period_ind = line.find('.')
            command = line[period_ind + 2:]

            colon_ind = command.find(':')
            command_type = command[:colon_ind]
            command = command[colon_ind + 2:]

            vals = command.split(', ')

            if command_type == 'Polarizer':
                rotr = vals[0]
                angle = float(vals[1][:-3])
                pause = int(vals[2].rstrip()[:-1])

                self.addPolarizerCommand(angle, pause)

            elif command_type == 'Analyzer':
                rotr = vals[0]
                angle = float(vals[1][:-3])
                pause = int(vals[2].rstrip()[:-1])

                self.addAnalyzerCommand(angle, pause)

            elif command_type == 'Set Temperature':
                temp = float(vals[0][:-1])
                un = float(vals[1][:-1])
                duration = int(vals[2][:-1])
                pause = int(vals[3].rstrip()[:-1])
                if len(vals) >= 5:
                    auto_xyz = bool(vals[4])
                    illumination = int(vals[5].rstrip())

                self.temp_pause_sb.setValue(pause)
                if len(vals) < 5:
                    self.addTempCommand(temp, un, duration)
                else:
                    self.addTempCommand(temp, un, duration, auto_xyz, illumination)

            elif command_type[:10] == 'Translator':
                x = float(vals[0])
                y = float(vals[1])
                z = float(vals[2])
                auto_xyz = (vals[3] == "True") or (vals[3] == "ReferencePointTrue")
                pause = int(vals[4].rstrip()[:-1])
                self.tran_pause_sb.setValue(pause)
                if command_type[12:15] == 'Abs':
                    if len(vals) >= 6:
                        if vals[5][0:6] == "sample":
                            num = int(vals[5][6:7])
                            self.addBrukerTranCommand(bruker_widget.sample_pos, num-1, auto_xyz, self.tran_pause_sb.value(), self.note_temp_sb.value())
                        elif vals[5][0:10] == "background":
                            self.addBrukerTranCommand(bruker_widget.background_pos, -1, auto_xyz, self.tran_pause_sb.value(), self.note_temp_sb.value())
                        elif vals[5][0:9] == "reference":
                            self.addPylonTranCommand(camera_widget.x_reference, camera_widget.y_reference, camera_widget.z_reference, auto_xyz, self.tran_pause_sb.value())
                    else:
                        self.addTranCommand1(x, y, z, False, pause)
                if command_type[12:15] == 'Rel':
                    self.addTranCommand2(x, y, z, False, pause)

            elif command_type == 'Bruker':
                if vals[0] == "Scan background":
                    XPM1 = vals[1] == "XPM1"
                    pause = int(vals[2].rstrip()[:-1])
                    self.bruker_pause_sb.setValue(pause)
                    self.addBrukerCommand(1, XPM1, pause)
                elif vals[0] == "Scan sample":
                    XPM1 = vals[1] == "XPM1"
                    pause = int(vals[2].rstrip()[:-1])
                    self.bruker_pause_sb.setValue(pause)
                    self.addBrukerCommand(2, XPM1, pause)
                elif vals[0] == "Save result as txt and png":
                    self.addBrukerSaveCommand(self.XPM1_rb.isChecked(), self.add_macro.currentText(), (self.title_lbl.text()+self.title_text.text()), self.vmin.value(), self.vmax.value(), self.raw_cb.isChecked(), self.csv_cb.isChecked(), self.bruker_freq_sb.value(), self.bruker_freq_cb.isChecked())

            elif command_type == "Keithley":
                if vals[0] == "current ramp":
                    mode = "Current"
                elif vals[0] == "voltage ramp":
                    mode = "Voltage"
                vi = float(vals[1][:-1])
                ramp_speed = int(vals[2][:-7])
                step = float(vals[3][:-1])
                VI_pause = int(vals[4].rstrip()[:-1])
                self.addKeithleyCommand(mode, ramp_speed, step, vi, VI_pause)

            if self.error:
                self.error = False
                return False

        return True

    def initRotatorTab(self):
        # create tab
        rotator_tab = QWidget()

        # create main hbox and main vbox to organize layout
        main_hbox = QHBoxLayout()
        main_hbox.setSpacing(10)
        rotator_tab.setLayout(main_hbox)

        main_vbox = QVBoxLayout()

        # absolute position label
        pos = QLabel('Absolute Position (deg)')

        # absolute position spin box
        abs_pos_sb = QDoubleSpinBox()
        abs_pos_sb.setDecimals(4)
        abs_pos_sb.setRange(0, 359)

        pos_hb = QHBoxLayout()
        pos_hb.addWidget(pos)
        pos_hb.addWidget(abs_pos_sb)
        main_vbox.addLayout(pos_hb)

        # create button to add command
        add_command_btn = QPushButton('Add Command')
        add_command_btn.setFixedWidth(150)
        add_command_btn.clicked.connect(lambda: self.addPolarizerCommand(abs_pos_sb.value(), self.pause_sb.value()))
        main_vbox.addWidget(add_command_btn, Qt.AlignLeft)

        or_lbl = QLabel('<b>OR</b>')
        main_vbox.addWidget(or_lbl, Qt.AlignCenter)

        # start position label
        start_pos = QLabel('Start Position (deg)')
        # start position spin box
        self.start_pos_sb = QDoubleSpinBox()
        self.start_pos_sb.setDecimals(4)
        self.start_pos_sb.setRange(0, 359)
        # start position hbox
        start_pos_hb = QHBoxLayout()
        start_pos_hb.addWidget(start_pos)
        start_pos_hb.addWidget(self.start_pos_sb)
        main_vbox.addLayout(start_pos_hb)

        # stop position label
        stop_pos = QLabel('Stop Position (deg)')
        # stop position spin box
        self.stop_pos_sb = QDoubleSpinBox()
        self.stop_pos_sb.setDecimals(4)
        self.stop_pos_sb.setRange(0, 359)
        # stop position hbox
        stop_pos_hb = QHBoxLayout()
        stop_pos_hb.addWidget(stop_pos)
        stop_pos_hb.addWidget(self.stop_pos_sb)
        main_vbox.addLayout(stop_pos_hb)

        # step label
        step = QLabel('Step (deg)')
        # step spin box
        self.step_sb = QDoubleSpinBox()
        self.step_sb.setDecimals(4)
        self.step_sb.setRange(0, 359)
        # start position hbox
        step_hb = QHBoxLayout()
        step_hb.addWidget(step)
        step_hb.addWidget(self.step_sb)
        main_vbox.addLayout(step_hb)

        # pause label
        pause = QLabel('Pause (sec)')
        # pause line edit
        self.pause_sb = QSpinBox()
        self.pause_sb.setMinimum(0)
        self.pause_sb.setFixedWidth(50)
        self.pause_sb.setAlignment(Qt.AlignTop)
        right_vbox = QVBoxLayout()
        right_vbox.addWidget(pause, Qt.AlignHCenter)
        right_vbox.addWidget(self.pause_sb, Qt.AlignHCenter)
        right_vbox.addStretch()

        add_commands_btn = QPushButton('Add Commands')
        add_commands_btn.setFixedWidth(150)
        main_vbox.addWidget(add_commands_btn, Qt.AlignLeft)
        add_commands_btn.clicked.connect(self.addPolarizerCommands)

        main_vbox.addStretch()

        main_hbox.addLayout(main_vbox)
        main_hbox.addLayout(right_vbox, Qt.AlignCenter)

        self.tabs.addTab(rotator_tab, 'Polarizer')

    def initThorTab(self):
        # create tab
        thor_tab = QWidget()

        # create main hbox and main vbox to organize layout
        main_hbox = QHBoxLayout()
        main_hbox.setSpacing(10)
        thor_tab.setLayout(main_hbox)

        main_vbox = QVBoxLayout()

        # absolute position label
        pos = QLabel('Absolute Position (deg)')

        # absolute position spin box
        abs_pos_sb = QDoubleSpinBox()
        abs_pos_sb.setDecimals(4)
        abs_pos_sb.setRange(0, 360)

        pos_hb = QHBoxLayout()
        pos_hb.addWidget(pos)
        pos_hb.addWidget(abs_pos_sb)
        main_vbox.addLayout(pos_hb)

        # create button to add command
        add_command_btn = QPushButton('Add Command')
        add_command_btn.setFixedWidth(150)
        add_command_btn.clicked.connect(lambda: self.addAnalyzerCommand(abs_pos_sb.value(), self.pause_sb.value()))
        main_vbox.addWidget(add_command_btn, Qt.AlignLeft)

        or_lbl = QLabel('<b>OR</b>')
        main_vbox.addWidget(or_lbl, Qt.AlignCenter)

        # start position label
        start_pos = QLabel('Start Position (deg)')
        # start position spin box
        self.start_pos_sb2 = QDoubleSpinBox()
        self.start_pos_sb2.setDecimals(4)
        self.start_pos_sb2.setRange(0, 360)
        # start position hbox
        start_pos_hb = QHBoxLayout()
        start_pos_hb.addWidget(start_pos)
        start_pos_hb.addWidget(self.start_pos_sb2)
        main_vbox.addLayout(start_pos_hb)

        # stop position label
        stop_pos = QLabel('Stop Position (deg)')
        # stop position spin box
        self.stop_pos_sb2 = QDoubleSpinBox()
        self.stop_pos_sb2.setDecimals(4)
        self.stop_pos_sb2.setRange(0, 360)
        # stop position hbox
        stop_pos_hb = QHBoxLayout()
        stop_pos_hb.addWidget(stop_pos)
        stop_pos_hb.addWidget(self.stop_pos_sb2)
        main_vbox.addLayout(stop_pos_hb)

        # step label
        step = QLabel('Step (deg)')
        # step spin box
        self.step_sb2 = QDoubleSpinBox()
        self.step_sb2.setDecimals(4)
        self.step_sb2.setRange(0, 360)
        # start position hbox
        step_hb = QHBoxLayout()
        step_hb.addWidget(step)
        step_hb.addWidget(self.step_sb2)
        main_vbox.addLayout(step_hb)

        # pause label
        pause = QLabel('Pause (sec)')
        # pause line edit
        self.pause_sb2 = QSpinBox()
        self.pause_sb2.setMinimum(0)
        self.pause_sb2.setFixedWidth(50)
        self.pause_sb2.setAlignment(Qt.AlignTop)
        right_vbox = QVBoxLayout()
        right_vbox.addWidget(pause, Qt.AlignHCenter)
        right_vbox.addWidget(self.pause_sb2, Qt.AlignHCenter)
        right_vbox.addStretch()

        add_commands_btn = QPushButton('Add Commands')
        add_commands_btn.setFixedWidth(150)
        main_vbox.addWidget(add_commands_btn, Qt.AlignLeft)
        add_commands_btn.clicked.connect(self.addAnalyzerCommands)

        main_vbox.addStretch()

        main_hbox.addLayout(main_vbox)
        main_hbox.addLayout(right_vbox, Qt.AlignCenter)

        self.tabs.addTab(thor_tab, 'Analyzer')

    def initTempTab(self):
        # create tab
        temp_tab = QWidget()

        # create main vbox to organize layout
        main_vbox = QVBoxLayout()
        main_vbox.setSpacing(10)
        temp_tab.setLayout(main_vbox)

        # give a note to the user that this will not cool down or warm up the cryostat automatically
        note = QLabel('Note: This command will not cool down or warm up the mercury ' +
                      'automatically. It is recommended to cool down the mercury to the ' +
                      'desired temperature before running all commands.')
        note.setWordWrap(True)
        main_vbox.addWidget(note)

        # allow user to input a temperature for the setpoint
        temp_lbl = QLabel('Temperature (K)')
        self.temp_sb = QDoubleSpinBox()
        self.temp_sb.setRange(4, 350)
        self.temp_sb.setDecimals(1)
        self.temp_sb.setValue(270.0)
        self.temp_sb.setToolTip('Temperature Set Point')

        temp_hb = QHBoxLayout()
        temp_hb.addWidget(temp_lbl)
        temp_hb.addWidget(self.temp_sb)
        main_vbox.addLayout(temp_hb)

        un_lbl = QLabel('Accepetable uncertainty (K)')
        un_sb = QDoubleSpinBox()
        un_sb.setDecimals(2)
        un_sb.setValue(1.0)
        #un_sb.setToolTip('Temperature Set Point Uncertainty')

        un_hb = QHBoxLayout()
        un_hb.addWidget(un_lbl)
        un_hb.addWidget(un_sb)
        main_vbox.addLayout(un_hb)

        duration_hb = QHBoxLayout()

        duration_lbl = QLabel('Stability duration (sec)')

        duration_sb = QSpinBox()
        duration_sb.setMinimum(0)
        duration_sb.setMaximum(180)
        duration_sb.setValue(90)

        duration_hb.addWidget(duration_lbl)
        duration_hb.addWidget(duration_sb)
        main_vbox.addLayout(duration_hb)

        pause_lbl = QLabel('Pause (sec)')

        self.temp_pause_sb = QSpinBox()
        self.temp_pause_sb.setMinimum(0)
        self.temp_pause_sb.setMaximum(600)
        self.temp_pause_sb.setFixedWidth(80)

        pause_hb = QHBoxLayout()
        pause_hb.addWidget(pause_lbl)
        pause_hb.addWidget(self.temp_pause_sb)
        main_vbox.addLayout(pause_hb)

        # create button to add command
        add_command_btn = QPushButton('Add Command')
        add_command_btn.setFixedWidth(150)
        add_command_btn.clicked.connect(lambda: self.addTempCommand(self.temp_sb.value(), un_sb.value(), duration_sb.value()))
        main_vbox.addWidget(add_command_btn, Qt.AlignLeft)

        save_hb = QHBoxLayout()
        self.save_ch = QCheckBox("Save temperature logging")
        self.save_ch.clicked.connect(self.check_temp_save)
        self.select_path_btn = QPushButton("Claim saving path and file name")
        self.select_path_btn.setEnabled(False)
        self.select_path_btn.clicked.connect(self.load_temp_save_path)
        save_hb.addWidget(self.save_ch)
        save_hb.addWidget(self.select_path_btn)
        main_vbox.addLayout(save_hb)

        self.path_indicator = QLabel("")
        main_vbox.addWidget(self.path_indicator)

        main_vbox.addStretch()

        self.tabs.addTab(temp_tab, 'Temperature Set Point')

    def check_temp_save(self):
        if self.save_ch.isChecked():
            self.select_path_btn.setEnabled(True)
        else:
            self.select_path_btn.setEnabled(False)
            self.path_indicator.setText("")

    def load_temp_save_path(self):
        path = QFileDialog.getSaveFileName(self, "Select a file", r"{}".format(cwd_path), "TXT Files (*.txt)")[0]
        self.path_indicator.setText(path)

    def initTranTab(self):
        tran_tab = QWidget()

        # create main vbox to organize layout
        main_vbox = QGridLayout()
        main_vbox.setSpacing(10)
        tran_tab.setLayout(main_vbox)

        note0 = QLabel('Please input the absolute or relative position in Tango Setting to add the first two commands!')
        main_vbox.addWidget(note0, 0, 0, 1, 2, Qt.AlignCenter)

        add_command1_btn = QPushButton('Move to absolute position')
        # add_command1_btn.setFixedWidth(150)
        add_command1_btn.setFixedHeight(50)
        add_command1_btn.clicked.connect(lambda: self.addTranCommand1(tran_widget.x_sb.value(), tran_widget.y_sb.value(), tran_widget.z_sb.value(), False, self.tran_pause_sb.value()))
        main_vbox.addWidget(add_command1_btn, 2, 0, Qt.AlignCenter)

        add_command2_btn = QPushButton('Move to relative position')
        # add_command2_btn.setFixedWidth(150)
        add_command2_btn.setFixedHeight(50)
        add_command2_btn.clicked.connect(lambda: self.addTranCommand2(tran_widget.x_sb.value(), tran_widget.y_sb.value(), tran_widget.z_sb.value(), False, self.tran_pause_sb.value()))
        main_vbox.addWidget(add_command2_btn, 2, 1, Qt.AlignCenter)

        self.tran_auto_xyz_cb = QCheckBox("Use reference point offset")
        self.tran_auto_xyz_cb.setStyleSheet("QCheckBox::indicator:checked"
                                "{"
                                "background-color : red;"
                                "}")
        main_vbox.addWidget(self.tran_auto_xyz_cb, 5, 0, 1, 1, Qt.AlignCenter)

        add_command3_btn = QPushButton('Move to Background')
        # add_command3_btn.setFixedWidth(150)
        add_command3_btn.setFixedHeight(50)
        add_command3_btn.clicked.connect(lambda: self.addBrukerTranCommand(bruker_widget.background_pos, -1, self.tran_auto_xyz_cb.isChecked(), self.tran_pause_sb.value(), self.note_temp_sb.value()))
        main_vbox.addWidget(add_command3_btn, 4, 0, Qt.AlignCenter)

        note_temp = QLabel("Temp")
        self.note_temp_sb = QDoubleSpinBox()
        self.note_temp_sb.setDecimals(1)
        self.note_temp_sb.setMinimum(50)
        self.note_temp_sb.setMaximum(350)
        self.note_temp_sb.setValue(295)
        self.note_temp_sb.setFixedWidth(60)
        self.note_temp_sb.setEnabled(False)
        self.note_temp_sb.editingFinished.connect(lambda: self.temp_sb.setValue(self.note_temp_sb.value()))
        self.temp_sb.editingFinished.connect(lambda: self.note_temp_sb.setValue(self.temp_sb.value()))
        note_K = QLabel("K")

        temp_hbox = QHBoxLayout()
        temp_hbox.addWidget(note_temp)
        temp_hbox.addWidget(self.note_temp_sb)
        temp_hbox.addWidget(note_K)
        main_vbox.addLayout(temp_hbox, 3, 0, Qt.AlignCenter)

        note4 = QLabel('Sample')
        note4.setWordWrap(True)

        self.note4_sb = QSpinBox()
        self.note4_sb.setValue(1)
        self.note4_sb.setEnabled(True)
        self.note4_sb.setMinimum(1)
        self.note4_sb.setMaximum(100)

        sample_vb = QHBoxLayout()
        sample_vb.addWidget(note4)
        sample_vb.addWidget(self.note4_sb)
        main_vbox.addLayout(sample_vb, 3, 1, Qt.AlignCenter)

        add_command4_btn = QPushButton('Move to sample')
        # add_command4_btn.setFixedWidth(150)
        add_command4_btn.setFixedHeight(50)
        add_command4_btn.clicked.connect(lambda: self.addBrukerTranCommand(bruker_widget.sample_pos, int(self.note4_sb.value()-1), self.tran_auto_xyz_cb.isChecked(), self.tran_pause_sb.value(), self.note_temp_sb.value()))
        main_vbox.addWidget(add_command4_btn, 4, 1, Qt.AlignCenter)

        add_command5_btn = QPushButton('Move to reference')
        # add_command4_btn.setFixedWidth(150)
        add_command5_btn.setFixedHeight(50)
        add_command5_btn.clicked.connect(lambda: self.addPylonTranCommand(camera_widget.x_reference, camera_widget.y_reference, camera_widget.z_reference, self.tran_auto_xyz_cb.isChecked(), self.tran_pause_sb.value()))
        main_vbox.addWidget(add_command5_btn, 4, 2, Qt.AlignCenter)

        pause_lbl = QLabel('Pause (sec)')

        self.tran_pause_sb = QSpinBox()
        self.tran_pause_sb.setMinimum(0)
        self.tran_pause_sb.setFixedWidth(50)

        pause_hb = QHBoxLayout()
        pause_hb.addWidget(pause_lbl)
        pause_hb.addWidget(self.tran_pause_sb)
        main_vbox.addLayout(pause_hb, 5, 1, 1, 1, Qt.AlignCenter)

        self.tabs.addTab(tran_tab, 'Tango XYZ Translator')

    def initBrukerTab(self):
        bruker_tab = QWidget()

        # create main vbox to organize layout
        main_vbox = QGridLayout()
        main_vbox.setSpacing(10)
        bruker_tab.setLayout(main_vbox)

        note0 = QLabel('Please make sure the correct directories all have ' +
                      'been declared via Bruker Setting!')
        note0.setFixedHeight(50)
        main_vbox.addWidget(note0, 0, 0, 1, 2, Qt.AlignCenter)

        scan_hbox = QHBoxLayout()

        add_command_btn = QPushButton('Scan background')
        add_command_btn.setFixedWidth(150)
        add_command_btn.setFixedHeight(50)
        add_command_btn.clicked.connect(lambda: self.addBrukerCommand(1, self.XPM1_rb.isChecked(), self.bruker_pause_sb.value()))

        add_command2_btn = QPushButton('Scan sample')
        add_command2_btn.setFixedWidth(150)
        add_command2_btn.setFixedHeight(50)
        add_command2_btn.clicked.connect(lambda: self.addBrukerCommand(2, self.XPM1_rb.isChecked(), self.bruker_pause_sb.value()))

        XPM_vbox = QVBoxLayout()
        self.XPM1_rb = QRadioButton("Use XPM1")
        self.XPM1_rb.setChecked(True)
        self.XPM2_rb = QRadioButton("Use XPM2")
        XPM_vbox.addWidget(self.XPM1_rb)
        XPM_vbox.addWidget(self.XPM2_rb)

        scan_hbox.addWidget(add_command_btn)
        scan_hbox.addWidget(add_command2_btn)
        scan_hbox.addLayout(XPM_vbox)
        main_vbox.addLayout(scan_hbox, 1, 0, 1, 2, Qt.AlignCenter)

        save_hbox = QHBoxLayout()

        self.add_macro = QComboBox()
        self.add_macro.addItem("REFL")
        self.add_macro.addItems(["TR"])
        self.add_macro.currentIndexChanged.connect(self.changeText)
        save_hbox.addWidget(self.add_macro)
        #main_vbox.addWidget(self.add_macro, 2, 0, 1, 1, Qt.AlignRight)

        add_command3_btn = QPushButton('Save result as .txt and .png')
        # add_command3_btn.setFixedWidth(150)
        add_command3_btn.setFixedHeight(50)
        add_command3_btn.clicked.connect(lambda: self.addBrukerSaveCommand(self.XPM1_rb.isChecked(), self.add_macro.currentText(), (self.title_lbl.text() + self.title_text.text()), self.vmin.value(), self.vmax.value(), self.raw_cb.isChecked(), self.csv_cb.isChecked(), self.bruker_freq_sb.value(), self.bruker_freq_cb.isChecked()))
        save_hbox.addWidget(add_command3_btn)
        #main_vbox.addWidget(add_command3_btn, 2, 1, 1, 1, Qt.AlignLeft)

        check_vbox = QVBoxLayout()
        self.raw_cb = QCheckBox("Save raw spectra")
        self.raw_cb.setChecked(False)
        check_vbox.addWidget(self.raw_cb)
        self.csv_cb = QCheckBox("Keep .csv in a folder")
        self.csv_cb.setChecked(False)
        check_vbox.addWidget(self.csv_cb)
        save_hbox.addLayout(check_vbox)
        main_vbox.addLayout(save_hbox, 2, 0, 1, 2, Qt.AlignCenter)

        set_hb = QHBoxLayout()
        lbl = QLabel("Title: ")
        self.title_lbl = QLabel("Reflectance ")
        self.title_text = QLineEdit("")
        self.title_text.setFixedWidth(100)
        set_hb.addWidget(lbl)
        set_hb.addWidget(self.title_lbl)
        main_vbox.addLayout(set_hb, 3, 0, 1, 1, Qt.AlignRight)
        main_vbox.addWidget(self.title_text,3, 1, 1, 1, Qt.AlignLeft)

        color_hb = QHBoxLayout()
        c_lbl = QLabel("Color range: ")
        c1_lbl = QLabel("vmin ")
        c2_lbl = QLabel("vmax ")
        self.vmin = QDoubleSpinBox()
        self.vmin.setDecimals(2)
        self.vmin.setValue(0)
        self.vmax = QDoubleSpinBox()
        self.vmax.setDecimals(2)
        self.vmax.setValue(1)
        color_hb.addWidget(c1_lbl)
        color_hb.addWidget(self.vmin)
        color_hb.addWidget(c2_lbl)
        color_hb.addWidget(self.vmax)
        main_vbox.addWidget(c_lbl, 4, 0, 1, 1, Qt.AlignRight)
        main_vbox.addLayout(color_hb, 4, 1, 1, 1, Qt.AlignLeft)

        freq_lbl = QLabel(r'Frequency of interest (cm-1)')

        freq_hb = QHBoxLayout()
        self.bruker_freq_sb = QDoubleSpinBox()
        self.bruker_freq_sb.setDecimals(2)
        self.bruker_freq_sb.setMinimum(0)
        self.bruker_freq_sb.setMaximum(25000)
        self.bruker_freq_sb.setValue(11000)
        self.bruker_freq_sb.setFixedWidth(100)
        self.bruker_freq_cb = QCheckBox("Generate angle fit")
        self.bruker_freq_cb.setChecked(False)
        freq_hb.addWidget(self.bruker_freq_sb)
        freq_hb.addWidget(self.bruker_freq_cb)
        main_vbox.addWidget(freq_lbl, 5, 0, Qt.AlignRight)
        main_vbox.addLayout(freq_hb, 5, 1, Qt.AlignLeft)

        pause_lbl = QLabel('Pause (sec)')

        self.bruker_pause_sb = QSpinBox()
        self.bruker_pause_sb.setMinimum(0)
        self.bruker_pause_sb.setFixedWidth(50)
        main_vbox.addWidget(pause_lbl, 6, 0, Qt.AlignRight)
        main_vbox.addWidget(self.bruker_pause_sb, 6, 1, Qt.AlignLeft)

        self.tabs.addTab(bruker_tab, 'Bruker')

    def changeText(self):
        if self.add_macro.currentText() == "REFL":
            self.title_lbl.setText("Reflectance ")
        elif self.add_macro.currentText() == "TR":
            self.title_lbl.setText("Transmittance ")

    def initComboTab(self):
        combo_tab = QWidget()

        # create main vbox to organize layout
        main_vbox = QGridLayout()
        main_vbox.setSpacing(10)
        combo_tab.setLayout(main_vbox)

        note0 = QLabel("1. Angles")
        note0.setFixedHeight(50)
        main_vbox.addWidget(note0, 0, 0, 1, 1, Qt.AlignCenter)

        self.select_rotr = QComboBox()
        self.select_rotr.addItem('Polarizer')
        self.select_rotr.addItems(["Analyzer"])
        main_vbox.addWidget(self.select_rotr, 0, 1, 1, 1, Qt.AlignRight)

         # start position label
        start_pos = QLabel('Start Position (deg)')
        # start position spin box
        self.start_pos = QDoubleSpinBox()
        self.start_pos.setDecimals(4)
        self.start_pos.setRange(0, 360)
        # start position hbox
        start_pos_hb = QHBoxLayout()
        start_pos_hb.addWidget(start_pos)
        start_pos_hb.addWidget(self.start_pos)
        main_vbox.addLayout(start_pos_hb, 1, 0, 1, 1, Qt.AlignCenter)

        # stop position label
        stop_pos = QLabel('Stop Position (deg)')
        # stop position spin box
        self.stop_pos = QDoubleSpinBox()
        self.stop_pos.setDecimals(4)
        self.stop_pos.setRange(0, 360)
        # stop position hbox
        stop_pos_hb = QHBoxLayout()
        stop_pos_hb.addWidget(stop_pos)
        stop_pos_hb.addWidget(self.stop_pos)
        main_vbox.addLayout(stop_pos_hb, 1, 1, 1, 1, Qt.AlignCenter)

        # step label
        step = QLabel('Step (deg)')
        # step spin box
        self.step = QDoubleSpinBox()
        self.step.setDecimals(4)
        self.step.setRange(0, 360)
        # start position hbox
        step_hb = QHBoxLayout()
        step_hb.addWidget(step)
        step_hb.addWidget(self.step)
        main_vbox.addLayout(step_hb, 1, 2, 1, 1, Qt.AlignCenter)

        note1 = QLabel("2. Background")
        note1.setFixedHeight(50)
        main_vbox.addWidget(note1, 2, 0, 1, 1, Qt.AlignCenter)

        note2 = QLabel("measures")
        self.back_pos_sb_combo = QDoubleSpinBox()
        self.back_pos_sb_combo.setDecimals(0)
        self.back_pos_sb_combo.setRange(0, 100)
        self.back_pos_sb_combo.setValue(1)

        back_hb = QHBoxLayout()
        back_hb.addWidget(note2)
        back_hb.addWidget(self.back_pos_sb_combo)
        main_vbox.addLayout(back_hb, 2, 1, 1, 1, Qt.AlignCenter)

        note3 = QLabel("3. Sample")
        note3.setFixedHeight(50)

        self.first = QDoubleSpinBox()
        self.first.setDecimals(0)
        self.first.setRange(0, 100)
        self.first.setValue(1)
        self.last = QDoubleSpinBox()
        self.last.setDecimals(0)
        self.last.setRange(0, 100)
        self.last.setValue(1)
        note4 = QLabel("to")
        # stop position hbox
        sample_hb = QHBoxLayout()
        sample_hb.addWidget(note3)
        sample_hb.addWidget(self.first)
        sample_hb.addWidget(note4)
        sample_hb.addWidget(self.last)
        main_vbox.addLayout(sample_hb, 3, 0, 1, 1, Qt.AlignCenter)

        note5 = QLabel("measures")
        self.sam_pos_sb_combo = QDoubleSpinBox()
        self.sam_pos_sb_combo.setDecimals(0)
        self.sam_pos_sb_combo.setRange(0, 100)
        self.sam_pos_sb_combo.setValue(1)

        sample_hb2 = QHBoxLayout()
        sample_hb2.addWidget(note5)
        sample_hb2.addWidget(self.sam_pos_sb_combo)
        main_vbox.addLayout(sample_hb2, 3, 1, 1, 1, Qt.AlignCenter)

        XPM_combo_vbox = QVBoxLayout()
        self.XPM1_combo_rb = QRadioButton("Use XPM1")
        self.XPM1_combo_rb.setChecked(True)
        self.XPM2_combo_rb = QRadioButton("Use XPM2")
        XPM_combo_vbox.addWidget(self.XPM1_combo_rb)
        XPM_combo_vbox.addWidget(self.XPM2_combo_rb)
        main_vbox.addLayout(XPM_combo_vbox, 2, 2, 2, 1, Qt.AlignCenter)

        pause_hbox = QHBoxLayout()
        pause_lbl = QLabel('Pause (sec)')
        self.combo_pause_sb = QSpinBox()
        self.combo_pause_sb.setMinimum(0)
        self.combo_pause_sb.setFixedWidth(50)
        pause_hbox.addWidget(pause_lbl)
        pause_hbox.addWidget(self.combo_pause_sb)
        main_vbox.addLayout(pause_hbox, 4, 1, 1, 1, Qt.AlignCenter)

        add_command3_btn = QPushButton('Add Angle Sweep Command')
        # add_command3_btn.setFixedWidth(150)
        add_command3_btn.setFixedHeight(50)
        add_command3_btn.clicked.connect(lambda: self.addComboCommand(self.select_rotr.currentText(), self.start_pos.value(), self.stop_pos.value(), self.step.value(), self.back_pos_sb_combo.value(), int(self.first.value()), int(self.last.value()), self.sam_pos_sb_combo.value(), self.XPM1_combo_rb.isChecked(), self.combo_pause_sb.value()))
        main_vbox.addWidget(add_command3_btn, 4, 2, 1, 1, Qt.AlignLeft)

        self.tabs.addTab(combo_tab, 'Angle Sweep')

    def initTempSweepTab(self):
        temp_sweep_tab = QWidget()

        # create main vbox to organize layout
        main_vbox = QGridLayout()
        main_vbox.setSpacing(10)
        temp_sweep_tab.setLayout(main_vbox)

        note0 = QLabel("1. Temp")
        note0.setFixedHeight(50)
        main_vbox.addWidget(note0, 0, 0, 1, 1, Qt.AlignCenter)

        uncertainty_lb = QLabel('Uncertainty (K)')
        self.uncertainty_temp = QDoubleSpinBox()
        self.uncertainty_temp.setDecimals(1)
        self.uncertainty_temp.setRange(0, 3)
        self.uncertainty_temp.setFixedWidth(50)
        uncertainty_temp_hb = QHBoxLayout()
        uncertainty_temp_hb.addWidget(uncertainty_lb)
        uncertainty_temp_hb.addWidget(self.uncertainty_temp)
        main_vbox.addLayout(uncertainty_temp_hb, 0, 1, 1, 1, Qt.AlignCenter)

        stability_lb = QLabel('Stability duration (sec)')
        self.stability_temp = QSpinBox()
        self.stability_temp.setRange(30, 180)
        self.stability_temp.setFixedWidth(50)
        stability_temp_hb = QHBoxLayout()
        stability_temp_hb.addWidget(stability_lb)
        stability_temp_hb.addWidget(self.stability_temp)
        main_vbox.addLayout(stability_temp_hb, 0, 2, 1, 1, Qt.AlignCenter)

         # start temp label
        start_temp = QLabel('Start Temp (K)')
        # start position spin box
        self.start_temp = QDoubleSpinBox()
        self.start_temp.setDecimals(1)
        self.start_temp.setRange(4, 350)
        # start temp hbox
        start_temp_hb = QHBoxLayout()
        start_temp_hb.addWidget(start_temp)
        start_temp_hb.addWidget(self.start_temp)
        main_vbox.addLayout(start_temp_hb, 1, 0, 1, 1, Qt.AlignCenter)

        # stop temp label
        stop_temp = QLabel('Stop Temp (K)')
        # stop temp spin box
        self.stop_temp = QDoubleSpinBox()
        self.stop_temp.setDecimals(1)
        self.stop_temp.setRange(4, 350)
        # stop temp hbox
        stop_temp_hb = QHBoxLayout()
        stop_temp_hb.addWidget(stop_temp)
        stop_temp_hb.addWidget(self.stop_temp)
        main_vbox.addLayout(stop_temp_hb, 1, 1, 1, 1, Qt.AlignCenter)

        # step label
        temp_step = QLabel('Step (K)')
        # step spin box
        self.temp_step = QDoubleSpinBox()
        self.temp_step.setDecimals(1)
        self.temp_step.setRange(0, 346)
        # temp step hbox
        temp_step_hb = QHBoxLayout()
        temp_step_hb.addWidget(temp_step)
        temp_step_hb.addWidget(self.temp_step)
        main_vbox.addLayout(temp_step_hb, 1, 2, 1, 1, Qt.AlignCenter)

        note1 = QLabel("2. Background")
        note1.setFixedHeight(50)
        main_vbox.addWidget(note1, 2, 0, 1, 1, Qt.AlignCenter)

        note2 = QLabel("measures")
        self.back_pos_sb_temp = QSpinBox()
        self.back_pos_sb_temp.setRange(0, 100)
        self.back_pos_sb_temp.setValue(1)

        back_hb = QHBoxLayout()
        back_hb.addWidget(note2)
        back_hb.addWidget(self.back_pos_sb_temp)
        main_vbox.addLayout(back_hb, 2, 1, 1, 1, Qt.AlignCenter)

        note3 = QLabel("3. Sample")
        note3.setFixedHeight(50)

        self.first_sample_temp = QSpinBox()
        self.first_sample_temp.setRange(0, 100)
        self.first_sample_temp.setValue(1)
        self.last_sample_temp = QSpinBox()
        self.last_sample_temp.setRange(0, 100)
        self.last_sample_temp.setValue(1)
        note4 = QLabel("to")
        # stop position hbox
        sample_hb = QHBoxLayout()
        sample_hb.addWidget(note3)
        sample_hb.addWidget(self.first_sample_temp)
        sample_hb.addWidget(note4)
        sample_hb.addWidget(self.last_sample_temp)
        main_vbox.addLayout(sample_hb, 3, 0, 1, 1, Qt.AlignCenter)

        note5 = QLabel("measures")
        self.sam_pos_sb_temp = QSpinBox()
        self.sam_pos_sb_temp.setRange(0, 100)
        self.sam_pos_sb_temp.setValue(1)

        sample_hb2 = QHBoxLayout()
        sample_hb2.addWidget(note5)
        sample_hb2.addWidget(self.sam_pos_sb_temp)
        main_vbox.addLayout(sample_hb2, 3, 1, 1, 1, Qt.AlignCenter)

        temp_XPM_vbox = QVBoxLayout()
        self.temp_XPM1_rb = QRadioButton("Use XPM1")
        self.temp_XPM1_rb.setChecked(True)
        self.temp_XPM2_rb = QRadioButton("Use XPM2")
        temp_XPM_vbox.addWidget(self.temp_XPM1_rb)
        temp_XPM_vbox.addWidget(self.temp_XPM2_rb)
        main_vbox.addLayout(temp_XPM_vbox, 2, 2, 2, 1, Qt.AlignCenter)

        auto_xyz_vbox = QVBoxLayout()
        self.temp_auto_xyz_cb = QCheckBox("Auto xyz tracking")
        auto_xyz_vbox.addWidget(self.temp_auto_xyz_cb)
        illumination_hbox = QHBoxLayout()
        illumination_lb = QLabel("Illumination")
        self.set_illumination_sb = QSpinBox()
        self.set_illumination_sb.setValue(5)
        self.set_illumination_sb.setEnabled(False)
        self.temp_auto_xyz_cb.toggled.connect(lambda: self.set_illumination_sb.setEnabled(self.temp_auto_xyz_cb.isChecked()))
        illumination_hbox.addWidget(illumination_lb)
        illumination_hbox.addWidget(self.set_illumination_sb)
        auto_xyz_vbox.addLayout(illumination_hbox)
        main_vbox.addLayout(auto_xyz_vbox, 4, 0, 1, 1, Qt.AlignCenter)

        pause_vb = QVBoxLayout()
        temp_pause_hb = QHBoxLayout()
        pause_lbl = QLabel('Temp Pause (sec)')
        self.temp_sweep_pause_sb = QSpinBox()
        self.temp_sweep_pause_sb.setMinimum(0)
        self.temp_sweep_pause_sb.setMaximum(600)
        self.temp_sweep_pause_sb.setFixedWidth(50)
        temp_pause_hb.addWidget(pause_lbl)
        temp_pause_hb.addWidget(self.temp_sweep_pause_sb)
        pause_vb.addLayout(temp_pause_hb)

        sampe_background_pause_hb = QHBoxLayout()
        sample_background_pause_lbl = QLabel('Sample/Background Pause (sec)')
        self.temp_sweep_sample_backrgound_pause_sb = QSpinBox()
        self.temp_sweep_sample_backrgound_pause_sb.setMinimum(0)
        self.temp_sweep_sample_backrgound_pause_sb.setMaximum(600)
        self.temp_sweep_sample_backrgound_pause_sb.setFixedWidth(50)
        sampe_background_pause_hb.addWidget(sample_background_pause_lbl)
        sampe_background_pause_hb.addWidget(self.temp_sweep_sample_backrgound_pause_sb)
        pause_vb.addLayout(sampe_background_pause_hb)
        main_vbox.addLayout(pause_vb, 4, 1, 1, 1, Qt.AlignCenter)

        self.add_temp_sweep_command_btn = QPushButton('Add Temp Sweep Command')
        # self.add_temp_sweep_command_btn.setFixedWidth(150)
        self.add_temp_sweep_command_btn.setFixedHeight(50)
        self.add_temp_sweep_command_btn.clicked.connect(lambda: self.addTempSweepCommand(self.uncertainty_temp.value(), self.stability_temp.value(), self.start_temp.value(), self.stop_temp.value(), self.temp_step.value(), self.back_pos_sb_temp.value(), int(self.first_sample_temp.value()), int(self.last_sample_temp.value()), self.sam_pos_sb_temp.value(), self.temp_XPM1_rb.isChecked(), self.temp_auto_xyz_cb.isChecked(), self.set_illumination_sb.value(), self.temp_sweep_pause_sb.value(), self.temp_sweep_sample_backrgound_pause_sb.value()))
        self.add_temp_sweep_command_btn.setEnabled(True)
        main_vbox.addWidget(self.add_temp_sweep_command_btn, 4, 2, 1, 1, Qt.AlignCenter)

        self.tabs.addTab(temp_sweep_tab, 'Temp Sweep')

    def initVISweepTab(self):

        VI_sweep_tab = QWidget()

        # create main vbox to organize layout
        main_vbox = QGridLayout()
        main_vbox.setSpacing(10)
        VI_sweep_tab.setLayout(main_vbox)

        note_hbox = QHBoxLayout()
        note0 = QLabel("1. ")
        note0.setFixedHeight(50)
        self.VI_select_cb = QComboBox()
        self.VI_select_cb.addItem("Voltage")
        self.VI_select_cb.addItem("Current")
        self.VI_select_cb.currentIndexChanged.connect(self.VI_switch)
        note_hbox.addWidget(note0)
        note_hbox.addWidget(self.VI_select_cb)
        main_vbox.addLayout(note_hbox, 0, 0, 1, 1, Qt.AlignCenter)

        space_lb = QLabel("")
        self.device_cb1 = QCheckBox("Device 1")
        self.device_cb2 = QCheckBox("Device 2")
        device_vbox = QVBoxLayout()
        device_vbox.addWidget(space_lb)
        device_vbox.addWidget(self.device_cb1)
        device_vbox.addWidget(self.device_cb2)

        self.start_VI_lb = QLabel('Start Voltage (V)')
        # start position spin box
        self.start_VI_sb1 = QDoubleSpinBox()
        self.start_VI_sb1.setDecimals(3)
        self.start_VI_sb1.setRange(0, 210)
        self.start_VI_sb1.setValue(0)
        self.start_VI_sb1.editingFinished.connect(lambda: self.VI_lim_balance(1))
        self.start_VI_sb2 = QDoubleSpinBox()
        self.start_VI_sb2.setDecimals(3)
        self.start_VI_sb2.setRange(0, 210)
        self.start_VI_sb2.setValue(0)
        self.start_VI_sb2.editingFinished.connect(lambda: self.VI_lim_balance(2))

        start_VI_vbox = QVBoxLayout()
        start_VI_vbox.addWidget(self.start_VI_lb)
        start_VI_vbox.addWidget(self.start_VI_sb1)
        start_VI_vbox.addWidget(self.start_VI_sb2)

        self.stop_VI_lb = QLabel('Stop Voltage (V)')
        self.stop_VI_sb1 = QDoubleSpinBox()
        self.stop_VI_sb1.setDecimals(3)
        self.stop_VI_sb1.setRange(0, 210)
        self.stop_VI_sb1.setValue(10)
        self.stop_VI_sb1.editingFinished.connect(lambda: self.VI_lim_balance(1))
        self.stop_VI_sb2 = QDoubleSpinBox()
        self.stop_VI_sb2.setDecimals(3)
        self.stop_VI_sb2.setRange(0, 210)
        self.stop_VI_sb2.setValue(10)
        self.stop_VI_sb2.editingFinished.connect(lambda: self.VI_lim_balance(2))

        stop_VI_vbox = QVBoxLayout()
        stop_VI_vbox.addWidget(self.stop_VI_lb)
        stop_VI_vbox.addWidget(self.stop_VI_sb1)
        stop_VI_vbox.addWidget(self.stop_VI_sb2)

        self.step_VI_lb = QLabel('Step (mV)')
        self.step_VI_sb1 = QDoubleSpinBox()
        self.step_VI_sb1.setRange(1, 1e4)
        self.step_VI_sb1.setValue(100)
        self.step_VI_sb1.editingFinished.connect(lambda: self.VI_step_balance(1))
        self.step_VI_sb2 = QDoubleSpinBox()
        self.step_VI_sb2.setRange(1, 1e4)
        self.step_VI_sb2.setValue(100)
        self.step_VI_sb2.editingFinished.connect(lambda: self.VI_step_balance(2))

        step_VI_vbox = QVBoxLayout()
        step_VI_vbox.addWidget(self.step_VI_lb)
        step_VI_vbox.addWidget(self.step_VI_sb1)
        step_VI_vbox.addWidget(self.step_VI_sb2)

        self.VI_ramp_speed_lb = QLabel("Ramp speed (mV/sec)")
        self.VI_ramp_speed_sb1 = QDoubleSpinBox()
        self.VI_ramp_speed_sb1.setRange(0, 210000)
        self.VI_ramp_speed_sb1.setValue(100)
        self.VI_ramp_speed_sb1.editingFinished.connect(lambda: self.VI_speed_balance(1))
        self.VI_ramp_speed_sb2 = QDoubleSpinBox()
        self.VI_ramp_speed_sb2.setRange(0, 210000)
        self.VI_ramp_speed_sb2.setValue(100)
        self.VI_ramp_speed_sb2.editingFinished.connect(lambda: self.VI_speed_balance(2))
        VI_ramp_speed_vbox = QVBoxLayout()
        VI_ramp_speed_vbox.addWidget(self.VI_ramp_speed_lb)
        VI_ramp_speed_vbox.addWidget(self.VI_ramp_speed_sb1)
        VI_ramp_speed_vbox.addWidget(self.VI_ramp_speed_sb2)

        points_VI_vbox = QVBoxLayout()
        self.points_VI_lb = QLabel("Points per step")
        self.points_VI_sb1 = QSpinBox()
        self.points_VI_sb1.setRange(2, 100)
        self.points_VI_sb1.setValue(30)
        self.points_VI_sb2 = QSpinBox()
        self.points_VI_sb2.setRange(2, 100)
        self.points_VI_sb2.setValue(30)
        self.points_VI_sb1.editingFinished.connect(lambda: self.points_VI_sb2.setValue(self.points_VI_sb1.value()))
        self.points_VI_sb2.editingFinished.connect(lambda: self.points_VI_sb1.setValue(self.points_VI_sb2.value()))
        points_VI_vbox.addWidget(self.points_VI_lb)
        points_VI_vbox.addWidget(self.points_VI_sb1)
        points_VI_vbox.addWidget(self.points_VI_sb2)

        VI_hbox = QHBoxLayout()
        VI_hbox.addLayout(device_vbox)
        VI_hbox.addLayout(start_VI_vbox)
        VI_hbox.addLayout(stop_VI_vbox)
        VI_hbox.addLayout(step_VI_vbox)
        VI_hbox.addLayout(VI_ramp_speed_vbox)
        VI_hbox.addLayout(points_VI_vbox)
        main_vbox.addLayout(VI_hbox, 0, 1, 2, 4, Qt.AlignCenter)

        note1 = QLabel("2. Background")
        note1.setFixedHeight(50)
        main_vbox.addWidget(note1, 2, 0, 1, 1, Qt.AlignCenter)

        note2 = QLabel("measures")
        self.back_pos_sb_VI = QSpinBox()
        self.back_pos_sb_VI.setRange(0, 100)
        self.back_pos_sb_VI.setValue(1)

        back_hb = QHBoxLayout()
        back_hb.addWidget(note2)
        back_hb.addWidget(self.back_pos_sb_VI)
        main_vbox.addLayout(back_hb, 2, 1, 1, 1, Qt.AlignCenter)

        note3 = QLabel("3. Sample")
        note3.setFixedHeight(50)

        self.first_sample_VI = QSpinBox()
        self.first_sample_VI.setRange(0, 100)
        self.first_sample_VI.setValue(1)
        self.last_sample_VI = QSpinBox()
        self.last_sample_VI.setRange(0, 100)
        self.last_sample_VI.setValue(1)
        note4 = QLabel("to")
        # stop position hbox
        sample_hb = QHBoxLayout()
        sample_hb.addWidget(note3)
        sample_hb.addWidget(self.first_sample_VI)
        sample_hb.addWidget(note4)
        sample_hb.addWidget(self.last_sample_VI)
        main_vbox.addLayout(sample_hb, 3, 0, 1, 1, Qt.AlignCenter)

        note5 = QLabel("measures")
        self.sam_pos_sb_VI = QSpinBox()
        self.sam_pos_sb_VI.setRange(0, 100)
        self.sam_pos_sb_VI.setValue(1)

        sample_hb2 = QHBoxLayout()
        sample_hb2.addWidget(note5)
        sample_hb2.addWidget(self.sam_pos_sb_VI)
        main_vbox.addLayout(sample_hb2, 3, 1, 1, 1, Qt.AlignCenter)

        VI_XPM_vbox = QVBoxLayout()
        self.VI_XPM1_rb = QRadioButton("Use XPM1")
        self.VI_XPM1_rb.setChecked(True)
        self.VI_XPM2_rb = QRadioButton("Use XPM2")
        VI_XPM_vbox.addWidget(self.VI_XPM1_rb)
        VI_XPM_vbox.addWidget(self.VI_XPM2_rb)
        main_vbox.addLayout(VI_XPM_vbox, 2, 2, 2, 1, Qt.AlignCenter)

        pause_vb = QVBoxLayout()
        VI_pause_hb = QHBoxLayout()
        pause_lbl = QLabel('Voltage/Current Pause (sec)')
        self.VI_sweep_pause_sb = QSpinBox()
        self.VI_sweep_pause_sb.setMinimum(0)
        self.VI_sweep_pause_sb.setMaximum(600)
        self.VI_sweep_pause_sb.setFixedWidth(50)
        VI_pause_hb.addWidget(pause_lbl)
        VI_pause_hb.addWidget(self.VI_sweep_pause_sb)
        pause_vb.addLayout(VI_pause_hb)

        sampe_background_pause_hb = QHBoxLayout()
        sample_background_pause_lbl = QLabel('Sample/Background Pause (sec)')
        self.VI_sweep_sample_backrgound_pause_sb = QSpinBox()
        self.VI_sweep_sample_backrgound_pause_sb.setMinimum(0)
        self.VI_sweep_sample_backrgound_pause_sb.setMaximum(600)
        self.VI_sweep_sample_backrgound_pause_sb.setFixedWidth(50)
        sampe_background_pause_hb.addWidget(sample_background_pause_lbl)
        sampe_background_pause_hb.addWidget(self.VI_sweep_sample_backrgound_pause_sb)
        pause_vb.addLayout(sampe_background_pause_hb)
        main_vbox.addLayout(pause_vb, 4, 1, 1, 1, Qt.AlignCenter)

        self.add_VI_sweep_command_btn = QPushButton('Add Voltage Sweep Command')
        # self.add_VI_sweep_command_btn.setFixedWidth(150)
        self.add_VI_sweep_command_btn.setFixedHeight(50)
        self.add_VI_sweep_command_btn.clicked.connect(lambda: self.addVISweepCommand(self.VI_select_cb.currentText(), self.start_VI_sb1.value(), self.stop_VI_sb1.value(), self.step_VI_sb1.value(), self.VI_ramp_speed_sb1.value(), self.start_VI_sb2.value(), self.stop_VI_sb2.value(), self.step_VI_sb2.value(), self.VI_ramp_speed_sb2.value(), self.points_VI_sb1.value(), self.back_pos_sb_VI.value(), int(self.first_sample_VI.value()), int(self.last_sample_VI.value()), self.sam_pos_sb_VI.value(), self.VI_XPM1_rb.isChecked(), self.VI_sweep_pause_sb.value(), self.VI_sweep_sample_backrgound_pause_sb.value()))
        main_vbox.addWidget(self.add_VI_sweep_command_btn, 4, 4, 1, 1, Qt.AlignCenter)

        self.tabs.addTab(VI_sweep_tab, 'Voltage/Current Sweep')

    def VI_switch(self):
        if self.VI_select_cb.currentText() == "Voltage":
            self.start_VI_lb.setText('Start Voltage (V)')
            self.start_VI_sb1.setRange(0, 210)
            self.start_VI_sb1.setValue(0)
            self.start_VI_sb2.setRange(0, 210)
            self.start_VI_sb2.setValue(0)
            self.stop_VI_lb.setText('Stop Voltage (V)')
            self.stop_VI_sb1.setRange(0, 210)
            self.stop_VI_sb1.setValue(10)
            self.stop_VI_sb2.setRange(0, 210)
            self.stop_VI_sb2.setValue(10)
            self.step_VI_lb.setText('Step (mV)')
            self.step_VI_sb1.setRange(1, 1e4)
            self.step_VI_sb1.setValue(100)
            self.step_VI_sb2.setRange(1, 1e4)
            self.step_VI_sb2.setValue(100)
            self.add_VI_sweep_command_btn.setText('Add Voltage Sweep Command')
            self.VI_ramp_speed_lb.setText("Ramp speed (mV/sec)")
            self.VI_ramp_speed_sb1.setRange(0, 210000)
            self.VI_ramp_speed_sb1.setValue(100)
            self.VI_ramp_speed_sb2.setRange(0, 210000)
            self.VI_ramp_speed_sb2.setValue(100)
        else:
            self.start_VI_lb.setText('Start Current (A)')
            self.start_VI_sb1.setRange(0, 1.05)
            self.start_VI_sb1.setValue(0)
            self.start_VI_sb2.setRange(0, 1.05)
            self.start_VI_sb2.setValue(0)
            self.stop_VI_lb.setText('Stop Current (A)')
            self.stop_VI_sb1.setValue(1)
            self.stop_VI_sb1.setRange(0, 1.05)
            self.stop_VI_sb2.setValue(1)
            self.stop_VI_sb2.setRange(0, 1.05)
            self.step_VI_lb.setText('Step (mA)')
            self.step_VI_sb1.setRange(1, 1e4)
            self.step_VI_sb1.setValue(10)
            self.step_VI_sb2.setRange(1, 1e4)
            self.step_VI_sb2.setValue(10)
            self.add_VI_sweep_command_btn.setText('Add Current Sweep Command')
            self.VI_ramp_speed_lb.setText("Ramp speed (mA/sec)")
            self.VI_ramp_speed_sb1.setRange(0, 1050)
            self.VI_ramp_speed_sb1.setValue(10)
            self.VI_ramp_speed_sb2.setRange(0, 1050)
            self.VI_ramp_speed_sb2.setValue(10)

    def VI_lim_balance(self, mode):
        d1 = abs(self.stop_VI_sb1.value()-self.start_VI_sb1.value())
        d2 = abs((self.stop_VI_sb2.value()-self.start_VI_sb2.value()))
        if mode == 1:
            self.step_VI_sb1.setValue(d1/d2*self.step_VI_sb2.value())
            self.VI_ramp_speed_sb1.setValue(d1/d2*self.VI_ramp_speed_sb2.value())
        elif mode == 2:
            self.step_VI_sb2.setValue(d2/d1*self.step_VI_sb1.value())
            self.VI_ramp_speed_sb2.setValue(d2/d1*self.VI_ramp_speed_sb1.value())

    def VI_step_balance(self, mode):
        d1 = abs(self.stop_VI_sb1.value()-self.start_VI_sb1.value())
        d2 = abs((self.stop_VI_sb2.value()-self.start_VI_sb2.value()))
        if mode == 1:
            self.step_VI_sb2.setValue(d2/d1*self.step_VI_sb1.value())
        elif mode == 2:
            self.step_VI_sb1.setValue(d1/d2*self.step_VI_sb2.value())

    def VI_speed_balance(self, mode):
        d1 = abs(self.stop_VI_sb1.value()-self.start_VI_sb1.value())
        d2 = abs((self.stop_VI_sb2.value()-self.start_VI_sb2.value()))
        if mode == 1:
            self.VI_ramp_speed_sb2.setValue(d2/d1*self.VI_ramp_speed_sb1.value())
        elif mode == 2:
            self.VI_ramp_speed_sb1.setValue(d1/d2*self.VI_ramp_speed_sb2.value())

    def addPolarizerCommand(self, angle, pause=0.0):
        # create text for command and add it to display
        if control_widget.polarizer_cb.currentText() == "Newport" and not pol_new_widget.connected:
            QMessageBox.warning(self.main_window, "Newport Error", "Newport rotator is not connected!")
            self.error = True
            return
        if control_widget.polarizer_cb.currentText() == "Thorlabs" and not pol_thor_widget.connected:
            QMessageBox.warning(self.main_window, "Thorlabs Error", "Thorlabs rotator is not connected!")
            self.error = True
            return
        newText = self.command_display.text().replace('</ol>', '')
        if control_widget.polarizer_cb.currentText() == "Newport":
            newText += '<li>Polarizer: Newport, {}deg, {}s</li>'.format(angle, pause)
        else:
            newText += '<li>Polarizer: Thorlabs, {}deg, {}s</li>'.format(angle, pause)
        newText += '</ol>'
        self.command_display.setText(newText)

        # create actual command and append it to list of commands
        if control_widget.polarizer_cb.currentText() == "Newport":
            command = NewportCommand(self.main_window, "Polarizer", angle, pause)
        else:
            command = ThorlabsCommand(self.main_window, "Polarizer", angle, pause)
        self.commands.append(command)

        self.error = False
        return

    def addPolarizerCommands(self):
        startAngle = self.start_pos_sb.value()
        stopAngle = self.stop_pos_sb.value()
        step = self.step_sb.value()
        pause = self.pause_sb.value()

        if step == 0:
            QMessageBox.warning(self, 'Step Error', 'Step cannot be 0')
            self.error = True
            return

        for angle in np.arange(startAngle, stopAngle + step, step):
            self.addPolarizerCommand(angle, pause)

        self.error = False
        return

    def addAnalyzerCommand(self, angle, pause=0.0):
        if control_widget.analyzer_cb.currentText() == "Newport" and not ana_new_widget.connected:
            QMessageBox.warning(self.main_window, "Newport Error", "Newport rotator is not connected!")
            self.error = True
            return
        if control_widget.analyzer_cb.currentText() == "Thorlabs" and not ana_thor_widget.connected:
            QMessageBox.warning(self.main_window, "Thorlabs Error", "Thorlabs rotator is not connected!")
            self.error = True
            return
        # create text for command and add it to display
        newText = self.command_display.text().replace('</ol>', '')
        if control_widget.analyzer_cb.currentText() == "Newport":
            newText += '<li>Analyzer: Newport, {}deg, {}s</li>'.format(angle, pause)
        else:
            newText += '<li>Analyzer: Thorlabs, {}deg, {}s</li>'.format(angle, pause)
        newText += '</ol>'
        self.command_display.setText(newText)

        # create actual command and append it to list of commands
        if control_widget.analyzer_cb.currentText() == "Newport":
            command = NewportCommand(self.main_window, "Analyzer", angle, pause)
        else:
            command = ThorlabsCommand(self.main_window, "Analyzer", angle, pause)
        self.commands.append(command)

        self.error = False
        return

    def addAnalyzerCommands(self):
        startAngle = self.start_pos_sb2.value()
        stopAngle = self.stop_pos_sb2.value()
        step = self.step_sb2.value()
        pause = self.pause_sb2.value()

        if step == 0:
            QMessageBox.warning(self, 'Step Error', 'Step cannot be 0')
            self.error = True
            return

        for angle in np.arange(startAngle, stopAngle + step, step):
            self.addAnalyzerCommand(angle, pause)

        self.error = False
        return

    def addTempCommand(self, temp, un, duration, auto_xyz=False, illumination=5):
        if not temp_widget.mercury.connection:
            QMessageBox.warning(self.main_window, "Mercury Error", "Mercury ITC temperature controller is not connected!")
            self.error = True
            return
        if auto_xyz and not camera_widget.connected:
            QMessageBox.warning(self.main_window, "Pylon Error", "The camera is not connected!")
            self.error = True
            return
        elif auto_xyz and (camera_widget.x_reference is None or camera_widget.y_reference is None or camera_widget.z_reference is None):
            QMessageBox.warning(self.main_window, "Pylon Error", "You haven't declared the reference position!")
            self.error = True
            return
        elif auto_xyz and camera_widget.img_record is None:
            QMessageBox.warning(self.main_window, "Pylon Error", "You haven't take a snippet of the reference position!")
            self.error = True
            return

        pause = self.temp_pause_sb.value()

        # create text for command and add it to display
        newText = self.command_display.text().replace('</ol>', '')
        newText += '<li>Set Temperature: {}K, {}K, {}s, {}s, {}, {}</li>'.format(temp, un, duration, pause, auto_xyz, illumination)
        newText += '</ol>'
        self.command_display.setText(newText)

        # create actual command and append it to list of commands
        command = SetTemperatureCommand(self.main_window, temp, un, duration, pause, auto_xyz, illumination)
        self.commands.append(command)

        self.error = False
        return

    def addTranCommand1(self, x, y, z, auto_xyz, pause=0.0):
        if not tran_widget.connected:
            QMessageBox.warning(self.main_window, "Tango XYZ Error", "Tango XYZ translator is not connected!")
            self.error = True
            return
        # create text for command and add it to display
        newText = self.command_display.text().replace('</ol>', '')
        newText += '<li>Translator (Abs): {}{}, {}{}, {}{}, {}s</li>'.format(x, f"{chr(956)}m", y, f"{chr(956)}m", z, f"{chr(956)}m", pause)
        newText += '</ol>'
        self.command_display.setText(newText)

        # create actual command and append it to list of commands
        command = TranCommand(self.main_window, x, y, z, auto_xyz, pause, 1)
        self.commands.append(command)

        self.error = False
        return

    def addTranCommand2(self, x, y, z, auto_xyz, pause=0.0):
        if not tran_widget.connected:
            QMessageBox.warning(self.main_window, "Tango XYZ Error", "Tango XYZ translator is not connected!")
            self.error = True
            return
        # create text for command and add it to display
        newText = self.command_display.text().replace('</ol>', '')
        newText += '<li>Translator (Rel): {}{}, {}{}, {}{}, {}s</li>'.format(x, f"{chr(956)}m", y, f"{chr(956)}m", z, f"{chr(956)}m", pause)
        newText += '</ol>'
        self.command_display.setText(newText)

        # create actual command and append it to list of commands
        command = TranCommand(self.main_window, x, y, z, auto_xyz, pause, 2)
        self.commands.append(command)

        self.error = False
        return

    def addPylonTranCommand(self, x, y, z, auto_xyz, pause=0.0):
        if not tran_widget.connected:
            QMessageBox.warning(self.main_window, "Tango XYZ Error", "Tango XYZ translator is not connected!")
            self.error = True
            return
        if x is None or y is None or z is None:
            QMessageBox.warning(self.main_window, "Pylon Error", "You haven't declared a reference position!")
            self.error = True
            return
        # create text for command and add it to display
        newText = self.command_display.text().replace('</ol>', '')
        newText += '<li>Translator (Abs): {}{}, {}{}, {}{}, ReferencePoint{}, {}s, reference</li>'.format(x, f"{chr(956)}m", y, f"{chr(956)}m", z, f"{chr(956)}m", auto_xyz, pause)
        newText += '</ol>'
        self.command_display.setText(newText)

        # create actual command and append it to list of commands
        command = TranCommand(self.main_window, x, y, z, auto_xyz, pause, 1)
        self.commands.append(command)

        self.error = False
        return

    def addBrukerTranCommand(self, pos, num, auto_xyz, pause, temp=0.0):
        if not tran_widget.connected:
            QMessageBox.warning(self.main_window, "Tango XYZ Error", "Tango XYZ translator is not connected!")
            self.error = True
            return
        if auto_xyz and not camera_widget.connected:
            QMessageBox.warning(self.main_window, "Camera Error", "Camera is not connected!")
            self.error = True
            return
        if bruker_widget.temp_based_pos:
            if not str(temp) in pos:
                QMessageBox.warning(self.main_window, "Temp", "Fail to access the position data at this temperature!")
                self.error = True
                return
            else:
                pos = pos[str(temp)]
        if num < 0:
            x = pos[0][0]
            y = pos[0][1]
            z = pos[0][2]
            if auto_xyz:
                if not (tran_widget.x-10000 < x+camera_widget.x_offset < tran_widget.x+10000 and tran_widget.y-10000 < y+camera_widget.y_offset < tran_widget.y+10000 and tran_widget.z-5000 < z+camera_widget.z_offset < tran_widget.z+5000):
                    QMessageBox.warning(self, 'Background alert', 'Background position is away from the current position by more than 5mm!')
            else:
                if not (tran_widget.x-10000 < x < tran_widget.x+10000 and tran_widget.y-10000 < y < tran_widget.y+10000 and tran_widget.z-5000 < z < tran_widget.z+5000):
                   QMessageBox.warning(self, 'Background alert', 'Background position is away from the current position by more than 5mm!')
        else:
            if num < len(bruker_widget.sample_pos):
                x = pos[num][0]
                y = pos[num][1]
                z = pos[num][2]
                if auto_xyz:
                    if not (tran_widget.x-5000 < x+camera_widget.x_offset < tran_widget.x+5000 and tran_widget.y-5000 < y+camera_widget.y_offset < tran_widget.y+5000 and tran_widget.z-5000 < z+camera_widget.z_offset < tran_widget.z+5000):
                        QMessageBox.warning(self, 'Background alert', 'Sample position is away from the current position by more than 5mm!')
                else:
                    if not (tran_widget.x-5000 < x < tran_widget.x+5000 and tran_widget.y-5000 < y < tran_widget.y+5000 and tran_widget.z-5000 < z < tran_widget.z+5000):
                       QMessageBox.warning(self, 'Background alert', 'Sample position is away from the current position by more than 5mm!')
            else:
                QMessageBox.warning(self, 'Sample warning', 'Sample is not found!')
                self.error = True
                return
        newText = self.command_display.text().replace('</ol>', '')
        if auto_xyz:
            if num < 0:
                newText += '<li>Translator (Abs): {}{}, {}{}, {}{}, ReferencePoint{}, {}s, background'.format(x+camera_widget.x_offset, f"{chr(956)}m", y+camera_widget.y_offset, f"{chr(956)}m", z+camera_widget.z_offset, f"{chr(956)}m", auto_xyz, pause)
            else:
                newText += '<li>Translator (Abs): {}{}, {}{}, {}{}, ReferencePoint{}, {}s, sample{}'.format(x+camera_widget.x_offset, f"{chr(956)}m", y+camera_widget.y_offset, f"{chr(956)}m", z+camera_widget.z_offset, f"{chr(956)}m", auto_xyz, pause, num+1)
        else:
            if num < 0:
                newText += '<li>Translator (Abs): {}{}, {}{}, {}{}, ReferencePoint{}, {}s, background'.format(x, f"{chr(956)}m", y, f"{chr(956)}m", z, f"{chr(956)}m", auto_xyz, pause)
            else:
                newText += '<li>Translator (Abs): {}{}, {}{}, {}{}, ReferencePoint{}, {}s, sample{}'.format(x, f"{chr(956)}m", y, f"{chr(956)}m", z, f"{chr(956)}m", auto_xyz, pause, num+1)
        if bruker_widget.temp_based_pos:
            newText += ', {}K temp-based</li>'.format(temp)
        else:
            newText += '</li>'
        newText += '</ol>'
        self.command_display.setText(newText)

        # create actual command and append it to list of commands
        command = TranCommand(self.main_window, x, y, z, auto_xyz, pause, 1)
        self.commands.append(command)

        self.error = False
        return

    def addBrukerCommand(self, mode, XPM1, pause=0.0):
        # create text for command and add it to display
        if XPM1:
            xpm_path = bruker_widget.XPM
            data_name = bruker_widget.data_name
        else:
            xpm_path = bruker_widget.XPM2
            data_name = bruker_widget.data_name2
        data_path = bruker_widget.data
        if xpm_path == "":
            QMessageBox.warning(self, 'XPM', 'XPM file is not declared!')
            self.error = True
            return
        if mode == 2 and (data_path == "" or data_name == ""):
            QMessageBox.warning(self, 'Data', 'Output data directory or file name is not declared!')
            self.error = True
            return
        newText = self.command_display.text().replace('</ol>', '')
        if mode == 1:
            if XPM1:
                newText += '<li>Bruker: Scan background, XPM1, {}s</li>'.format(pause)
            else:
                newText += '<li>Bruker: Scan background, XPM2, {}s</li>'.format(pause)
        else:
            if XPM1:
                newText += '<li>Bruker: Scan sample, XPM1, {}s</li>'.format(pause)
            else:
                newText += '<li>Bruker: Scan sample, XPM2, {}s</li>'.format(pause)
        newText += '</ol>'
        self.command_display.setText(newText)
        self.reminder = True

        # create actual command and append it to list of commands
        command = BrukerCommand(self.main_window, xpm_path, data_path, data_name, pause, mode)
        self.commands.append(command)

        self.error = False
        return

    def addBrukerSaveCommand(self, XPM1, type, title, vmin, vmax, save_raw, keep_csv, freq, angle_fit):
        if XPM1:
            xpm_path = bruker_widget.XPM
            data_name = bruker_widget.data_name
            dataset = 1
        else:
            xpm_path = bruker_widget.XPM2
            data_name = bruker_widget.data_name2
            dataset = 2
        if type == "REFL":
            if "REFL" in xpm_path or xpm_path == "":
                if save_raw:
                    # macro_path = r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\Instruments\VERTEX_80v\MarcoYinming\EXPORT_MULTI_REFL_RSC_SSC.mtx"
                    macro_path = r"{}\MarcoYinming\EXPORT_MULTI_REFL_RSC_SSC.mtx".format(cwd_path)
                else:
                    # macro_path = r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\Instruments\VERTEX_80v\MarcoYinming\EXPORT_MULTI_REFL.mtx"
                    macro_path = r"{}\MarcoYinming\EXPORT_MULTI_REFL.mtx".format(cwd_path)
            else:
                QMessageBox.warning(self.main_window, "REFL", "Your xpm file does not correspond to reflectance!")
                self.error = True
                return
        elif type == "TR":
            if "TRANS" in xpm_path or xpm_path == "":
                if save_raw:
                    # macro_path = r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\Instruments\VERTEX_80v\MarcoYinming\EXPORT_MULTI_TR_RSC_SSC.mtx"
                    macro_path = r"{}\MarcoYinming\EXPORT_MULTI_TR_RSC_SSC.mtx".format(cwd_path)
                else:
                    # macro_path = r"C:\Users\Public\Documents\Bruker\OPUS_8.5.29\Instruments\VERTEX_80v\MarcoYinming\EXPORT_MULTI_TR.mtx"
                    macro_path = r"{}\MarcoYinming\EXPORT_MULTI_TR.mtx".format(cwd_path)
            else:
                QMessageBox.warning(self.main_window, "TR", "Your xpm file does not correspond to transmittance!")
                self.error = True
                return
        else:
            QMessageBox.warning(self.main_window, "MTX undefined", "You have to select a mtx file in order to save OPUS data!")
            self.error = True
            return
        if vmax <= vmin:
            QMessageBox.warning(self.main_window, "Invalid vmin & vmax", "Input vmin or vmax is invalid!")
            self.error = True
            return
        data_path = bruker_widget.data
        if data_path == "" or data_name == "":
            QMessageBox.warning(self, 'Data', 'Output data directory or file name is not declared!')
            self.error = True
            return
        newText = self.command_display.text().replace('</ol>', '')
        newText += '<li>Bruker: Save result as txt and png, dataset{}, {}, {}, vmin={}, vmax={}, raw spectra {}, csv {}, freq={}, angle fit {}</li>'.format(dataset, type, title, vmin, vmax, save_raw, keep_csv, freq, angle_fit)
        newText += '</ol>'
        self.command_display.setText(newText)

        self.log_cb.setChecked(True)

        angle = None
        angle_list = []
        for i in range(len(self.commands)):
            command = self.commands[i]
            if isinstance(command, ThorlabsCommand) or isinstance(command, NewportCommand):
                angle = command.angle
                if angle > 180:
                    angle -= 360
            elif isinstance(command, BrukerCommand) and command.mode != 1:
                if (XPM1 and command.data_name == bruker_widget.data_name) or (not XPM1 and command.data_name == bruker_widget.data_name2):
                    if angle is not None:
                        angle_list.append(angle)

        # create actual command and append it to list of commands
        command = BrukerSaveCommand(self.main_window, macro_path, data_path, data_name, title, vmin, vmax, save_raw, keep_csv, freq, angle_fit, angle_list)

        self.commands.append(command)
        self.error = False
        return

    def addComboCommand(self, rotr_type, start, stop, step, back_meas, first, last, sam_meas, XPM1, pause=0.0):
        if start < stop:
            angle = np.arange(start, stop+step, step)
        else:
            angle = np.arange(start, stop-step, -step)
        sample = np.arange(first, last+1, 1)
        for i in angle:
            if rotr_type == "Polarizer":
                self.addPolarizerCommand(i, pause)
            elif rotr_type == "Analyzer":
                self.addAnalyzerCommand(i, pause)
            else:
                QMessageBox.warning(self.main_window, "Undefined rotator", "You have to declare a rotator before use!")
                self.error = True
                return
            self.addBrukerTranCommand(bruker_widget.background_pos, -1, self.tran_auto_xyz_cb.isChecked(), pause, self.temp_pause_sb.value())
            # Prevent multiple error alerts
            if not tran_widget.connected:
                return
            for n in range(int(back_meas)):
                self.addBrukerCommand(1, XPM1, pause)
            for s in sample:
                self.addBrukerTranCommand(bruker_widget.sample_pos, int(s-1), self.tran_auto_xyz_cb.isChecked(), pause, self.temp_pause_sb.value())
                for m in range(int(sam_meas)):
                    self.addBrukerCommand(2, XPM1, pause)

        self.error = False
        return

    def addTempSweepCommand(self, un, duration, start, stop, step, back_meas, first, last, sam_meas, XPM1, auto_xyz, illumination, temp_pause, sample_background_pause):
        if start < stop:
            temp = np.arange(start, stop+step, step)
        else:
            temp = np.arange(start, stop-step, -step)
        sample = np.arange(first, last+1, 1)
        for t in temp:
            if auto_xyz:
                self.addPylonTranCommand(camera_widget.x_reference, camera_widget.y_reference, camera_widget.z_reference, auto_xyz, sample_background_pause)
            self.temp_pause_sb.setValue(temp_pause)
            self.addTempCommand(t, un, duration, auto_xyz, illumination)
            # Prevent multiple error alerts
            if not tran_widget.connected:
                QMessageBox.warning(self, 'Tango', 'Tango is not connected!')
                return
            if back_meas > 0:
                self.addBrukerTranCommand(bruker_widget.background_pos, -1, auto_xyz, sample_background_pause, round(t, 1))
                for n in range(int(back_meas)):
                    self.addBrukerCommand(1, XPM1, sample_background_pause)
            if sam_meas > 0:
                for s in sample:
                    if s >= 1:
                        self.addBrukerTranCommand(bruker_widget.sample_pos, int(s-1), auto_xyz, sample_background_pause, round(t, 1))
                        for m in range(int(sam_meas)):
                            self.addBrukerCommand(2, XPM1, sample_background_pause)

        self.error = False
        return

    def addKeithleyCommand(self, device, mode, ramp_speed, step, vi, points, VI_pause=0):
        if device == 1:
            if not keithley_widget.connected1:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'Device 1 is not connecteed!')
                return
            if not keithley_widget.enabled1:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'You need to enable a source current or voltage before ramping!')
                return
            if mode == "Voltage" and abs(vi) > keithley_widget.keithley1.voltage_range:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'The input voltage exceeds the limit!')
                return
            if mode == "Current" and abs(vi) > keithley_widget.keithley1.current_range:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'The input current exceeds the limit!')
                return
        elif device == 2:
            if not keithley_widget.connected2:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'Device 2 is not connecteed!')
                return
            if not keithley_widget.enabled2:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'You need to enable a source current or voltage before ramping!')
                return
            if mode == "Voltage" and abs(vi) > keithley_widget.keithley2.voltage_range:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'The input voltage exceeds the limit!')
                return
            if mode == "Current" and abs(vi) > keithley_widget.keithley2.current_range:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'The input current exceeds the limit!')
                return

        # create text for command and add it to display
        newText = self.command_display.text().replace('</ol>', '')
        if mode == "Voltage":
            newText += '<li>Keithley: device{}, voltage ramp, {}V, {} mV/sec, {}mV, {}points, {}s</li>'.format(device, vi, ramp_speed, step, points, VI_pause)
        else:
            newText += '<li>Keithley: device{}, current ramp, {}A, {} mA/sec, {}mA, {}points, {}s</li>'.format(device, vi, ramp_speed, step, points, VI_pause)
        newText += '</ol>'
        self.command_display.setText(newText)

        command = KeithleyCommand(self.main_window, device, mode, ramp_speed, step, vi, points, VI_pause)
        self.commands.append(command)

    def addDoubleKeithleyCommand(self, mode, ramp_speed1, step1, vi1, ramp_speed2, step2, vi2, points, VI_pause=0):
        if not keithley_widget.connected1:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'Device 1 is not connecteed!')
            return
        if not keithley_widget.connected2:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'Device 2 is not connecteed!')
            return
        if not keithley_widget.enabled1:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'You need to enable a source current or voltage before ramping!')
            return
        if not keithley_widget.enabled2:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'You need to enable a source current or voltage before ramping!')
            return
        if mode == "Voltage" and abs(vi1) > keithley_widget.keithley1.voltage_range:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'Device 1: input voltage exceeds the limit!')
            return
        if mode == "Voltage" and abs(vi2) > keithley_widget.keithley2.voltage_range:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'Device 2: input voltage exceeds the limit!')
            return
        if mode == "Current" and abs(vi1) > keithley_widget.keithley1.current_range:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'Device 1: The input current exceeds the limit!')
            return
        if mode == "Current" and abs(vi2) > keithley_widget.keithley2.current_range:
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'Device 2: The input current exceeds the limit!')
            return

        # create text for command and add it to display
        newText = self.command_display.text().replace('</ol>', '')
        if mode == "Voltage":
            newText += '<li>Keithley: two device, voltage ramp, {}V, {} mV/sec, {}mV, {}V, {} mV/sec, {}mV, {}points, {}s</li>'.format(vi1, ramp_speed1, step1, vi2, ramp_speed2, step2, points, VI_pause)
        else:
            newText += '<li>Keithley: two device, current ramp, {}A, {} mA/sec, {}mA, {}A, {} mA/sec, {}mA, {}points, {}s</li>'.format(vi1, ramp_speed1, step1, vi2, ramp_speed2, step2, points, VI_pause)
        newText += '</ol>'
        self.command_display.setText(newText)

        command = DoubleKeithleyCommand(self.main_window, mode, ramp_speed1, step1, vi1, ramp_speed2, step2, vi2, points, VI_pause)
        self.commands.append(command)

    def addVISweepCommand(self, mode, start1, stop1, step1, speed1, start2, stop2, step2, speed2, points, back_meas, first, last, sam_meas, XPM1, VI_pause, sample_background_pause):
        if not self.device_cb1.isChecked() and not self.device_cb2.isChecked():
            self.error = True
            QMessageBox.warning(self, 'Source meter', 'No source meter selected!')
            return
        if start1 < stop1:
            VI1 = np.arange(start1, stop1+step1/1e3, step1/1e3)
        else:
            VI1 = np.arange(start1, stop1-step1/1e3, -step1/1e3)
        if start2 < stop2:
            VI2 = np.arange(start2, stop2+step2/1e3, step2/1e3)
        else:
            VI2 = np.arange(start2, stop2-step2/1e3, -step2/1e3)
        sample = np.arange(first, last+1, 1)
        for i in range(len(VI1)):
            # Prevent multiple error alerts
            if not keithley_widget.connected1 and not keithley_widget.connected2:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'No source meter is not connecteed!')
                return
            if not keithley_widget.enabled1 and not keithley_widget.enabled2:
                self.error = True
                QMessageBox.warning(self, 'Source meter', 'You need to enable a source current or voltage before ramping!')
                return
            if self.device_cb1.isChecked() and self.device_cb2.isChecked():
                self.addDoubleKeithleyCommand(mode, speed1, step1, VI1[i], speed2, step2, VI2[i], points, VI_pause)
            elif self.device_cb1.isChecked():
                self.addKeithleyCommand(1, mode, speed1, step1, VI1[i], points, VI_pause)
            elif self.device_cb2.isChecked():
                self.addKeithleyCommand(2, mode, speed2, step2, VI2[i], points, VI_pause)
            # Prevent multiple error alerts
            if not tran_widget.connected:
                QMessageBox.warning(self, 'Tango', 'Tango is not connected!')
                return
            if back_meas > 0:
                self.addBrukerTranCommand(bruker_widget.background_pos, -1, False, sample_background_pause)
                for n in range(int(back_meas)):
                    self.addBrukerCommand(1, XPM1, sample_background_pause)
            if sam_meas > 0:
                for s in sample:
                    if s >= 1:
                        self.addBrukerTranCommand(bruker_widget.sample_pos, int(s-1), False, sample_background_pause)
                        for m in range(int(sam_meas)):
                            self.addBrukerCommand(2, XPM1, sample_background_pause)

        self.error = False
        return

    def call_temp_saving(self):
        self.start_index = []
        for panel in temp_widget.panels.values():
            self.start_index.append(len(panel.xdata))

    def stop_temp_saving(self):
        i = 0
        self.stop_index = []
        # Pay attention to the number of panels, now the program only works for single panel
        for panel in temp_widget.panels.values():
            self.stop_index.append(len(panel.xdata))
        for panel in temp_widget.panels.values():
            header = "\t".join(["Time (sec)", "Temperature (K)", "Heater (%)", "Gas flow (%)\nStart from {}".format(time.strftime("%Y-%m-%d_%H-%M-%S"))])
            rel_time = np.copy(panel.rel_time[self.start_index[i]:self.stop_index[i]])
            rel_time = rel_time - np.ones(len(rel_time))*rel_time[0]
            data_matrix = np.concatenate(
                (
                    rel_time[:, np.newaxis],
                    panel.ydata_tmpr[self.start_index[i]:self.stop_index[i], np.newaxis],
                    panel.ydata_htr[self.start_index[i]:self.stop_index[i], np.newaxis],
                    panel.ydata_gflw[self.start_index[i]:self.stop_index[i], np.newaxis],
                ),
                axis=1,
            )
            # noinspection PyTypeChecker
            i += 1
            np.savetxt(self.path_indicator.text(), data_matrix, delimiter="\t", header=header, fmt="%f")

    def log_worklist(self):
        filename = bruker_widget.data + "//" + datetime.now().strftime("%Y%m%d_%H%M%S_")+"experimentLog.txt"
        file = open(filename, "w")
        file.write(datetime.now().strftime("%Y/%m/%d %H:%M:%S")+"\n")
        file.write("background pos: {} {} {}\n".format(bruker_widget.background_pos[0][0], bruker_widget.background_pos[0][1], bruker_widget.background_pos[0][2]))
        for i in range(len(bruker_widget.sample_pos)):
            file.write("sample{} pos: {} {} {}\n".format(i+1, bruker_widget.sample_pos[i][0], bruker_widget.sample_pos[i][1], bruker_widget.sample_pos[i][2]))
        file.write("reference pos: {} {} {}\n".format(camera_widget.x_reference, camera_widget.y_reference, camera_widget.z_reference))
        file.write("reference offset: {} {} {}\n".format(camera_widget.x_offset, camera_widget.y_offset, camera_widget.z_offset))
        index1 = 0
        index2 = 0
        sample = ""
        angle = ""
        log1 = []
        log2 = []
        for command in self.commands:
            if isinstance(command, BrukerCommand):
                if command.mode != 1:
                    if command.data_name == bruker_widget.data_name:
                        log1.append([index1, sample, angle])
                        index1 += 1
                    elif command.data_name == bruker_widget.data_name2:
                        log2.append([index2, sample, angle])
                        index2 += 1
            elif isinstance(command, NewportCommand) or isinstance(command, ThorlabsCommand):
                angle = "{}deg".format(command.angle)
            if isinstance(command, TranCommand):
                for i in range(len(bruker_widget.sample_pos)):
                    if command.x == bruker_widget.sample_pos[i][0] and command.y == bruker_widget.sample_pos[i][1] and command.z == bruker_widget.sample_pos[i][2]:
                        sample = "sample{}".format(i+1)
        if len(log1) > 0:
            file.write("Filename1: {}\n".format(bruker_widget.data + "/" + bruker_widget.data_name))
            file.write("XPM1: {}\n".format(bruker_widget.XPM))
            for l1 in log1:
                file.write("{}\t{}\t{}\n".format(l1[0], l1[1], l1[2]))
        if len(log2) > 0:
            file.write("Filename2: {}\n".format(bruker_widget.data + "/" + bruker_widget.data_name2))
            file.write("XPM2: {}\n".format(bruker_widget.XPM2))
            for l2 in log2:
                file.write("{}\t{}\t{}\n".format(l2[0], l2[1], l2[2]))
        file.close()

        return filename

    @pyqtSlot()
    def emitCommandStarted(self):
        time.sleep(1)  # 1 second delay to make sure command starts
        #instruments.zi_widget.pausePlot()  # stop recording data while temperature or rotator is changed
        self.command_started.emit()

    #@pyqtSlot()
    #def resumePlot(self):
    #    instruments.zi_widget.resumePlot()

    def runCommands(self):
        if self.save_ch.isChecked() and self.path_indicator.text() == "":
            QMessageBox.warning(self.main_window, "Mercury Error", "You haven't claimed a legal path to store Mercury logging files!")
            return
        #        self.threads = [] #list of threads
        # create a copy of self.commands called self.commands_copy
        self.commands_copy = [command.copy() for command in self.commands]

        if self.reminder:
            bruker_control_widget.set_IR()
            # QMessageBox.information(self.main_window, "Reminder", "Please make sure Bruker is in measurement mode!")
            QTest.qWait(5000)
            bruker_control_widget.illumination_sb.setValue(0)
            bruker_control_widget.set_illumination2()
            self.reminder = False

        # disable buttons until commands are finished
        for button in self.buttons:
            button.setEnabled(False)

        self.save_ch.setEnabled(False)

        if self.save_ch.isChecked():
            self.call_temp_saving()

        if self.log_cb.isChecked():
            self.worklist_log_name = self.log_worklist()

        for i in range(len(self.commands)):
            # append a new thread to self.threads, then move the command to that thread
            # when the command is finished (emits its finished signal), quit the thread
            command = self.commands[i]
        #            self.threads.append(QThread())
        #            command.moveToThread(self.threads[i])
        #            command.finished.connect(self.threads[i].quit, Qt.DirectConnection)

        # connect commands to functions which will emit signals back to the command object
        # to tell the program that the command has been executed so that the program can
        # start checking when the command is finished
        #            try: #allows program to do a scan if needed by the command
        #                command.scan_ready.connect(self.executeScan)
        #            except AttributeError:
        #                pass
        #            try:
        #                command.rotator_ready.connect(self.emitCommandStarted)
        #                command.resume_plot.connect(self.resumePlot)
        #            except AttributeError:
        #                pass
        #            try:
        #                command.cryostat_ready.connect(self.emitCommandStarted)
        #                command.resume_plot.connect(self.resumePlot)
        #            except AttributeError:
        #                pass

        # for each command, when the thread which has the command is started, the command will
        # execute using the execute function specified in its class
        # when the thread is finished, call the function runNextCommand to run the command in
        # the next thread in self.threads
        #            self.threads[i].started.connect(command.execute)
        #            self.threads[i].finished.connect(self.runNextCommand, Qt.DirectConnection)

        # signal so that while loop starts after the command has actually started
        # starts after scan_ready, rotator_ready, or crysotat_ready is emitted
        #            self.command_started.connect(command.checkIfDone)

        # run first command
        self.i = -1
        self.runNextCommand()

    @pyqtSlot()
    def runNextCommand(self):
        self.i += 1
        if self.i < len(self.commands):  # call next command if there is one
            self.progressBar.setValue(int((self.i)/len(self.commands)*100))
            self.thread = QThread()
            self.commands[self.i].moveToThread(self.thread)
            self.commands[self.i].finished.connect(self.thread.quit)

            # connect commands to functions which will emit signals back to the command object
            # to tell the program that the command has been executed so that the program can
            # start checking when the command is finished
            try:
                self.commands[self.i].rotator_ready.connect(self.emitCommandStarted)
                #self.commands[self.i].resume_plot.connect(self.resumePlot)
            except AttributeError:
                pass
            try:
                self.commands[self.i].thor_ready.connect(self.emitCommandStarted)
                #self.commands[self.i].resume_plot.connect(self.resumePlot)
            except AttributeError:
                pass
            try:
                self.commands[self.i].mercury_ready.connect(self.emitCommandStarted)
                #self.commands[self.i].resume_plot.connect(self.resumePlot)
            except AttributeError:
                pass
            try:
                self.commands[self.i].Tango_ready.connect(self.emitCommandStarted)
                #self.commands[self.i].resume_plot.connect(self.resumePlot)
            except AttributeError:
                pass
            try:
                self.commands[self.i].Bruker_ready.connect(self.emitCommandStarted)
                #self.commands[self.i].resume_plot.connect(self.resumePlot)
            except AttributeError:
                pass
            try:
                self.commands[self.i].keithley_ready.connect(self.emitCommandStarted)
                #self.commands[self.i].resume_plot.connect(self.resumePlot)
            except AttributeError:
                pass

            # when the thread (which contains the command) is started, the command will
            # execute using the execute function specified in its class
            # when the thread is finished, call the function runNextCommand to run the command in
            # the next thread in self.threads
            self.thread.started.connect(self.commands[self.i].execute)
            self.thread.finished.connect(self.runNextCommand)

            # signal so that while loop starts after the command has actually started
            # starts after scan_ready, rotator_ready, or crysotat_ready is emitted
            self.command_started.connect(self.commands[self.i].checkIfDone)

            self.thread.start()

            # if self.i > 0:
            #     data_recording_widget.recordData(dialog=False)
        else:  # otherwise clear self.threads and show that commands are finished
            #            self.threads.clear()
            self.progressBar.setValue(100)
            if self.save_ch.isChecked():
                self.stop_temp_saving()
            if self.log_cb.isChecked():
                with open(self.worklist_log_name, "a") as f:
                    f.write(datetime.now().strftime("%Y/%m/%d %H:%M:%S")+"\n")
                # test
                screenshot = temp_widget.grab()
                screenshot.save(self.worklist_log_name[:-4] + ".png")
            self.commands = self.commands_copy  # set self.commands to commands_copy because commands are now in different threads
            for button in self.buttons:  # enable all buttons again
                button.setEnabled(True)
            self.save_ch.setEnabled(True)
            QMessageBox.information(self, 'Run Commands', 'Finished running commands.')
            #data_recording_widget.recordData(dialog=True)
            self.progressBar.setValue(0)

    def removeLast(self):
        try:
            # remove last command from list of commands by popping
            self.commands.pop()

            # update the display
            oldText = self.command_display.text()
            newText = oldText[:oldText.rfind('<li>')] + '</ol>'
            self.command_display.setText(newText)
        except IndexError:  # do nothing if list was already empty
            pass

    def clearAll(self):
        # clear the list of commands
        self.commands.clear()

        # reset text of display to an empty list
        self.command_display.setText('<b>Commands:</b><ol style="margin:0px;"></ol>')

    def stop_commands(self):
        if self.i < 0:
            return
        if len(self.commands) > 0 and self.i < len(self.commands):
            current_command = self.commands[self.i]
            self.i = len(self.commands)
            current_command.finished.emit()
            if not isinstance(current_command, SetTemperatureCommand):
                QMessageBox.information(self.main_window, "Stop", "The worklist will stop after the current step is finished")

class NewportCommand(QObject):
    finished = pyqtSignal()
    rotator_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, rotr, angle, pause):
        super().__init__()
        self.main_window = main_window
        self.rotr = rotr
        self.angle = angle
        self.pause = pause

    def copy(self):
        return NewportCommand(self.main_window, self.rotr, self.angle, self.pause)

    def execute(self):
        try:
            if self.rotr == "Polarizer":
                pol_new_widget.abs_pos_sb.setValue(self.angle)
                pol_new_widget.abs_pos_sb.editingFinished.emit()
            else:
                ana_new_widget.abs_pos_sb.setValue(self.angle)
                ana_new_widget.abs_pos_sb.editingFinished.emit()

            self.rotator_ready.emit()

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Newport rotator is connected and enabled.')

    @pyqtSlot()
    def checkIfDone(self):
        try:
            while True:
                if self.rotr == "Polarizer":
                    ctrl_state = pol_new_widget.controller_states[instruments.rotr.query('1mm?')[3:].strip()]
                else:
                    ctrl_state = ana_new_widget.controller_states[instruments.rotr.query('1mm?')[3:].strip()]
                if ctrl_state.split(' ')[0] == 'READY':
                    self.resume_plot.emit()
                    QTest.qWait(self.pause * 1000)
                    self.finished.emit()
                    break

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Newport rotator is connected and enabled.')

class ThorlabsCommand(QObject):
    finished = pyqtSignal()
    thor_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, rotr, angle, pause):
        super().__init__()
        self.main_window = main_window
        self.rotr = rotr
        self.angle = angle
        self.pause = pause

    def copy(self):
        return ThorlabsCommand(self.main_window, self.rotr, self.angle, self.pause)

    def execute(self):
        try:
            if self.rotr == "Polarizer":
                pol_thor_widget.abs_pos_sb.setValue(self.angle)
                pol_thor_widget.abs_pos_sb.editingFinished.emit()
            else:
                ana_thor_widget.abs_pos_sb.setValue(self.angle)
                ana_thor_widget.abs_pos_sb.editingFinished.emit()

            self.thor_ready.emit()

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Thorlabs rotator is connected and enabled.')

    @pyqtSlot()
    def checkIfDone(self):
        try:
            QTest.qWait(10)
            while True:
                if self.rotr == "Polarizer":
                    if pol_thor_widget.ready:
                        self.resume_plot.emit()
                        QTest.qWait(self.pause * 1000)
                        self.finished.emit()
                        break
                else:
                    if ana_thor_widget.ready:
                        self.resume_plot.emit()
                        QTest.qWait(self.pause * 1000)
                        self.finished.emit()
                        break

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Thorlabs rotator is connected and enabled.')


class SetTemperatureCommand(QObject):
    finished = pyqtSignal()
    mercury_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, temp, un, duration, pause, auto_xyz, illumination):
        super().__init__()
        self.main_window = main_window
        self.temp = temp
        self.un = un
        self.duration = duration
        self.pause = pause
        self.auto_xyz = auto_xyz
        self.illumination = illumination
        self.stability = 0

    def copy(self):
        return SetTemperatureCommand(self.main_window, self.temp, self.un, self.duration, self.pause, self.auto_xyz, self.illumination)

    def execute(self):
        try:
        #if instruments.cryostat is None:
            #    QMessageBox.warning(self.main_window, 'Connection Error', 'Not connected to cryostat.')
            #    return
            next(iter(temp_widget.panels.values())).temperature.loop_tset = self.temp

            if self.auto_xyz:
                pythoncom.CoInitialize()
                self.directCommand = win32com.client.Dispatch("OpusCMD334.DirectCommand")
                # set visible
                self.directCommand.SendDirect("MOT56 =2", True)
                QTest.qWait(5000)
                # set illumination to self.illumination
                self.directCommand.SendDirect("MOT56 ={}".format(100+self.illumination), True)

                self.pos_timer = QTimer()
                self.pos_timer.timeout.connect(camera_widget.auto_xyz)
                self.pos_timer.start(20000)

            self.mercury_ready.emit()

        except Exception as e:
           QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e))

    @pyqtSlot()
    def checkIfDone(self):
        # create timer to check temperature every 3 seconds because socket will timeout
        # if there are too many requests
        self.timer = QTimer()
        self.timer.timeout.connect(self.delayedCheckIfDone)
        self.timer.start(1000)

    def delayedCheckIfDone(self):
        try:
                current_temp = next(iter(temp_widget.panels.values())).temperature.temp[0]

                if current_temp == -0.1:
                    time.sleep(1)

                if round(self.temp, 2) - round(self.un, 2) <= round(current_temp, 2) <= round(self.temp, 2) + round(self.un):
                    self.stability += 1

                if self.stability > self.duration:
                    self.resume_plot.emit()
                    QTest.qWait(self.pause * 1000)
                    if self.auto_xyz:

                        # set IR
                        self.directCommand.SendDirect("MOT56 =1", True)
                        QTest.qWait(5000)
                        # set illumination to 0
                        self.directCommand.SendDirect("MOT56 =100", True)
                    self.finished.emit()

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e))

        except socket.timeout:
            time.sleep(1)

class KeithleyCommand(QObject):
    finished = pyqtSignal()
    keithley_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, device, mode, ramp_speed, step, vi, points, pause):
        super().__init__()
        self.main_window = main_window
        self.device = device
        self.mode = mode
        self.ramp_speed = ramp_speed
        self.step = step
        self.vi = vi
        self.points = points
        self.pause = pause
        self.ready = False

    def copy(self):
        return KeithleyCommand(self.main_window, self.device, self.mode, self.ramp_speed, self.step, self.vi, self.points, self.pause)

    def execute(self):
        try:
            ramp_step = self.points
            ramp_pause = abs(self.step)/self.ramp_speed/ramp_step
            if self.mode == "Voltage":
                if self.device == 1:
                    keithley_widget.keithley1.ramp_to_voltage(self.vi, ramp_step, ramp_pause)
                elif self.device == 2:
                    keithley_widget.keithley2.ramp_to_voltage(self.vi, ramp_step, ramp_pause)
            else:
                keithley_widget.updateIVR1.Timer.stop()
                if self.device == 1:
                    keithley_widget.keithley1.ramp_to_current(self.vi, ramp_step, ramp_pause)
                elif self.device == 2:
                    keithley_widget.keithley2.ramp_to_current(self.vi, ramp_step, ramp_pause)
            self.ready = True
            self.keithley_ready.emit()

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Keithley is connected and a source current or voltage is enabled.')

    @pyqtSlot()
    def checkIfDone(self):
        try:
            QTest.qWait(10)
            while True:
                if self.ready:
                    self.resume_plot.emit()
                    QTest.qWait(self.pause * 1000)
                    self.finished.emit()
                    break

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Keithley is connected and a source current or voltage is enabled.')

class DoubleKeithleyCommand(QObject):
    finished = pyqtSignal()
    keithley_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, mode, ramp_speed1, step1, vi1, ramp_speed2, step2, vi2, points, pause):
        super().__init__()
        self.main_window = main_window
        self.mode = mode
        self.ramp_speed1 = ramp_speed1
        self.step1 = step1
        self.vi1 = vi1
        self.ramp_speed2 = ramp_speed2
        self.step2 = step2
        self.vi2 = vi2
        self.points = points
        self.pause = pause
        self.ready = False

    def copy(self):
        return DoubleKeithleyCommand(self.main_window, self.mode, self.ramp_speed1, self.step1, self.vi1, self.ramp_speed2, self.step2, self.vi2, self.points, self.pause)

    def execute(self):
        try:
            ramp_step = self.points
            ramp_pause1 = abs(self.step1)/self.ramp_speed1/ramp_step
            ramp_pause2 = abs(self.step2)/self.ramp_speed2/ramp_step
            # keithley_widget.updateIVR1.sleep(int(max(ramp_pause1, ramp_pause2))+5)
            # keithley_widget.updateIVR2.sleep(int(max(ramp_pause1, ramp_pause2))+5)
            for i in range(ramp_step):
                print(i)
                target1 = self.vi1-self.step1/1e3/ramp_step*(ramp_step-i-1)
                target2 = self.vi2-self.step2/1e3/ramp_step*(ramp_step-i-1)
                if target1 < 0:
                    target1 = 0
                if target2 < 0:
                    target2 = 0
                if self.mode == "Voltage":
                    keithley_widget.keithley1.ramp_to_voltage(target1, 2, ramp_pause1/4)
                    keithley_widget.keithley2.ramp_to_voltage(target2, 2, ramp_pause2/4)
                elif self.mode == "Current":
                    keithley_widget.keithley1.ramp_to_current(target1, 2, ramp_pause1/4)
                    keithley_widget.keithley2.ramp_to_current(target2, 2, ramp_pause2/4)
            self.ready = True
            self.keithley_ready.emit()

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Keithley is connected and a source current or voltage is enabled.')

    @pyqtSlot()
    def checkIfDone(self):
        try:
            QTest.qWait(10)
            while True:
                if self.ready:
                    self.resume_plot.emit()
                    QTest.qWait(self.pause * 1000)
                    self.finished.emit()
                    break

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Keithley is connected and a source current or voltage is enabled.')


class TranCommand(QObject):
    finished = pyqtSignal()
    Tango_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, x, y, z, auto_xyz, pause, mode):
        super().__init__()
        self.main_window = main_window
        self.x = x
        self.y = y
        self.z = z
        self.auto_xyz = auto_xyz
        self.pause = pause
        self.mode = mode

    def copy(self):
        return TranCommand(self.main_window, self.x, self.y, self.z, self.auto_xyz, self.pause, self.mode)

    def execute(self):
        try:
            if self.auto_xyz:
                self.x += camera_widget.x_offset
                self.y += camera_widget.y_offset
                self.z += camera_widget.z_offset
            # absolute
            if self.mode == 1:
                tran_widget.Tango.LSX_MoveAbs(tran_widget.LSID, c_double(self.x), c_double(self.y), c_double(self.z), c_double(0), c_bool(False))
            elif self.mode == 2:
                tran_widget.Tango.LSX_MoveRel(tran_widget.LSID, c_double(self.x), c_double(self.y), c_double(self.z), c_double(0), c_bool(False))

            self.Tango_ready.emit()

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure translator is connected and enabled.')

    @pyqtSlot()
    def checkIfDone(self):
        try:
            while True:
                x = tran_widget.get_x_pos()
                y = tran_widget.get_y_pos()
                z = tran_widget.get_z_pos()
                QTest.qWait(10)
                if x == tran_widget.get_x_pos() and y == tran_widget.get_y_pos() and z == tran_widget.get_z_pos():
                    self.resume_plot.emit()
                    QTest.qWait(self.pause * 1000)
                    self.finished.emit()
                    break

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure translator is connected and enabled.')

class BrukerCommand(QObject):
    finished = pyqtSignal()
    Bruker_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, xpm_path, data_path, data_name, pause, mode):
        super().__init__()
        self.main_window = main_window
        self.mode = mode
        self.xpm_path = xpm_path
        self.xpm_name = os.path.basename(xpm_path)
        self.data_path = data_path
        self.data_name = data_name
        self.pause = pause
        self.busy = True

    def copy(self):
        return BrukerCommand(self.main_window, self.xpm_path, self.data_path, self.data_name, self.pause, self.mode)

    def execute(self):
        try:
            in_Opus = False
            for proc in psutil.process_iter(["pid", "name", "username"]):
                if proc.info["name"] == "opus.exe":
                    in_Opus = True
            if not in_Opus:
                start = win32com.client.Dispatch("OpusCMD334.StartOpus")
                exePath = r"C:\Program Files\Bruker\OPUS_8.5.29\opus.exe"
                password = "OPUS"
                start.StartOpus(exePath, password)
            if self.mode == 1:
                tkbkg = win32com.client.Dispatch("OpusCMD334.TakeBackground")
                result = tkbkg.TakeReference(self.xpm_path.replace("/", "\\"))
            else:
                tkbsmp = win32com.client.Dispatch("OpusCMD334.TakeSample")
                index = self.xpm_path.find(self.xpm_name)
                self.xpm_path = self.xpm_path[:index-1]
                result = tkbsmp.TakeSample(self.xpm_name, self.xpm_path, self.data_name, self.data_path, True)
                tkblf = win32com.client.Dispatch("OpusCMD334.LoadFile")
                list = glob.glob(self.data_path + r"\*")
                new_name = max(list, key=os.path.getctime).split("\\")[-1]
                tkblf.Load(new_name, self.data_path)
            if result:
                self.busy = False
            else:
                QMessageBox.warning(self.main_window, 'Bruker', 'Fail to scan the sample or background')
                print("Error! Samples are not analyzed correctly!")
                control_widget.stop_commands()

            self.Bruker_ready.emit()

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure ALL FILES are CORRECT.')

    @pyqtSlot()
    def checkIfDone(self):
        try:
            while True:
                if not self.busy:
                    self.resume_plot.emit()
                    QTest.qWait(self.pause * 1000)
                    self.finished.emit()
                    break

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Bruker is connected and enabled.')

class BrukerSaveCommand(QObject):
    finished = pyqtSignal()
    Bruker_ready = pyqtSignal()
    resume_plot = pyqtSignal()

    def __init__(self, main_window, macro_path, data_path, data_name, title, vmin, vmax, save_raw, keep_csv, freq, angle_fit, angle_list):
        super().__init__()
        self.main_window = main_window
        self.macro_path = macro_path
        self.data_path = data_path
        self.data_name = data_name
        self.title = title
        self.vmin = vmin
        self.vmax = vmax
        self.save_raw = save_raw
        self.keep_csv = keep_csv
        self.freq_of_interest = freq
        self.angle_fit = angle_fit
        self.angle_list = angle_list
        self.path_destination = self.data_path + "\\" + self.data_name + "_csv"
        self.busy = True

    def copy(self):
        return BrukerSaveCommand(self.main_window, self.macro_path, self.data_path, self.data_name, self.title, self.vmin, self.vmax, self.save_raw, self.keep_csv, self.freq_of_interest, self.angle_fit, self.angle_list)

    def execute(self):
        try:
            in_Opus = False
            for proc in psutil.process_iter(["pid", "name", "username"]):
                if proc.info["name"] == "opus.exe":
                    in_Opus = True
            if not in_Opus:
                start = win32com.client.Dispatch("OpusCMD334.StartOpus")
                exePath = r"C:\Program Files\Bruker\OPUS_8.5.29\opus.exe"
                password = "OPUS"
                start.StartOpus(exePath, password)
            macro = win32com.client.Dispatch("OpusCMD334.RunMacro")
            if not os.path.exists(self.path_destination):
                os.makedirs(self.path_destination)
            input = self.data_path + "," + self.data_name + ".*" + "," + self.path_destination
            result = macro.RunMacro(self.macro_path, input)
            macro_ID = macro.MacroID
            ready = False
            while ready != True:
                macro.MacroReady(macro_ID)
                ready = macro.MacroDone
            QTest.qWait(500)
            csv = os.listdir(self.path_destination)
            csv_length = len(csv)
            file = open(self.path_destination + "\\" + self.data_name + ".0.csv", "r")
            length = 0
            for line_index, line_str in enumerate(file):
                length += 1
            file.close()
            if not self.save_raw:
                data = np.zeros((csv_length, length))
                for i in range(csv_length):
                    file = open(self.path_destination + "\\" + self.data_name + ".{}.csv".format(i), "r")
                    for line_index, line_str in enumerate(file):
                        data[i, line_index] = float(line_str.split(",")[1].split("\n")[0])
                    file.close()
                freq = np.zeros(length)
                file = open(self.path_destination + "\\" + self.data_name + ".0.csv", "r")
                for line_index, line_str in enumerate(file):
                    freq[line_index] = float(line_str.split(",")[0])
                file.close()
            else:
                csv_length = int(csv_length/3)
                data = np.zeros((csv_length, length))
                for i in range(csv_length):
                    file = open(self.path_destination + "\\" + self.data_name + ".{}.csv".format(i), "r")
                    for line_index, line_str in enumerate(file):
                        data[i, line_index] = float(line_str.split(",")[1].split("\n")[0])
                    file.close()
                freq = np.zeros(length)
                file = open(self.path_destination + "\\" + self.data_name + ".0.csv", "r")
                for line_index, line_str in enumerate(file):
                    freq[line_index] = float(line_str.split(",")[0])
                file.close()
                # raw RSC spectra data
                file = open(self.path_destination + "\\" + "RSC_" + self.data_name + ".0.csv", "r")
                length = 0
                for line_index, line_str in enumerate(file):
                    length += 1
                file.close()
                data_RSC = np.zeros((csv_length, length))
                for i in range(csv_length):
                    file = open(self.path_destination + "\\" + "RSC_" + self.data_name + ".{}.csv".format(i), "r")
                    for line_index, line_str in enumerate(file):
                        data_RSC[i, line_index] = float(line_str.split(",")[1].split("\n")[0])
                    file.close()
                freq_RSC = np.zeros(length)
                file = open(self.path_destination + "\\" + "RSC_" + self.data_name + ".0.csv", "r")
                for line_index, line_str in enumerate(file):
                    freq_RSC[line_index] = float(line_str.split(",")[0])
                file.close()
                # raw SSC spectra data
                file = open(self.path_destination + "\\" + "SSC_" + self.data_name + ".0.csv", "r")
                length = 0
                for line_index, line_str in enumerate(file):
                    length += 1
                file.close()
                data_SSC = np.zeros((csv_length, length))
                for i in range(csv_length):
                    file = open(self.path_destination + "\\" + "SSC_" + self.data_name + ".{}.csv".format(i), "r")
                    for line_index, line_str in enumerate(file):
                        data_SSC[i, line_index] = float(line_str.split(",")[1].split("\n")[0])
                    file.close()
                freq_SSC = np.zeros(length)
                file = open(self.path_destination + "\\" + "SSC_" + self.data_name + ".0.csv", "r")
                for line_index, line_str in enumerate(file):
                    freq_SSC[line_index] = float(line_str.split(",")[0])
                file.close()

            if len(self.angle_list) == csv_length:
                angles = np.array(self.angle_list)
                arg = np.argsort(angles)
                angles = angles[arg]
                data = np.array(data)[arg]
            else:
                angles = np.arange(0,csv_length,1)

            if csv_length > 1 and len(set(angles)) > 1:
                if not self.angle_fit:
                    fig, axs = plt.subplots(constrained_layout=1)
                    # 2D color plot
                    min_index = 0
                    max_index = len(freq)
                    # for i in range(len(freq)):
                    #     if freq[i] < 8500:
                    #         min_index = i+1
                    #     elif freq[i] > 22500:
                    #         max_index = i
                    #         break
                    freq = freq[min_index:max_index]
                    ff, aa = np.meshgrid(freq,angles)
                    img = axs.pcolormesh(ff, aa, data[:, min_index:max_index], vmin=self.vmin, vmax=self.vmax, shading='auto')
                    axs.set(xlabel=r'Frequency (cm$^{-1}$)')
                    axs.set_title(self.title)
                    fig.colorbar(img, ax=axs, shrink=0.6)
                    # for i in range(csv_length):
                    #     axs.plot(data[0], data[i+1], "-", linewidth=1, label="{}".format(i))
                    # axs.legend()
                    # plt.tight_layout()
                    plt.savefig(self.data_path + "\\" + self.data_name + "_combined.png")
                else:
                    fig, axs = plt.subplots(ncols=2, figsize=(10, 5))
                    # 2D color plot
                    min_index = 0
                    max_index = len(freq)
                    # for i in range(len(freq)):
                    #     if freq[i] < 8500:
                    #         min_index = i+1
                    #     elif freq[i] > 22500:
                    #         max_index = i
                    #         break
                    freq = freq[min_index:max_index]
                    ff, aa = np.meshgrid(freq,angles)
                    img = axs[0].pcolormesh(ff, aa, data[:, min_index:max_index], vmin=self.vmin, vmax=self.vmax, shading='auto')
                    axs[0].axvline(x=self.freq_of_interest, linestyle="--", color="red")
                    axs[0].set_xlabel(r'Frequency (cm$^{-1}$)', fontsize=12)
                    axs[0].set_title(self.title)
                    fig.colorbar(img, ax=axs[0], shrink=0.6)
                    # for i in range(csv_length):
                    #     axs.plot(data[0], data[i+1], "-", linewidth=1, label="{}".format(i))
                    # axs.legend()
                    # plt.tight_layout()
                    freq_of_interest_index = np.argmin(np.abs(np.array(freq)-self.freq_of_interest))
                    axs[1].scatter(angles, data[:, freq_of_interest_index], color="r")
                    angle_fit_result = self.fit_angle_dependence([0, 0, 0], np.array(angles), data[:, freq_of_interest_index])
                    axs[1].plot(angles, self.fitfunc(angle_fit_result, angles), color="#000000")
                    axs[1].set_title('p0 = %.3f, p1 = %.3f, rotation angle = %f degs' %(angle_fit_result[0],angle_fit_result[1],angle_fit_result[1]*180/np.pi), fontsize=12)
                    axs[1].set_xlabel(r'Angle (deg)', fontsize=12)
                    plt.savefig(self.data_path + "\\" + self.data_name + "_combined.png")

            data = data.transpose()
            final_txt = open(self.data_path + "\\" + self.data_name + "_combined.txt", "w")
            final_txt.write("Wavenumber")
            for i in range(csv_length):
                if len(self.angle_list) == csv_length:
                    final_txt.write(",%.2f" % angles[i])
                else:
                    final_txt.write(",{}".format(angles[i]))
            final_txt.write("\n")
            for i in range(len(freq)):
                final_txt.write("{},".format(freq[i]))
                for j in range(csv_length):
                    final_txt.write("{}".format(data[i, j]))
                    if j != csv_length-1:
                        final_txt.write(",")
                    else:
                        final_txt.write("\n")
            final_txt.close()

            if self.save_raw:
                if len(freq_SSC) < len(freq_RSC):
                    min = freq_RSC.tolist().index(freq_SSC[0])
                    max = freq_RSC.tolist().index(freq_SSC[-1])
                    if min >= 0 and max >= 0:
                        freq_RSC = freq_RSC[min: max+1]
                        data_RSC = data_RSC[:, min: max+1]
                else:
                    min = freq_SSC.tolist().index(freq_RSC[0])
                    max = freq_SSC.tolist().index(freq_RSC[-1])
                    if min >= 0 and max >= 0:
                        freq_SSC = freq_SSC[min: max+1]
                        data_SSC = data_SSC[:, min: max+1]
                if len(self.angle_list) == csv_length:
                    data_RSC = np.array(data_RSC)[arg]
                data_RSC = data_RSC.transpose()
                final_txt = open(self.data_path + "\\" + "RSC_" + self.data_name + "_combined.txt", "w")
                final_txt.write("Wavenumber")
                for i in range(csv_length):
                    if len(self.angle_list) == csv_length:
                        final_txt.write(",%.2f" % angles[i])
                    else:
                        final_txt.write(",{}".format(angles[i]))
                final_txt.write("\n")
                for i in range(len(freq_RSC)):
                    final_txt.write("{},".format(freq_RSC[i]))
                    for j in range(csv_length):
                        final_txt.write("{}".format(data_RSC[i, j]))
                        if j != csv_length-1:
                            final_txt.write(",")
                        else:
                            final_txt.write("\n")
                final_txt.close()
                if len(self.angle_list) == csv_length:
                    data_SSC = np.array(data_SSC)[arg]
                data_SSC = data_SSC.transpose()
                final_txt = open(self.data_path + "\\" + "SSC_" + self.data_name + "_combined.txt", "w")
                final_txt.write("Wavenumber")
                for i in range(csv_length):
                    final_txt.write(",{}".format(angles[i]))
                final_txt.write("\n")
                for i in range(len(freq_SSC)):
                    if len(self.angle_list) == csv_length:
                        final_txt.write(",%.2f" % angles[i])
                    else:
                        final_txt.write(",{}".format(angles[i]))
                    for j in range(csv_length):
                        final_txt.write("{}".format(data_SSC[i, j]))
                        if j != csv_length-1:
                            final_txt.write(",")
                        else:
                            final_txt.write("\n")
                final_txt.close()

            if not self.keep_csv:
                shutil.rmtree(self.path_destination)

            if result:
                self.busy = False
            else:
                QMessageBox.warning(self.main_window, 'Bruker', 'Fail to scan the sample or background')
                print("Error! Samples are not analyzed correctly!")
            self.Bruker_ready.emit()

        except Exception as e:
            print(e)
            # QMessageBox.warning(self.main_window, 'Error', 'Error: {}'.format(e) +
            #                     '\nMake sure ALL FILES are CORRECT.')
            return

    def fitfunc(self, p, x):
        """
        x = angle in degrees
        p = fitting parameters
        p[0]: Intensity ratio
        p[1]: Rotation angle, theta_F
        p[2]: offset from leaky polarizer
        """
        xrad = [i*np.pi/180 for i in x]
        return p[0]*pow(np.cos(xrad-p[1]),2) + p[2]

    def resid(self, p, x, y):
        return ((y - self.fitfunc(p, x))**2)

    def fit_angle_dependence(self, init, x, y):
        # initial guess for paras.
        res,flag = optimize.leastsq(self.resid, init, args=(x, y), maxfev=50000)
        [p0,p1,p2] = res
        # print('p0 = %.3f, p1 = %.3f, rotation angle = %f degs' %(p0,p1,p1*180/np.pi))
        return [p0,p1,p2]

    @pyqtSlot()
    def checkIfDone(self):
        try:
            while True:
                if not self.busy:
                    self.resume_plot.emit()
                    self.finished.emit()
                    break

        except Exception as e:
            QMessageBox.warning(self.main_window, 'Error', 'Error: ' + str(e) +
                                '\nMake sure Bruker is connected and enabled.')

"""
class DataRecordingWidget(QFrame):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.initUI()
        self.setFixedHeight(230)

    def initUI(self):
        # create main grid to organize layout
        main_grid = QGridLayout()
        main_grid.setSpacing(10)
        self.setLayout(main_grid)

        # data recording text label
        data_recording_lbl = QLabel('<b>Data Recording</b>')
        main_grid.addWidget(data_recording_lbl, 0, 0, 1, 3)

        # rotator data recording
        self.rotator_lbl = QLabel('Rotator')
        self.rotator_cb = QCheckBox()
        self.rotator_le = QLineEdit()
        self.rotator_le.setPlaceholderText('File name')
        main_grid.addWidget(self.rotator_lbl, 4, 0)
        main_grid.addWidget(self.rotator_cb, 4, 1)
        main_grid.addWidget(self.rotator_le, 4, 2)

        # combined data recording
        self.combined_lbl = QLabel('Combined')
        self.combined_cb = QCheckBox()
        self.combined_le = QLineEdit()
        self.combined_le.setPlaceholderText('File name')
        main_grid.addWidget(self.combined_lbl, 5, 0)
        main_grid.addWidget(self.combined_cb, 5, 1)
        main_grid.addWidget(self.combined_le, 5, 2)

        # save data button
        save_data_btn = QPushButton('Save Data')
        save_data_btn.setFixedWidth(150)
        save_data_btn.clicked.connect(self.recordData)
        main_grid.addWidget(save_data_btn, 6, 0, 1, 3, Qt.AlignLeft)

        spacer = QVBoxLayout()
        spacer.addStretch()
        main_grid.addLayout(spacer, 7, 0, 1, 3)

    def recordData(self, dialog=True):
        '''Record data when main window is closed'''
        data_recorded = False

        if self.rotator_cb.isChecked():
            self.recordRotatorData()
            data_recorded = True
        if self.combined_cb.isChecked():
            self.recordCombinedData()
            data_recorded = True

        if dialog and data_recorded:
            QMessageBox.information(self, 'Confirmation', 'The data has been saved')

    def recordRotatorData(self):
        # get filename from line edit and add .txt extension, then create file
        filename = self.rotator_le.text() + '.txt'
        f = open(filename, 'w+')

        # write header for the file
        f.write('Angle(deg)\n')

        # get data from crysotat widget
        angle_data = rotr_widget.angle_data

        # write each row of data
        for angle in angle_data:
            f.write('{}\n'.format(angle))

        # close file
        f.close()

        # add checkmark to cryostat label to show that data has been recorded
        self.rotator_lbl.setText(u'Rotator \u2705')

    def recordCombinedData(self):
        # get filename from line edit and add .txt extension, then create file
        filename = self.combined_le.text() + '.txt'
        f = open(filename, 'w+')

        # write header for the file
        f.write('Time(s),V0,V2,V3,Platform Temperature(K),Sample Temperature(K)' +
                ',User Temperature(K),QCL Wavenumber(cm^-1)\n')

        data_length = instruments.zi_widget.data_length

        # get data from crysotat widget
        time_data = instruments.zi_widget.time_data[0]
        volt_data = instruments.zi_widget.volt_data
        temp_data = instruments.zi_widget.temp_data
        qcl_wnum_data = instruments.zi_widget.qcl_wnum
        # rotator_data = instruments.zi_widget.   #20190920 add rotator to saved data
        #        qcl_curr_data = instruments.zi_widget.qcl_curr
        #        pem_wlength_data = instruments.zi_widget.pem_wlength
        #        pem_wnum_data = instruments.zi_widget.pem_wnum

        # write each row of data
        for i, data in enumerate(zip(time_data, volt_data[0], volt_data[1], volt_data[2])):
            plat_temp = temp_data[0][i // data_length]
            samp_temp = temp_data[1][i // data_length]
            user_temp = temp_data[2][i // data_length]
            qcl_wnum = qcl_wnum_data[i // data_length]
            #            qcl_curr = qcl_curr_data[i//data_length]
            #            pem_wlength = pem_wlength_data[i//data_length]
            #            pem_wnum = pem_wnum_data[i//data_length]
            f.write('{:.4f},{:.8e},{:.8e},{:.8e},{:.2f},{:.2f},{:.2f},{:.1f}\n'.format(data[0], data[1], data[2],
                                                                                       data[3], plat_temp, samp_temp,
                                                                                       user_temp, qcl_wnum))

        # close file
        f.close()

        # add checkmark to cryostat label to show that data has been recorded
        self.combined_lbl.setText(u'Connected \u2705')
"""

class QDoubleSlider(QSlider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.decimals = 4
        self._max_int = 10 ** self.decimals

        super().setMinimum(0)
        super().setMaximum(self._max_int)

        self._min_value = 0.0
        self._max_value = 1.0

    @property
    def _value_range(self):
        return self._max_value - self._min_value

    def value(self):
        return float(super().value()) / self._max_int * self._value_range + self._min_value

    def setValue(self, value):
        super().setValue(int((value - self._min_value) / self._value_range * self._max_int))

    def setMinimum(self, value):
        if value > self._max_value:
            raise ValueError("Minimum limit cannot be higher than maximum")

        self._min_value = value
        self.setValue(self.value())

    def setMaximum(self, value):
        if value < self._min_value:
            raise ValueError("Minimum limit cannot be higher than maximum")

        self._max_value = value
        self.setValue(self.value())

    def setRange(self, minval, maxval):
        self.setMinimum(minval)
        self.setMaximum(maxval)

    def minimum(self):
        return self._min_value

    def maximum(self):
        return self._max_value

    def setDecimals(self, value):
        if type(value != int):
            raise ValueError('Number of decimals must be an int')
        else:
            self.decimals = value


# from https://github.com/nlamprian/pyqt5-led-indicator-widget/blob/master/LedIndicatorWidget.py
class QLedIndicator(QAbstractButton):
    scaledSize = 1000.0

    def __init__(self, color='green', parent=None):  # added a color option to use red or orange
        QAbstractButton.__init__(self, parent)

        self.setMinimumSize(24, 24)
        self.setCheckable(True)

        # prevent user from changing indicator color by clicking
        self.setEnabled(False)

        if color.lower() == 'red':
            self.on_color_1 = QColor(255, 0, 0)
            self.on_color_2 = QColor(192, 0, 0)
            self.off_color_1 = QColor(28, 0, 0)
            self.off_color_2 = QColor(128, 0, 0)
        elif color.lower() == 'orange':
            self.on_color_1 = QColor(255, 175, 0)
            self.on_color_2 = QColor(170, 115, 0)
            self.off_color_1 = QColor(90, 60, 0)
            self.off_color_2 = QColor(150, 100, 0)
        else:  # default to green if user does not give valid option
            self.on_color_1 = QColor(0, 255, 0)
            self.on_color_2 = QColor(0, 192, 0)
            self.off_color_1 = QColor(0, 28, 0)
            self.off_color_2 = QColor(0, 128, 0)

    def changeColor(self, color):
        '''change color by inputting a string only for red, orange, and green'''
        if color.lower() == 'red':
            self.on_color_1 = QColor(255, 0, 0)
            self.on_color_2 = QColor(192, 0, 0)
            self.off_color_1 = QColor(28, 0, 0)
            self.off_color_2 = QColor(128, 0, 0)
        elif color.lower() == 'orange':
            self.on_color_1 = QColor(255, 175, 0)
            self.on_color_2 = QColor(170, 115, 0)
            self.off_color_1 = QColor(90, 60, 0)
            self.off_color_2 = QColor(150, 100, 0)
        elif color.lower() == 'green':
            self.on_color_1 = QColor(0, 255, 0)
            self.on_color_2 = QColor(0, 192, 0)
            self.off_color_1 = QColor(0, 28, 0)
            self.off_color_2 = QColor(0, 128, 0)

        self.update()

    def resizeEvent(self, QResizeEvent):
        self.update()

    def paintEvent(self, QPaintEvent):
        realSize = min(self.width(), self.height())

        painter = QPainter(self)
        pen = QPen(Qt.black)
        pen.setWidth(1)

        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(realSize / self.scaledSize, realSize / self.scaledSize)

        gradient = QRadialGradient(QPointF(-500, -500), 1500, QPointF(-500, -500))
        gradient.setColorAt(0, QColor(224, 224, 224))
        gradient.setColorAt(1, QColor(28, 28, 28))
        painter.setPen(pen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPointF(0, 0), 500, 500)

        gradient = QRadialGradient(QPointF(500, 500), 1500, QPointF(500, 500))
        gradient.setColorAt(0, QColor(224, 224, 224))
        gradient.setColorAt(1, QColor(28, 28, 28))
        painter.setPen(pen)
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(QPointF(0, 0), 450, 450)

        painter.setPen(pen)
        if self.isChecked():
            gradient = QRadialGradient(QPointF(-500, -500), 1500, QPointF(-500, -500))
            gradient.setColorAt(0, self.on_color_1)
            gradient.setColorAt(1, self.on_color_2)
        else:
            gradient = QRadialGradient(QPointF(500, 500), 1500, QPointF(500, 500))
            gradient.setColorAt(0, self.off_color_1)
            gradient.setColorAt(1, self.off_color_2)

        painter.setBrush(gradient)
        painter.drawEllipse(QPointF(0, 0), 400, 400)

    @pyqtProperty(QColor)
    def onColor1(self):
        return self.on_color_1

    @onColor1.setter
    def onColor1(self, color):
        self.on_color_1 = color

    @pyqtProperty(QColor)
    def onColor2(self):
        return self.on_color_2

    @onColor2.setter
    def onColor2(self, color):
        self.on_color_2 = color

    @pyqtProperty(QColor)
    def offColor1(self):
        return self.off_color_1

    @offColor1.setter
    def offColor1(self, color):
        self.off_color_1 = color

    @pyqtProperty(QColor)
    def offColor2(self):
        return self.off_color_2

    @offColor2.setter
    def offColor2(self, color):
        self.off_color_2 = color

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # app.setStyleSheet("QLabel{font-size: 12pt;}")
    # app.setStyleSheet("QPushButton{font-size: 12pt;}")
    # app.setStyleSheet("QDoubleSpinBox{font-size: 12pt;}")
    # app.setStyleSheet("QSpinBox{font-size: 12pt;}")
    # app.setStyleSheet("QComboBox{font-size: 12pt;}")
    app.setFont(QFont('Times', 12))
    window = MainWindow()
    sys.exit(app.exec_())
