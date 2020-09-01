from src.Gui.MainApp import MainApp
import tkinter as tk


class App(tk.Tk):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.shared_data = {
            "Stock search": tk.StringVar()
        }

        self.frames = {
            'MainApp': MainApp(self, self)
        }

        self.current_frame = None
        self.show_frame('MainApp')

    def show_frame(self, name):
        if self.current_frame:
            self.current_frame.forget()
        self.current_frame = self.frames[name]
        self.current_frame.pack()

        self.current_frame.update_widgets()  # <-- update data in widgets


def run_gui():
    app = App()

    w = 350  # width
    h = 150  # height

    # get screen width and height
    ws = app.winfo_screenwidth()  # width of the screen
    hs = app.winfo_screenheight()  # height of the screen

    # calculate x and y coordinates for the Tk root window
    x = (ws / 2) - (w / 2)
    y = (hs / 2) - (h / 2)

    # set the dimensions of the screen
    # and where it is placed
    app.geometry('%dx%d+%d+%d' % (w, h, x, y))
    app.title("Stock News Updates searcher")
    app.mainloop()
