import abc
import os
import platform
import threading
import queue
import logging

class BaseUI(abc.ABC):
    @abc.abstractmethod
    def display_message(self, text: str, sender: str = "JARVIS"):
        pass

    @abc.abstractmethod
    def set_status(self, text: str):
        pass

    @abc.abstractmethod
    def get_input(self) -> str:
        """Blocking input for CLI, or handling via events in GUI."""
        pass

    @abc.abstractmethod
    def start(self):
        pass

    def stop(self):
        """Stop the UI event loop."""
        pass

    def begin_stream(self, sender: str = "JARVIS"):
        pass

    def append_stream(self, text: str):
        pass

    def end_stream(self):
        pass

    def emit_event(self, event_type: str, data=None):
        """Publish an operational event when the UI supports live activity."""
        pass

class ConsoleUI(BaseUI):
    def __init__(self):
        self._streaming = False
        self._output_lock = threading.Lock()

    def display_message(self, text: str, sender: str = "JARVIS"):
        with self._output_lock:
            if self._streaming:
                print()
                self._streaming = False
            print(f"\n[{sender}]: {text}")

    def set_status(self, text: str):
        # Console doesn't really have a status bar, maybe just log it
        pass

    def get_input(self) -> str:
        try:
            return input("\n[You]: ").strip()
        except EOFError:
            return "exit"

    def start(self):
        # CLI doesn't need a mainloop setup
        pass

    def stop(self):
        pass

    def begin_stream(self, sender: str = "JARVIS"):
        with self._output_lock:
            if self._streaming:
                print()
            print(f"\n[{sender}]: ", end="", flush=True)
            self._streaming = True

    def append_stream(self, text: str):
        with self._output_lock:
            print(text, end="", flush=True)

    def end_stream(self):
        with self._output_lock:
            if self._streaming:
                print()
                self._streaming = False

# Try importing Tkinter
try:
    import tkinter as tk
    from tkinter import scrolledtext, ttk
    HAS_TK = True
except ImportError:
    HAS_TK = False

class TkinterUI(BaseUI):
    def __init__(self, callback_handler):
        if not HAS_TK:
            raise ImportError("Tkinter not available")
        if (
            platform.system() not in {"Windows", "Darwin"}
            and not os.environ.get("DISPLAY")
        ):
            raise RuntimeError("No graphical display is available")

        self.callback_handler = callback_handler
        self.msg_queue = queue.Queue()
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S - Advanced System")
        self.root.geometry("900x600")
        self.root.configure(bg="#050505")

        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#050505")
        
        # Chat Display
        self.chat_area = scrolledtext.ScrolledText(
            self.root, 
            wrap=tk.WORD, 
            bg="#0f0f0f", 
            fg="#00ffcc", # Sci-fi cyan
            font=("Consolas", 11),
            insertbackground="white"
        )
        self.chat_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        self.chat_area.configure(state='disabled')

        # Input Area
        input_frame = tk.Frame(self.root, bg="#050505")
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        self.entry = tk.Entry(
            input_frame, 
            bg="#1a1a1a", 
            fg="white", 
            insertbackground="white",
            font=("Consolas", 12)
        )
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.entry.bind("<Return>", self._on_enter)

        send_btn = tk.Button(
            input_frame, 
            text="EXECUTE", 
            command=self._on_send,
            bg="#004433", 
            fg="#00ffcc", 
            activebackground="#006644",
            activeforeground="white",
            font=("Consolas", 10, "bold"),
            relief="flat"
        )
        send_btn.pack(side=tk.RIGHT)

        stop_btn = tk.Button(
            input_frame,
            text="STOP",
            command=lambda: self.callback_handler("stop generating"),
            bg="#442200",
            fg="#ffbb66",
            activebackground="#663300",
            activeforeground="white",
            font=("Consolas", 10, "bold"),
            relief="flat",
        )
        stop_btn.pack(side=tk.RIGHT, padx=(0, 8))

        # Status Bar
        self.status_var = tk.StringVar()
        status_bar = tk.Label(
            self.root, 
            textvariable=self.status_var, 
            bg="#000000", 
            fg="#666666", 
            anchor="w",
            font=("Consolas", 9)
        )
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._process_queue)

    def _process_queue(self):
        try:
            if not self.root.winfo_exists():
                return
        except tk.TclError:
            return
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                if msg_type == "msg":
                    sender, text = content
                    self.chat_area.configure(state='normal')
                    
                    tag = "user" if sender == "You" else "jarvis"
                    self.chat_area.tag_config("user", foreground="#aaaaaa")
                    self.chat_area.tag_config("jarvis", foreground="#00ffcc")
                    
                    self.chat_area.insert(tk.END, f"\n[{sender}]: ", tag)
                    self.chat_area.insert(tk.END, f"{text}\n")
                    self.chat_area.see(tk.END)
                    self.chat_area.configure(state='disabled')
                elif msg_type == "status":
                    self.status_var.set(content)
                elif msg_type == "stream_start":
                    sender = content
                    self.chat_area.configure(state="normal")
                    tag = "user" if sender == "You" else "jarvis"
                    self.chat_area.insert(tk.END, f"\n[{sender}]: ", tag)
                    self.chat_area.configure(state="disabled")
                elif msg_type == "stream_chunk":
                    self.chat_area.configure(state="normal")
                    self.chat_area.insert(tk.END, content)
                    self.chat_area.see(tk.END)
                    self.chat_area.configure(state="disabled")
                elif msg_type == "stream_end":
                    self.chat_area.configure(state="normal")
                    self.chat_area.insert(tk.END, "\n")
                    self.chat_area.see(tk.END)
                    self.chat_area.configure(state="disabled")
        except queue.Empty:
            pass
        finally:
            try:
                self.root.after(100, self._process_queue)
            except tk.TclError:
                pass

    def _on_enter(self, event):
        self._on_send()

    def _on_send(self):
        text = self.entry.get().strip()
        if text:
            self.entry.delete(0, tk.END)
            # Skills such as OCR and model inference must not block Tk's event loop.
            threading.Thread(
                target=self.callback_handler,
                args=(text,),
                daemon=True,
                name="jarvis-ui-command",
            ).start()

    def _on_close(self):
        self.callback_handler("exit")
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def display_message(self, text: str, sender: str = "JARVIS"):
        self.msg_queue.put(("msg", (sender, text)))

    def set_status(self, text: str):
        self.msg_queue.put(("status", text))

    def get_input(self) -> str:
        # Not used in callback, non-blocking model
        return ""

    def start(self):
        self.root.mainloop()

    def stop(self):
        try:
            self.root.after(0, self.root.quit)
        except (tk.TclError, RuntimeError):
            pass

    def begin_stream(self, sender: str = "JARVIS"):
        self.msg_queue.put(("stream_start", sender))

    def append_stream(self, text: str):
        self.msg_queue.put(("stream_chunk", text))

    def end_stream(self):
        self.msg_queue.put(("stream_end", None))
