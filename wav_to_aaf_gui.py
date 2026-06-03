#!/usr/bin/env python3
"""
WAVsToAAF GUI - Graphical User Interface for WAV to AAF Conversion

Copyright (c) 2025 Jason Brodkey. All rights reserved.

This script provides a graphical user interface for converting WAV files to
Advanced Authoring Format (AAF) files with comprehensive metadata extraction.

Features:
- Drag-and-drop support for input files/folders
- Batch processing with progress tracking
- Cancel functionality for long-running operations
- Comprehensive WAV metadata extraction (BEXT, LIST-INFO, XML, UCS)
- Configurable AAF generation options

Author: Jason Brodkey
Version: 1.0.0
Date: 2025-11-04
"""

import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path
from typing import Optional, Any

# Try to import tkinterdnd2 for drag-and-drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False
    print("Warning: tkinterdnd2 not available. Drag-and-drop will be disabled.")
    print("Install with: pip install tkinterdnd2")

# Import the main WAVsToAAF processor
try:
    from wav_to_aaf import WAVsToAAFProcessor
except ImportError:
    print("Error: Could not import wav_to_aaf module")
    sys.exit(1)


def get_app_version() -> str:
    """Get the application version from _version.py"""
    try:
        import _version
        return _version.__version__
    except ImportError:
        return "1.0.0"


def load_text_file(paths):
    """Load text from the first available file in the list"""
    for path in paths:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            continue
    return "License information not available."


def launch_gui():
    """Launch the WAVsToAAF GUI"""
    global root, input_var, out_var, emit_ale_var, one_aaf_var
    global near_sources_var, tape_mode_var, relative_locators_var, bit_depth_var, sample_rate_var
    global cancel_event, progress_var, status_var, log_text, run_btn, cancel_btn, open_btn

    # Create root window with drag-and-drop support if available
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()

    root.title("WAVsToAAF - WAV to AAF Converter")
    root.geometry("800x700")
    root.minsize(700, 600)

    # Variables
    input_var = tk.StringVar(value="")
    out_var = tk.StringVar(value="")
    emit_ale_var = tk.BooleanVar(value=False)
    one_aaf_var = tk.BooleanVar(value=False)
    near_sources_var = tk.BooleanVar(value=False)
    tape_mode_var = tk.BooleanVar(value=False)
    relative_locators_var = tk.BooleanVar(value=False)
    bit_depth_var = tk.StringVar(value="24")
    sample_rate_var = tk.StringVar(value="48000")
    fps_var = tk.StringVar(value="24")
    last_outputs = {'paths': [], 'last_output_path': None}
    progress_var = tk.StringVar(value="")
    status_var = tk.StringVar(value="")
    cancel_event = threading.Event()

    def log(msg):
        log_text.configure(state='normal')
        log_text.insert('end', str(msg) + "\n")
        log_text.see('end')
        log_text.configure(state='disabled')
        # Track output folder for Open button and parse progress
        try:
            s = str(msg)
            if "Output:" in s:
                path = s.split("Output:", 1)[1].strip()
                if path and os.path.isdir(path):
                    last_outputs['paths'].append(path)
                    try:
                        if not open_btn.winfo_ismapped():
                            open_btn.pack(side='left', padx=(8, 0))
                        open_btn.configure(state='normal')
                    except Exception:
                        pass
            # Parse progress "X/Y" from batch processing output
            if "/" in s and "%" in s:
                parts = s.split()
                for part in parts:
                    if "/" in part and part.replace("/", "").replace(".", "").isdigit():
                        progress_var.set(f"Progress: {part}")
                        break
        except Exception:
            pass

    def browse_input():
        """Browse for input file or directory"""
        initial_dir = None
        current_input = input_var.get().strip()
        if current_input:
            if os.path.isdir(current_input):
                initial_dir = current_input
            else:
                initial_dir = os.path.dirname(current_input) or os.getcwd()
        else:
            initial_dir = os.getcwd()

        path = filedialog.askopenfilename(
            title="Select WAV file",
            initialdir=initial_dir,
            filetypes=[("WAV files", ("*.wav", "*.wave")), ("All files", "*.*")]
        )
        if path:
            input_var.set(path)
            status_var.set(f"Input set to: {os.path.basename(path)}")
            root.after(3000, lambda: status_var.set("") if status_var.get().startswith("Input set to:") else None)

    def browse_input_dir():
        """Browse for input directory"""
        path = filedialog.askdirectory(title="Select input directory")
        if path:
            input_var.set(path)
            status_var.set(f"Input set to: {os.path.basename(path)}")
            root.after(3000, lambda: status_var.set("") if status_var.get().startswith("Input set to:") else None)

    def browse_output():
        """Browse for output directory"""
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            out_var.set(path)
            status_var.set(f"Output set to: {os.path.basename(path)}")
            root.after(3000, lambda: status_var.set("") if status_var.get().startswith("Output set to:") else None)

    def handle_input_drop(event):
        """Handle drag-and-drop for input entry."""
        # tkinterdnd2 returns file paths as a string with potential braces/quotes
        data = event.data

        # Remove surrounding braces if present (tkinterdnd2 format)
        if data.startswith('{') and data.endswith('}'):
            data = data[1:-1]

        # For single file/folder, use the whole path (don't split on spaces)
        path = data.strip()
        # Remove quotes if present
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]

        if os.path.exists(path):
            input_var.set(path)
            # Provide visual feedback
            status_var.set(f"Input set to: {os.path.basename(path)}")
            # Clear status after 3 seconds
            root.after(3000, lambda: status_var.set("") if status_var.get().startswith("Input set to:") else None)
        return 'copy'

    def handle_output_drop(event):
        """Handle drag-and-drop for output entry."""
        data = event.data

        if data.startswith('{') and data.endswith('}'):
            data = data[1:-1]
        path = data.strip()
        if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
            path = path[1:-1]

        if os.path.exists(path) and os.path.isdir(path):
            out_var.set(path)
            # Provide visual feedback
            status_var.set(f"Output set to: {os.path.basename(path)}")
            # Clear status after 3 seconds
            root.after(3000, lambda: status_var.set("") if status_var.get().startswith("Output set to:") else None)
        return 'copy'

    def run_clicked():
        """Handle the Run button click"""
        inp = input_var.get().strip()
        outp = out_var.get().strip()

        # Validate inputs
        if not inp:
            messagebox.showerror("Missing input", "Please select a WAV file or directory.")
            return

        if not os.path.exists(inp):
            messagebox.showerror("Input not found", f"The selected input does not exist:\n{inp}")
            return

        # Parse options
        try:
            fps = float(fps_var.get().strip() or "24")
            if fps <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Invalid FPS", "FPS must be a positive number (e.g. 24 or 23.976). Using 24.")
            fps = 24.0

        embed_audio = True
        emit_ale = emit_ale_var.get()
        one_aaf = one_aaf_var.get()
        near_sources = near_sources_var.get()
        tape_mode = tape_mode_var.get()
        relative_locators = relative_locators_var.get()
        link_mode = 'import'

        # Parse bit depth and sample rate (only for embedded audio)
        bit_depth = None
        sample_rate = None
        if embed_audio:
            try:
                bit_depth = int(bit_depth_var.get().strip() or "24")
                if bit_depth not in [16, 24]:
                    raise ValueError
            except Exception:
                messagebox.showwarning("Invalid Bit Depth", "Bit depth must be 16 or 24. Using 24.")
                bit_depth = 24

            try:
                sample_rate = int(sample_rate_var.get().strip() or "48000")
                if sample_rate not in [44100, 48000, 96000]:
                    raise ValueError
            except Exception:
                messagebox.showwarning("Invalid Sample Rate", "Sample rate must be 44100, 48000, or 96000 Hz. Using 48000.")
                sample_rate = 48000

        if not outp and not near_sources:
            # Auto-generate output path
            if os.path.isfile(inp):
                outp = os.path.join(os.path.dirname(inp), "AAFs")
            else:
                parent_dir = os.path.dirname(inp.rstrip('/\\'))
                dir_name = os.path.basename(inp.rstrip('/\\'))
                outp = os.path.join(parent_dir, "AAFs", dir_name)

        cancel_event.clear()
        run_btn.configure(state='disabled')
        cancel_btn.configure(state='normal')

        def complete(success: bool, cancelled: bool = False, error_msg: Optional[str] = None):
            run_btn.configure(state='normal')
            cancel_btn.configure(state='disabled')
            if cancelled:
                messagebox.showinfo("Cancelled", "WAV to AAF conversion was cancelled.")
            elif success:
                messagebox.showinfo("Done", "WAV to AAF conversion completed.")
            elif error_msg:
                messagebox.showerror("Error", f"WAV to AAF conversion failed: {error_msg}")

        def worker():
            current_outp = outp
            root.after(0, lambda: log("Starting WAV to AAF conversion…"))
            root.after(0, lambda: log(f"Frame rate: {fps} fps"))
            root.after(0, lambda: log(f"Audio mode: Embedded ({bit_depth}-bit, {sample_rate}Hz)"))

            last_outputs['paths'].clear()

            try:
                processor = WAVsToAAFProcessor()

                if os.path.isfile(inp):
                    # Single file processing
                    if not current_outp:
                        current_outp = os.path.join(os.path.dirname(inp), "AAFs")
                    os.makedirs(current_outp, exist_ok=True)
                    base = os.path.splitext(os.path.basename(inp))[0]
                    dest = os.path.join(current_outp, base + ".aaf")

                    result = processor.process_single_file(
                        inp, dest, fps=fps, embed_audio=embed_audio,
                        link_mode=link_mode, relative_locators=relative_locators,
                        bit_depth=bit_depth, sample_rate=sample_rate
                    )

                    if result == 0:
                        log(f"✓ Success: {dest}")
                        last_outputs['paths'].append(current_outp)
                    else:
                        log("✗ Failed to process file")

                else:
                    # Directory processing
                    result = processor.process_directory(
                        inp, current_outp, fps=fps, embed_audio=embed_audio,
                        link_mode=link_mode, emit_ale=emit_ale, one_aaf=one_aaf,
                        near_sources=near_sources, tape_mode=tape_mode,
                        relative_locators=relative_locators,
                        bit_depth=bit_depth, sample_rate=sample_rate,
                        cancel_event=cancel_event
                    )

                    if result == 0:
                        log("✓ Batch processing completed")
                        if outp:
                            last_outputs['paths'].append(outp)
                    else:
                        log("✗ Batch processing failed")

                # Expose output folder button
                try:
                    root.after(0, lambda: open_btn.pack(side='left', padx=(8, 0)))
                    root.after(0, lambda: open_btn.configure(state='normal'))
                except Exception:
                    pass

                if cancel_event.is_set():
                    root.after(0, lambda: complete(False, cancelled=True))
                else:
                    root.after(0, lambda: complete(True))

            except Exception as e:
                error_str = str(e)
                if "cancelled" in error_str.lower():
                    root.after(0, lambda: complete(False, cancelled=True))
                elif error_str.strip():
                    root.after(0, lambda: log(f"Error: {e}"))
                    root.after(0, lambda: complete(False, error_msg=str(e)))
                else:
                    root.after(0, lambda: complete(False, error_msg=error_str))
                try:
                    root.after(0, lambda: progress_var.set(""))
                except Exception:
                    pass
            finally:
                root.after(0, lambda: run_btn.configure(state='normal'))
                root.after(0, lambda: cancel_btn.configure(state='disabled'))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def cancel_clicked():
        """Handle the Cancel button click"""
        cancel_event.set()
        log("Cancelling operation...")

    def open_output_location():
        """Open the output directory in file explorer"""
        if last_outputs['paths']:
            path = last_outputs['paths'][-1]
            try:
                if sys.platform == "win32":
                    os.startfile(path)
                elif sys.platform == "darwin":
                    os.system(f"open '{path}'")
                else:
                    os.system(f"xdg-open '{path}'")
            except Exception as e:
                messagebox.showerror("Error", f"Could not open output location: {e}")

    def show_about():
        about = tk.Toplevel(root)
        about.title("About WAVsToAAF")
        about.geometry("420x260")
        about.transient(root)
        about.grab_set()

        app_version = get_app_version()

        ttk.Label(about, text=f"WAVsToAAF v{app_version}", font=(None, 12, "bold")).pack(pady=(10, 2))
        ttk.Label(about, text="WAV to AAF Converter", font=(None, 10)).pack()
        ttk.Label(about, text="© Jason Brodkey", font=(None, 10)).pack(pady=(0, 10))

        ttk.Button(about, text="Close", command=about.destroy).pack(pady=(8, 12))

    def show_license():
        lic_win = tk.Toplevel(root)
        lic_win.title("License Information")
        lic_win.geometry("720x560")
        lic_win.transient(root)
        lic_win.grab_set()

        license_text = load_text_file(["LICENSES.txt", "LICENSE.txt", "LICENSE"])

        ttk.Label(lic_win, text="License Information", font=(None, 12, "bold")).pack(pady=(10, 4))
        box = ScrolledText(lic_win, height=28, wrap='word')
        box.pack(fill='both', expand=True, padx=12, pady=(2, 12))
        box.insert('1.0', license_text)
        box.configure(state='disabled')
        ttk.Button(lic_win, text="Close", command=lic_win.destroy).pack(pady=(0, 10))

    def show_help():
        help_win = tk.Toplevel(root)
        help_win.title("WAVsToAAF Help")
        help_win.geometry("780x600")
        help_win.transient(root)
        help_win.grab_set()

        readme_file = "README.md"
        help_text = load_text_file([readme_file])

        ttk.Label(help_win, text="WAVsToAAF Help", font=(None, 12, "bold")).pack(pady=(10, 4))
        box = ScrolledText(help_win, height=34, wrap='word')
        box.pack(fill='both', expand=True, padx=12, pady=(2, 12))
        box.insert('1.0', help_text)
        box.configure(state='disabled')
        ttk.Button(help_win, text="Close", command=help_win.destroy).pack(pady=(0, 10))

    # Layout
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill='both', expand=True)

    # Menu bar
    menubar = tk.Menu(root)
    root.config(menu=menubar)

    # File menu
    file_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Exit", command=root.quit)

    # Help menu
    help_menu = tk.Menu(menubar, tearoff=0)
    menubar.add_cascade(label="Help", menu=help_menu)
    help_menu.add_command(label="About", command=show_about)
    help_menu.add_command(label="License", command=show_license)
    help_menu.add_command(label="Help", command=show_help)

    # Input section
    input_frame = ttk.LabelFrame(frm, text="Input", padding=10)
    input_frame.pack(fill='x', pady=(0, 10))

    input_row = ttk.Frame(input_frame)
    input_row.pack(fill='x')

    ttk.Label(input_row, text="WAV File or Directory:").pack(side='left')
    input_entry = ttk.Entry(input_row, textvariable=input_var)
    input_entry.pack(side='left', fill='x', expand=True, padx=(8, 0))

    # Add drag-and-drop support if available
    if HAS_DND:
        input_entry.drop_target_register(DND_FILES)
        input_entry.dnd_bind('<<Drop>>', handle_input_drop)

    browse_file_btn = ttk.Button(input_row, text="Browse File", command=browse_input)
    browse_file_btn.pack(side='left', padx=(8, 0))
    browse_dir_btn = ttk.Button(input_row, text="Browse Directory", command=browse_input_dir)
    browse_dir_btn.pack(side='left', padx=(4, 0))

    # Output section
    output_frame = ttk.LabelFrame(frm, text="Output", padding=10)
    output_frame.pack(fill='x', pady=(0, 10))

    output_row = ttk.Frame(output_frame)
    output_row.pack(fill='x')

    ttk.Label(output_row, text="Output Directory:").pack(side='left')
    output_entry = ttk.Entry(output_row, textvariable=out_var)
    output_entry.pack(side='left', fill='x', expand=True, padx=(8, 0))

    # Add drag-and-drop support if available
    if HAS_DND:
        output_entry.drop_target_register(DND_FILES)
        output_entry.dnd_bind('<<Drop>>', handle_output_drop)

    browse_output_btn = ttk.Button(output_row, text="Browse", command=browse_output)
    browse_output_btn.pack(side='left', padx=(8, 0))

    # Advanced options (collapsible)
    adv_frame = ttk.Frame(frm)
    adv_frame.pack(fill='x', pady=(0, 10))

    adv_expanded = tk.BooleanVar(value=False)

    def toggle_advanced():
        if adv_expanded.get():
            adv_container.pack_forget()
            adv_expanded.set(False)
            adv_btn.configure(text="Advanced ▼")
        else:
            adv_container.pack(fill='x', pady=(0, 8), before=buttons_row)
            adv_expanded.set(True)
            adv_btn.configure(text="Advanced ▲")

    adv_btn = ttk.Button(adv_frame, text="Advanced ▼", command=toggle_advanced, width=12)
    adv_btn.pack(side='left')

    # Advanced container
    adv_container = ttk.Frame(frm)
    # Pack after GUI creation so toggle can position it consistently
    adv_container.pack_forget()

    # Embedded audio settings
    audio_frame = ttk.Frame(adv_container)
    audio_frame.pack(fill='x', pady=(0, 8))

    embed_opts_frame = ttk.Frame(audio_frame)
    embed_opts_frame.pack(fill='x', pady=(4, 0))

    ttk.Label(embed_opts_frame, text="Bit Depth:").pack(side='left')
    bit_depth_combo = ttk.Combobox(embed_opts_frame, textvariable=bit_depth_var, values=["16", "24"], state="readonly", width=4)
    bit_depth_combo.pack(side='left', padx=(4, 0))

    ttk.Label(embed_opts_frame, text="Sample Rate (Hz):").pack(side='left', padx=(12, 0))
    sample_rate_combo = ttk.Combobox(embed_opts_frame, textvariable=sample_rate_var, values=["44100", "48000", "96000"], state="readonly", width=8)
    sample_rate_combo.pack(side='left', padx=(4, 0))

    ttk.Label(embed_opts_frame, text="Frame Rate (FPS):").pack(side='left', padx=(12, 0))
    fps_combo = ttk.Combobox(embed_opts_frame, textvariable=fps_var, values=["23.976", "24", "25", "29.97", "30"], state="readonly", width=8)
    fps_combo.pack(side='left', padx=(4, 0))

    adv_container.pack_forget()

    # Action buttons
    buttons_row = ttk.Frame(frm)
    buttons_row.pack(fill='x', pady=(0, 8))
    run_btn = ttk.Button(buttons_row, text="Run", command=run_clicked)
    run_btn.pack(side='left')
    cancel_btn = ttk.Button(buttons_row, text="Cancel", command=cancel_clicked, state='disabled')
    cancel_btn.pack(side='left', padx=(8, 0))
    open_btn = ttk.Button(buttons_row, text="Open AAF Location", command=open_output_location, state='disabled')
    open_btn.pack(side='left', padx=(8, 0))
    open_btn.pack_forget()  # Hide initially

    # Status bar
    status_label = ttk.Label(frm, textvariable=status_var, foreground="blue")
    status_label.pack(fill='x', pady=(0, 8))

    # Progress bar
    progress_label = ttk.Label(frm, textvariable=progress_var, foreground="green")
    progress_label.pack(fill='x', pady=(0, 8))

    # Log area
    log_frame = ttk.LabelFrame(frm, text="Log", padding=8)
    log_frame.pack(fill='both', expand=True, pady=(0, 8))

    log_text = ScrolledText(log_frame, height=12, wrap='word', state='disabled')
    log_text.pack(fill='both', expand=True)

    # Footer
    footer = ttk.Frame(frm)
    footer.pack(fill='x', pady=(0, 4))
    footer.columnconfigure(0, weight=1)
    footer.columnconfigure(1, weight=1)
    footer.columnconfigure(2, weight=1)

    left_lbl = ttk.Label(footer, text="© Jason Brodkey", foreground="#555555", anchor='w', justify='left')
    left_lbl.grid(row=0, column=0, sticky='w')

    def open_website(event=None):
        webbrowser.open_new_tab("https://www.editcandy.com")

    center_lbl = ttk.Label(footer, text="www.editcandy.com", foreground="#4ea3ff", cursor='hand2', anchor='center', justify='center')
    center_lbl.grid(row=0, column=1)
    center_lbl.bind("<Button-1>", open_website)

    right_lbl = ttk.Label(footer, text=f"v{get_app_version()}", foreground="#555555", anchor='e', justify='right')
    right_lbl.grid(row=0, column=2, sticky='e')

    # Redirect stdout to log
    class StdoutRedirector:
        def __init__(self):
            self.last_was_carriage_return = False

        def write(self, message):
            if not message:
                return

            # Handle carriage return (\r) - used by progress bars to update same line
            if '\r' in message:
                # Split by \r and process each part
                parts = message.split('\r')
                for i, part in enumerate(parts):
                    if not part.strip():
                        continue

                    if i > 0 or self.last_was_carriage_return:
                        # Replace last line in log
                        log_text.configure(state='normal')
                        log_text.delete("end-2l", "end-1l")
                        log_text.configure(state='disabled')

                    if part.strip():
                        log(part.rstrip('\n'))

                self.last_was_carriage_return = True
            else:
                # Normal output
                if message.strip():
                    log(message.rstrip('\n'))
                self.last_was_carriage_return = False

        def flush(self):
            pass

    sys.stdout = StdoutRedirector()

    root.mainloop()


def main():
    launch_gui()


if __name__ == "__main__":
    main()
