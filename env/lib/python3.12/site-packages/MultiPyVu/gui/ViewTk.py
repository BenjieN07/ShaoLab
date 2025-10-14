"""
View.py holds the code for a gui for MultiPyVu.Server

@author: djackson
"""


import io
import logging
import logging.handlers
import sys
import tkinter as tk
from enum import IntEnum, auto
from threading import Lock
from tkinter import font
try:
    from PIL import ImageTk, Image
except ImportError:
    msg = "Must import the PIL module.  Use:  \n"
    msg += "\tconda install -c conda-forge Pillow\n"
    msg += "   or\n"
    msg += "\tpip install Pillow"
    exit(msg)


from ..__version import __version__ as mpv_version
from ..project_vars import SERVER_NAME
from .IView import IView
from .IController import IController


class TextWidgetHandler(logging.Handler):
    """
    Configure a handler for info messages to the std.out
    """
    def __init__(self, text_widget: tk.Text):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.config(state=tk.NORMAL)

    def emit(self, record):
        msg = self.format(record)
        # enable editing
        self.text_widget.config(state=tk.NORMAL)
        # insert logging message into the Text widget
        self.text_widget.insert(tk.END, msg + '\n')
        # auto-scroll to the end
        self.text_widget.see(tk.END)
        # disable editing
        self.text_widget.config(state=tk.DISABLED)

    def stop(self):
        """
        Remove the handler.
        """
        self.close()


class StdoutRedirector(io.TextIOBase):
    """
    This is used to redirect stdout to the gui
    """
    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget
        # Redirect sys.stdout to the custom redirector
        sys.stdout = self

    def write(self, string):
        """
        Overwrite the io.TextIOBase.write command to go to the text_widget
        """
        self.text_widget.config(state='normal')
        self.text_widget.insert("end", string)
        self.text_widget.see("end")  # Auto-scroll to the end
        self.text_widget.config(state='disabled')
        return len(string)

    def stop(self):
        sys.stdout = sys.__stdout__


class RedirectOutputToGui():
    def __init__(self, text_widget: tk.Text):
        """
        Redirect stdio and INFO logging handlers to the gui

        Parameters:
        -----------
        text_widget: tkinter.Text
            The text widget target
        """
        self.stdio = StdoutRedirector(text_widget)
        self.add_tkinter_handler(text_widget)

    def add_tkinter_handler(self, text_widget: tk.Text):
        """
        This adds the tkinter text widget handler so that messages
        will show up in the gui text box
        """
        self.tk_logger = logging.getLogger(SERVER_NAME)
        # check if the tkinter handler is already attached
        for handler in self.tk_logger.handlers:
            if isinstance(handler, TextWidgetHandler):
                # it exists, so do nothing
                return
        tk_handler = TextWidgetHandler(text_widget)
        tk_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(message)s',
                                      '%m-%d %H:%M')
        tk_handler.setFormatter(formatter)
        self.tk_logger.addHandler(tk_handler)

    def stop(self):
        """
        Stop redirecting output to the gui
        """
        self.stdio.stop()


class ViewTk(IView):
    """
    The implementation of the View in the Model-View-Controller 
    design pattern.  This implements a Tkinter gui.
    """
    TK_RUNNING = False
    _pad = 7
    _border_width_main_frames = 3
    _thin_border = 1
    _info_label_width = 19
    _num_of_clients: int = 0

    class start_button_text(IntEnum):
        start = auto()
        idle = auto()
        stop = auto()
    start_button_enum = start_button_text

    def __init__(self, controller: IController):
        self._controller = controller

        self.gui = tk.Tk()
        self.gui.title(f'MultiPyVu Server {mpv_version}')
        self.gui.protocol("WM_DELETE_WINDOW", self.quit_gui)

        # the image needs to be defined here in order to keep it in memory
        rel_path = '../images/QD_logo.jpg'
        file_image = Image.open(self._controller.absolute_path(rel_path))
        self.logo_img = ImageTk.PhotoImage(file_image)

        # this gets instantiated when the server starts
        self.redirector = None

    def create_display(self):
        """
        Create the Server window
        """
        # add the QD font
        font_location = self._controller.absolute_path('font/Play-Regular.ttf')
        # qd_font_large = font.Font(family=font_location, size=30)
        qd_font_small = font.Font(family=font_location, size=17)
        qd_font_status = font.Font(family=font_location, size=12)

        # create the header
        frm_header = tk.Frame(
            master=self.gui,
            background='white',
            border=ViewTk._border_width_main_frames,
            relief=tk.RAISED,
            padx=10,
            pady=ViewTk._pad,
            )
        panel = tk.Label(master=frm_header,
                         image=self.logo_img,
                         )
        panel.grid(row=0, column=0)
        frm_header.pack()

        # create the main info frame
        frm_info = tk.Frame(
            master=self.gui,
            background=self.qd_red,
            border=ViewTk._border_width_main_frames,
            relief=tk.SUNKEN,
            padx=ViewTk._pad,
            pady=ViewTk._pad,
            )

        # create an indicator to show connection status
        self.frm_connected = tk.Frame(
            master=frm_info,
            background=self.qd_red,
            padx=ViewTk._pad,
            pady=ViewTk._pad,
            )
        self._var_connected = tk.BooleanVar(value=False)
        self.lbl_connected_indicator = tk.Label(
            master=self.frm_connected,
            width=2,
            height=1,
            padx=ViewTk._pad,
        )
        self.lbl_connected = tk.Label(
            master=self.frm_connected,
            font=qd_font_small,
            padx=ViewTk._pad,
        )
        self.lbl_connected_indicator.pack(fill=tk.BOTH, side=tk.LEFT)
        self.lbl_connected.pack(fill=tk.BOTH, side=tk.LEFT)

        # start server button
        self.btn_start = tk.Button(
            master=frm_info,
            font=qd_font_small,
            padx=ViewTk._pad,
            pady=ViewTk._pad,
            width=10,
            command=lambda: self._start_btn_action()
        )
        self.btn_start.grid(row=0, column=2, sticky='e')
        btn_txt = self._get_start_btn_txt(self.start_button_enum.start)
        self.btn_start.config(text=btn_txt)

        # set the indicator light and start button
        self.server_status('closed')

        # ip address
        frm_address = tk.Frame(master=frm_info,
                               background=self.qd_red,
                               padx=ViewTk._pad,
                               pady=ViewTk._pad,
                               )
        lbl_ip_name = tk.Label(master=frm_address,
                               font=qd_font_status,
                               text='IP Address',
                               width=len('IP Address'),
                               background=self.qd_red,
                               fg='white',
                               anchor='w',
                               justify='left',
                               )
        lbl_ip_name.grid(row=0, column=0, sticky='w')
        self.txt_ip = tk.Text(master=frm_address,
                              font=qd_font_small,
                              height=1,
                              width=ViewTk._info_label_width,
                              relief=tk.SUNKEN,
                              border=ViewTk._border_width_main_frames,
                              borderwidth=ViewTk._border_width_main_frames,
                              )
        self.txt_ip.grid(row=1,
                         column=0,
                         padx=ViewTk._pad,
                         ipady=ViewTk._pad,
                         )
        self.txt_ip.tag_configure('center', justify='center')
        self.txt_ip.tag_add('center', '1.0', tk.END)
        self.txt_ip.insert(tk.END, self._controller.ip_address)
        self.txt_ip.configure(state=tk.DISABLED)

        # port label
        lbl_port_name = tk.Label(master=frm_address,
                                 font=qd_font_status,
                                 text='Port Number',
                                 width=len('Port Number'),
                                 background=self.qd_red,
                                 fg='white',
                                 anchor='w',
                                 justify='left',
                                 )
        lbl_port_name.grid(row=0, column=1, sticky='W')
        # port number
        self.ent_port = tk.Entry(master=frm_address,
                                 font=qd_font_small,
                                 width=int(ViewTk._info_label_width / 2),
                                 relief=tk.SUNKEN,
                                 border=ViewTk._border_width_main_frames,
                                 borderwidth=ViewTk._border_width_main_frames,
                                 )
        self.port = self._controller.model.port
        self.ent_port.grid(row=1, column=1,
                           sticky='e',
                           padx=ViewTk._pad,
                           ipady=ViewTk._pad,
                           )

        # number of connected indicator
        lbl_num_connected_name = tk.Label(master=frm_address,
                                          font=qd_font_status,
                                          text='Connected Clients',
                                          width=len('Connected Clients'),
                                          background=self.qd_red,
                                          anchor='w',
                                          )
        lbl_num_connected_name.grid(row=0, column=2, sticky='e')
        self.lbl_num_connected = tk.Label(
            master=frm_address,
            font=qd_font_small,
            text=ViewTk._num_of_clients,
            padx=ViewTk._pad,
        )
        self.lbl_num_connected.grid(row=1, column=2, sticky='e')
        lbl_num_connected_name.grid_forget()
        self.lbl_num_connected.grid_forget()
        frm_address.grid(row=1, column=0, sticky='w')

        # flavor name
        # create a frame so that the alignment matches other widgets
        frm_flavor = tk.Frame(
            master=frm_info,
            background=self.qd_red,
            padx=ViewTk._pad,
            pady=ViewTk._pad,
            )
        self.lbl_flavor = tk.Label(
            master=frm_flavor,
            font=qd_font_small,
            text='',
            width=ViewTk._info_label_width,
            relief=tk.SUNKEN,
            padx=ViewTk._pad,
            pady=ViewTk._pad,
        )
        self.lbl_flavor.pack()
        frm_flavor.grid(row=2, column=0, sticky='w')

        # Output the command line info to the gui
        frm_readback = tk.Frame(master=frm_info,
                                background=self.qd_red,
                                padx=ViewTk._pad,
                                pady=ViewTk._pad,
                                )
        lbl_readback_title = tk.Label(master=frm_readback,
                                      font=qd_font_small,
                                      background='white',
                                      fg=self.qd_black,
                                      text='Server Status',
                                      border=ViewTk._border_width_main_frames,
                                      padx=ViewTk._pad,
                                      pady=ViewTk._pad,
                                      )
        self.txt_readback = tk.Text(
            master=frm_readback,
            font=qd_font_status,
            background='white',
            fg=self.qd_black,
            width=55,
            height=7,
            state="disabled",
            )
        # Create vertical scroll bar and link it to the Text widget
        self.vertical_scrollbar = tk.Scrollbar(master=frm_readback,
                                               command=self.txt_readback.yview)
        self.txt_readback.configure(yscrollcommand=self.vertical_scrollbar.set)
        self.vertical_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        lbl_readback_title.pack(fill=tk.BOTH)
        self.txt_readback.pack()
        frm_readback.grid(row=3, column=0, sticky='w')

        # Quit button
        btn_quit = tk.Button(
            master=frm_info,
            font=qd_font_small,
            text='Quit',
            padx=ViewTk._pad,
            pady=ViewTk._pad,
            command=lambda: self.quit_gui()
        )
        btn_quit.grid(row=3, column=2, sticky='se')

        frm_info.pack()

    @property
    def ip_address(self) -> str:
        """
        Returns the IP address being used by the Server

        Returns:
        --------
        string of the IP address
        """
        return self.txt_ip.get('1.0', tk.END)

    @ip_address.setter
    def ip_address(self, new: str):
        """
        Setter for the IP address
        """
        # change the state
        self.txt_ip.config(state=tk.NORMAL)
        # remove the current text
        self.txt_ip.delete(1.0, tk.END)
        # set the text
        self.txt_ip.insert(tk.END, new)
        # change the state back
        self.txt_ip.config(state=tk.DISABLED)

    @property
    def port(self) -> int:
        """
        Returns the port being used by the Server

        Returns:
        --------
        int with the port number.
        """
        try:
            p = int(self.ent_port.get())
        except AttributeError:
            p = self._controller.model.port
        return p

    @port.setter
    def port(self, new: int):
        """
        The setter for the Port number
        """
        # remove the current text
        self.ent_port.delete(0, tk.END)
        # set the text
        self.ent_port.insert(0, str(new))

    def get_connection_status(self) -> bool:
        """
        Returns True (False) if a client is connected (not connected)

        Returns:
        --------
        bool
        """
        return self._var_connected.get()

    def set_number_of_clients(self, num: int):
        """
        Updates the number of clients connected
        """
        ViewTk._num_of_clients = num
        self.lbl_num_connected.config(text=num)

    def server_status(self, server_status: str):
        """
        Updates the gui based on the server status
        """
        if server_status == 'closed':
            # hide the connection frame
            self.frm_connected.grid_remove()
            self._var_connected.set(False)
            # update the button text
            btn_text = self._get_start_btn_txt(self.start_button_enum.start)
        elif server_status == 'idle':
            # show the light
            self.frm_connected.grid(row=0, column=0, sticky='w')
            # turn the indicator light off
            self.lbl_connected_indicator.config(bg='grey')
            self._var_connected.set(True)
            # update the button text
            btn_text = self._get_start_btn_txt(self.start_button_enum.stop)
        elif server_status == 'connected':
            # show the light
            self.frm_connected.grid(row=0, column=0, sticky='w')
            # turn the indicator light on
            self.lbl_connected_indicator.config(bg='green')
            self._var_connected.set(True)
            # update the button text
            btn_text = self._get_start_btn_txt(self.start_button_enum.stop)
        self.lbl_connected.config(text=server_status)
        self.btn_start.config(text=btn_text)

    def _get_start_btn_txt(self, btn_enum: start_button_enum) -> str:
        """
        Helper method to get the text on this button
        """
        if btn_enum == self.start_button_enum.start:
            return 'Start Server'
        elif btn_enum == self.start_button_enum.idle:
            return 'Waiting for Client'
        elif btn_enum == self.start_button_enum.stop:
            return 'Close Server'
        else:
            raise ValueError('Unknown option')

    def _start_btn_action(self):
        """
        Toggle between this button starting/stopping the server
        """
        with Lock():
            # server is not running and needs to be opened
            if self._controller.server_status() == 'closed':
                # redirect the output to the gui
                self.redirector = RedirectOutputToGui(self.txt_readback)
                instance = self._controller.start_server()

                # check if an instance was returned
                if not instance:
                    # Failed to start the server.  Check the IP address
                    self._controller.stop_server()
                    return None
            else:
                # stop the server
                self._controller.stop_server()

    @property
    def mvu_flavor(self):
        """
        Gets the flavor of the MultiVu which is running
        """
        return self.lbl_flavor['text']

    @mvu_flavor.setter
    def mvu_flavor(self, flavor):
        """
        The setter for the MultiVu flavor
        """
        self.lbl_flavor.config(text=flavor)
        self.lbl_flavor['text'] = flavor

    def start_gui(self):
        """
        Opens the gui window and runs the gui.
        """
        ViewTk.TK_RUNNING = True
        self.gui.mainloop()

    def quit_gui(self):
        """
        Close the gui and its window.
        """
        self._controller.stop_server()
        if self.redirector is not None:
            self.redirector.stop()
            self.redirector = None
        self.gui.destroy()
        ViewTk.TK_RUNNING = False
