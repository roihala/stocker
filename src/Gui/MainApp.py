import tkinter as tk

from src.search_tools import search_stock


class MainApp(tk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        tk.Label(self, text="Stock News Searcher").pack(side="top", fill="x", pady=10)

        self.entry1 = tk.Entry(self, textvariable=self.controller.shared_data["Stock search"])
        self.entry1.pack()

        call_button = tk.Button(self, text="Search", command=self._webchrome)
        call_button.pack()

        tk.Label(self, text="Searching stocks news created by Roi & Nati Enjoy ;)").pack(side="top", fill="x", pady=10)

    def _webchrome(self):
        ticker = self.controller.shared_data["Stock search"].get()

        if ticker:
            search_stock(ticker)

    def update_widgets(self):
        pass
