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