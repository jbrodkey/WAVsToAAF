#!/usr/bin/env python3
"""
WAVsToAAF GUI - Graphical User Interface for WAV to AAF Conversion

Copyright (c) 2025 Jason Brodkey. All rights reserved.

A graphical interface for converting WAV files to Advanced Authoring Format (AAF).
Provides file/folder browsing, frame rate selection, and real-time processing feedback.

Author: Jason Brodkey
Version: 1.0.0
Date: 2025-11-04
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import os
import sys
import threading
import subprocess
import webbrowser

# Import the core processor from wav_to_aaf (robust even when not a package)
# Prefer normal import; fallback to file-based import so editors and frozen apps work reliably.
try:
    import importlib
    _mod = importlib.import_module('wav_to_aaf')
    WAVsToAAFProcessor = _mod.WAVsToAAFProcessor
    core_version = getattr(_mod, '__version__', '0.0.0')
except Exception:
    try:
        import importlib.util
        from pathlib import Path as _Path
        _module_path = _Path(__file__).parent / 'wav_to_aaf.py'
        _spec = importlib.util.spec_from_file_location('wav_to_aaf', _module_path)
        if _spec and _spec.loader:
            _m = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_m)
            WAVsToAAFProcessor = _m.WAVsToAAFProcessor
            core_version = getattr(_m, '__version__', '0.0.0')
        else:
            raise ImportError('spec loader missing')
    except Exception:
        print("Error: Could not import wav_to_aaf module.")
        print("Make sure wav_to_aaf.py is in the same directory.")
        sys.exit(1)

__version__ = core_version

def launch_gui():
    """Launch a Tkinter GUI for selecting inputs and running AAF conversion."""
    root = tk.Tk()
    root.title("WAVsToAAF")
    root.geometry("680x520")

    # Variables
    wav_var = tk.StringVar()
    out_var = tk.StringVar()
    fps_var = tk.StringVar(value="24")
    embed_var = tk.BooleanVar(value=True)
    last_outputs = {'paths': []}
    cancel_event = threading.Event()
    processor = WAVsToAAFProcessor()

    def log(msg):
        log_text.configure(state='normal')
        log_text.insert('end', str(msg) + "\n")
        log_text.see('end')
        log_text.configure(state='disabled')
        # Capture generated AAF paths from log lines to enable Reveal button
        try:
            s = str(msg)
            markers = ["Created:", "Output files saved to:"]
            for m in markers:
                if m in s:
                    # Extract path after marker
                    path = s.split(m, 1)[1].strip() if m in s else ""
                    if path:
                        # Store directory path
                        if os.path.isdir(path):
                            if path not in last_outputs['paths']:
                                last_outputs['paths'].append(path)
                        elif path.lower().endswith('.aaf'):
                            if path not in last_outputs['paths']:
                                last_outputs['paths'].append(path)
                        try:
                            if not open_btn.winfo_ismapped():
                                open_btn.pack(side='left', padx=(8, 0))
                            open_btn.configure(state='normal')
                        except Exception:
                            pass
                    break
        except Exception:
            pass

    def browse_wav_file():
        path = filedialog.askopenfilename(
            title="Select WAV file",
            filetypes=[("WAV Files", "*.wav *.wave"), ("All Files", "*.*")]
        )
        if path:
            wav_var.set(path)
    def browse_wav_dir():
        path = filedialog.askdirectory(title="Select WAV directory")
        if path:
            wav_var.set(path)

    def browse_out():
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            out_var.set(path)

    def run_clicked():
        # Parse FPS
        try:
            fps = float(fps_var.get().strip() or "24")
            if fps <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Invalid FPS", "FPS must be a positive number (e.g. 24 or 23.976). Using 24.")
            fps = 24.0
        
        # Get options
        embed_audio = embed_var.get()
        write_skip_log = True  # Always on by default

        wavp = wav_var.get().strip() or None
        outp = out_var.get().strip() or None

        if not wavp:
            messagebox.showerror("Missing input", "Please select a WAV file or directory.")
            return

        # Set default output if not specified
        if not outp:
            if os.path.isfile(wavp):
                outp = os.path.join(os.path.dirname(wavp), "aaf_output")
            else:
                outp = os.path.join(wavp, "aaf_output")

        # Run in a thread to keep UI responsive
        cancel_event.clear()
        try:
            run_btn.configure(state='disabled')
            cancel_btn.configure(state='normal')
        except Exception:
            pass

        def worker():
            log("Starting conversion…")
            log(f"Frame rate: {fps} fps")
            log(f"Audio: {'Embedded' if embed_audio else 'Linked'}")
            last_outputs['paths'].clear()
            ok = False
            try:
                if os.path.isfile(wavp):
                    # Single file mode
                    output_filename = os.path.splitext(os.path.basename(wavp))[0] + '.aaf'
                    output_file = os.path.join(outp, output_filename)
                    result = processor.process_single_file(
                        wavp, output_file, fps=fps, embed_audio=embed_audio,
                        auto_skip_log=write_skip_log
                    )
                    ok = (result == 0)
                else:
                    # Directory mode
                    result = processor.process_directory(
                        wavp, outp, fps=fps, embed_audio=embed_audio,
                        auto_skip_log=write_skip_log
                    )
                    ok = (result == 0)
            except Exception as e:
                log(f"Error: {e}")
                ok = False

            # Update UI from main thread
            def finish_ui():
                try:
                    run_btn.configure(state='normal')
                    cancel_btn.configure(state='disabled')
                except Exception:
                    pass
                if ok:
                    messagebox.showinfo("Done", "AAF creation completed.")
                else:
                    if cancel_event.is_set():
                        messagebox.showinfo("Cancelled", "AAF creation canceled. Some AAFs may have already been created.")
                    else:
                        messagebox.showerror("Error", "AAF creation failed. Check the log for details.")

            try:
                root.after(0, finish_ui)
            except Exception:
                finish_ui()

        threading.Thread(target=worker, daemon=True).start()

    def cancel_clicked():
        cancel_event.set()
        log("Cancellation requested…")

    def clear_log():
        log_text.configure(state='normal')
        log_text.delete('1.0', 'end')
        log_text.configure(state='disabled')

    def open_output_location():
        # If the user set an Output Folder, prioritize opening that location
        outp = (out_var.get().strip() or '')
        wavp = (wav_var.get().strip() or '')
        if outp:
            try:
                folder = outp if os.path.isdir(outp) else os.path.dirname(outp)
                if sys.platform == 'darwin':
                    subprocess.run(['open', folder], check=False)
                elif sys.platform == 'win32':
                    os.startfile(folder)
                else:
                    subprocess.run(['xdg-open', folder], check=False)
                return
            except Exception:
                pass
        # Otherwise, prefer revealing the last created AAF file if tracked
        paths = last_outputs.get('paths') or []
        if paths:
            target = paths[-1]  # last created AAF
            try:
                if sys.platform == 'darwin':
                    subprocess.run(['open', '-R', target], check=False)
                elif sys.platform == 'win32':
                    subprocess.run(['explorer', '/select,', target], check=False)
                else:
                    subprocess.run(['xdg-open', os.path.dirname(target)], check=False)
                return
            except Exception:
                pass
        # Fallback: open expected folder based on inputs
        try:
            if os.path.isfile(wavp):
                folder = os.path.join(os.path.dirname(wavp), 'aaf_output')
            else:
                folder = os.path.join(wavp, 'aaf_output')
            if sys.platform == 'darwin':
                subprocess.run(['open', folder], check=False)
            elif sys.platform == 'win32':
                os.startfile(folder)
            else:
                subprocess.run(['xdg-open', folder], check=False)
        except Exception:
                        messagebox.showwarning("Open Location", "Could not open the AAF location.")

    # Layout - use ttk.Frame like ALE
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill='both', expand=True)

    # WAV
    ttk.Label(frm, text="WAV file or directory").grid(row=0, column=0, sticky='w')
    wav_entry = ttk.Entry(frm, textvariable=wav_var, width=60)
    # Tiny positive top padding to nudge entry down for visual alignment
    wav_entry.grid(row=1, column=0, columnspan=2, sticky='we', pady=(1, 0))
    # Place the buttons in a frame in the same row as the entry
    wav_btns = ttk.Frame(frm)
    wav_btns.grid(row=1, column=2, sticky='w', pady=0)
    ttk.Button(wav_btns, text="File…", command=browse_wav_file).grid(row=0, column=0, padx=(0, 4), pady=0)
    ttk.Button(wav_btns, text="Folder…", command=browse_wav_dir).grid(row=0, column=1, pady=0)

    # Output
    ttk.Label(frm, text="Output Folder for AAFs").grid(row=2, column=0, sticky='w', pady=(6, 0))
    out_entry = ttk.Entry(frm, textvariable=out_var, width=60)
    # Mirror tiny top padding for consistent alignment
    out_entry.grid(row=3, column=0, columnspan=2, sticky='we', pady=(1, 0))
    ttk.Button(frm, text="Browse…", command=browse_out).grid(row=3, column=2, sticky='w', pady=0)

    # FPS
    fps_row = ttk.Frame(frm)
    fps_row.grid(row=4, column=0, columnspan=3, sticky='w', pady=(6, 8))
    ttk.Label(fps_row, text="FPS:").pack(side='left')
    ttk.Entry(fps_row, textvariable=fps_var, width=8).pack(side='left', padx=(4, 0))
    ttk.Label(fps_row, text="(default 24)").pack(side='left', padx=(6, 0))
    
    # Embed audio checkbox (embedded is default)
    ttk.Checkbutton(frm, text="Embed audio in AAF (default)", variable=embed_var).grid(row=5, column=0, columnspan=3, sticky='w', pady=(0, 8))

    # Action buttons
    buttons_row = ttk.Frame(frm)
    buttons_row.grid(row=6, column=0, columnspan=3, sticky='w', pady=(0, 8))
    run_btn = ttk.Button(buttons_row, text="Run", command=run_clicked)
    run_btn.pack(side='left')
    cancel_btn = ttk.Button(buttons_row, text="Cancel", command=cancel_clicked, state='disabled')
    cancel_btn.pack(side='left', padx=(8, 0))
    open_btn = ttk.Button(buttons_row, text="Open AAF Location", command=open_output_location, state='disabled')
    # Keep hidden until an AAF is generated
    try:
        open_btn.pack_forget()
    except Exception:
        pass

    # Log area with clear button
    log_header = ttk.Frame(frm)
    log_header.grid(row=7, column=0, columnspan=3, sticky='ew', pady=(0, 2))
    ttk.Label(log_header, text="Output Log").pack(side='left')
    ttk.Button(log_header, text="Clear", command=clear_log, width=8).pack(side='right')

    log_text = ScrolledText(frm, height=16, state='disabled')
    log_text.grid(row=8, column=0, columnspan=3, sticky='nsew')
    frm.rowconfigure(8, weight=1)

    # Copyright, website, and version labels below log
    copyright_font = (None, 10)
    copyright_lbl = ttk.Label(frm, text="© Jason Brodkey", font=copyright_font, anchor='w', justify='left')
    copyright_lbl.grid(row=9, column=0, sticky='w', pady=(4, 0))

    def open_website(event=None):
        webbrowser.open_new_tab('https://www.editcandy.com')

    website_lbl = ttk.Label(frm, text="www.editcandy.com", font=copyright_font, foreground="#4ea3ff", cursor="hand2")
    website_lbl.grid(row=9, column=0, columnspan=3, pady=(4, 0))
    website_lbl.bind("<Button-1>", open_website)

    version_lbl = ttk.Label(frm, text=f"v{__version__}", font=copyright_font, anchor='e', justify='right')
    version_lbl.grid(row=9, column=2, sticky='e', pady=(4, 0))

    frm.columnconfigure(0, weight=1)

    # Redirect stdout to log
    class StdoutRedirector:
        def write(self, message):
            log(message.rstrip('\n')) if message.strip() else None
        def flush(self):
            pass

    sys.stdout = StdoutRedirector()

    root.mainloop()


def main():
    """Main entry point for the GUI application"""
    launch_gui()


if __name__ == "__main__":
    main()
