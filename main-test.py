import tkinter as tk
from tkinter import font

class Calculator:
    def __init__(self, root):
        self.root = root
        self.root.title("Calculator")
        self.root.geometry("400x500")
        self.root.resizable(False, False)
        
        self.expression = ""
        
        # Display
        self.display = tk.Entry(root, font=("Arial", 20), 
                               borderwidth=2, relief="solid",
                               justify="right", bg="white")
        self.display.grid(row=0, column=0, columnspan=4, 
                         ipady=10, padx=10, pady=10, sticky="nsew")
        
        # Buttons layout
        buttons = [
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('/', 1, 3),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2), ('*', 2, 3),
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2), ('-', 3, 3),
            ('0', 4, 0), ('.', 4, 1), ('=', 4, 2), ('+', 4, 3),
            ('C', 5, 0), ('DEL', 5, 1),
        ]
        
        # Create buttons
        for (text, row, col) in buttons:
            self.create_button(text, row, col)
    
    def create_button(self, text, row, col):
        btn = tk.Button(self.root, text=text, font=("Arial", 18),
                       command=lambda: self.on_button_click(text))
        btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew", ipadx=20, ipady=20)
        
        # Color codes
        if text == '=':
            btn.config(bg="#4CAF50", fg="white")
        elif text in ['C', 'DEL']:
            btn.config(bg="#f44336", fg="white")
        elif text in ['/', '*', '-', '+']:
            btn.config(bg="#FF9800", fg="white")
        else:
            btn.config(bg="#e0e0e0")
    
    def on_button_click(self, char):
        if char == 'C':
            self.expression = ""
            self.display.delete(0, tk.END)
        elif char == 'DEL':
            self.expression = self.expression[:-1]
            self.display.delete(0, tk.END)
            self.display.insert(0, self.expression)
        elif char == '=':
            try:
                result = eval(self.expression)
                self.display.delete(0, tk.END)
                self.display.insert(0, str(result))
                self.expression = str(result)
            except:
                self.display.delete(0, tk.END)
                self.display.insert(0, "Error")
                self.expression = ""
        else:
            self.expression += str(char)
            self.display.delete(0, tk.END)
            self.display.insert(0, self.expression)

if __name__ == "__main__":
    root = tk.Tk()
    calc = Calculator(root)
    root.mainloop()