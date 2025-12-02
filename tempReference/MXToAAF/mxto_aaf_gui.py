#!/usr/bin/env python3
"""
MXToAAF GUI - Graphical User Interface for Music to AAF Conversion

A graphical interface for converting music files (mp3, m4a, aif, wav) to AAFs for Avid import.
Provides file/folder browsing, embed option, CSV export, and real-time processing feedback.

Author: Jason Brodkey
Version: 0.9.0
Date: 2025-11-30
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import os
import sys
import threading
import subprocess
import webbrowser

from mxto_aaf.__version__ import __version__
from mxto_aaf.batch import process_directory
from mxto_aaf.metadata import extract_music_metadata
from mxto_aaf.aaf import create_music_aaf
from mxto_aaf.utils import convert_to_wav


def launch_gui():
    root = tk.Tk()
    root.title("MXToAAF - Music to AAF Converter")
    root.geometry("680x520")
    # Use native theme only; do not paint custom colors so Aqua/Vista control appearance
    # This mirrors WAVsToALE behavior exactly.
    try:
        style = ttk.Style()
        if sys.platform == 'darwin' and 'aqua' in style.theme_names():
            style.theme_use('aqua')
    except Exception:
        pass

    # Variables
    input_var = tk.StringVar()
    out_var = tk.StringVar()
    fps_var = tk.StringVar(value="24")
    embed_var = tk.BooleanVar(value=True)
    csv_var = tk.BooleanVar(value=False)
    meta_csv_var = tk.BooleanVar(value=False)
    last_outputs = {'paths': []}
    status_var = tk.StringVar(value="")
    cancel_event = threading.Event()

    def log(msg):
        log_text.configure(state='normal')
        log_text.insert('end', str(msg) + "\n")
        log_text.see('end')
        log_text.configure(state='disabled')
        # Track output folder for Open button
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
        except Exception:
            pass

    def browse_input_file():
        path = filedialog.askopenfilename(
            title="Select music file",
            filetypes=[("Audio Files", "*.mp3 *.m4a *.wav *.aif *.aiff"), ("All Files", "*.*")]
        )
        if path:
            input_var.set(path)

    def browse_input_dir():
        path = filedialog.askdirectory(title="Select music directory")
        if path:
            input_var.set(path)

    def browse_out():
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            out_var.set(path)

    def run_clicked():
        inp = input_var.get().strip()
        outp = out_var.get().strip()
        embed = embed_var.get()
        export_csv = csv_var.get()
        export_meta_csv = meta_csv_var.get()
        
        # Parse FPS
        try:
            fps = float(fps_var.get().strip() or "24")
            if fps <= 0:
                raise ValueError
        except Exception:
            messagebox.showwarning("Invalid FPS", "FPS must be a positive number (e.g. 24 or 23.976). Using 24.")
            fps = 24.0

        if not inp:
            messagebox.showerror("Missing input", "Please select a music file or directory.")
            return
        if not outp:
            outp = os.path.join(os.path.dirname(inp), "aaf_output") if os.path.isfile(inp) else os.path.join(inp, "aaf_output")
            out_var.set(outp)

        cancel_event.clear()
        run_btn.configure(state='disabled')
        cancel_btn.configure(state='normal')

        def worker():
            log("Starting conversion…")
            log(f"Frame rate: {fps} fps")
            log(f"Embed audio: {'Yes' if embed else 'No'}")
            log(f"Input: {inp}")
            log(f"Output: {outp}")
            # Animate dots to show activity before first progress line
            import time
            log_text.configure(state='normal')
            log_text.insert('end', 'Processing')
            log_text.see('end')
            log_text.configure(state='disabled')
            for i in range(1, 11):
                log_text.configure(state='normal')
                log_text.insert('end', '.')
                log_text.see('end')
                log_text.configure(state='disabled')
                time.sleep(0.175)  # 175ms per dot = 1.75s total
            log("")  # newline after dots
            last_outputs['paths'].clear()
            try:
                if os.path.isdir(inp):
                    summary = process_directory(
                        inp,
                        outp,
                        recursive=True,
                        embed=embed,
                        skip_existing=True,
                        export_csv=os.path.join(outp, "results.csv") if export_csv else None,
                        export_metadata_csv=os.path.join(outp, "metadata.csv") if export_meta_csv else None,
                        fps=fps,
                    )
                    log(f"✓ Success: {summary['success_count']}")
                    log(f"✗ Failed: {summary['failed_count']}")
                    log(f"⊘ Skipped: {summary['skipped_count']}")
                    log(f"Duration: {summary['total_duration']:.1f}s")
                    log(f"Output: {outp}")
                else:
                    # Single-file processing
                    os.makedirs(outp, exist_ok=True)
                    base = os.path.splitext(os.path.basename(inp))[0]
                    dest = os.path.join(outp, base + ".aaf")
                    import time as _time
                    t0 = _time.time()
                    md = extract_music_metadata(str(inp))
                    created = None
                    try:
                        if embed and not inp.lower().endswith('.wav'):
                            tmp = os.path.join(outp, base + ".tmp.wav")
                            convert_to_wav(str(inp), tmp)
                            created = create_music_aaf(tmp, md, dest, embed=True, tag_map=None, fps=fps)
                            try:
                                os.remove(tmp)
                            except Exception:
                                pass
                        else:
                            created = create_music_aaf(str(inp), md, dest, embed=embed, tag_map=None, fps=fps)
                        dur = _time.time() - t0
                        log(f"✓ Created: {created}")
                        log(f"Duration: {dur:.1f}s")
                        # Optional CSV outputs for single-file
                        if export_csv:
                            try:
                                csv_path = os.path.join(outp, "results.csv")
                                import csv as _csv
                                write_header = not os.path.exists(csv_path)
                                with open(csv_path, "a", newline="", encoding="utf-8") as f:
                                    w = _csv.writer(f)
                                    if write_header:
                                        w.writerow(["input", "output", "status", "error", "duration_s"])
                                    w.writerow([inp, created, "success", "", f"{dur:.3f}"])
                            except Exception as _e:
                                log(f"Warning: unable to write CSV report: {_e}")
                        if export_meta_csv:
                            try:
                                mpath = os.path.join(outp, "metadata.csv")
                                import csv as _csv
                                write_header = not os.path.exists(mpath)
                                with open(mpath, "a", newline="", encoding="utf-8") as f:
                                    w = _csv.writer(f)
                                    if write_header:
                                        w.writerow([
                                            "input","output","status","error","duration_s",
                                            "Track Name","Track","Total Tracks","Genre","Artist","Album Artist","Talent","Composer","Source","Album","Catalog #","Description","Duration"
                                        ])
                                    w.writerow([
                                        inp, created, "success", "", f"{dur:.3f}",
                                        md.track_name, md.track, md.total_tracks, md.genre, md.artist, md.album_artist,
                                        md.talent, md.composer, md.source, md.album, md.catalog_number, md.description, md.duration
                                    ])
                            except Exception as _e:
                                log(f"Warning: unable to write metadata CSV: {_e}")
                        # Expose output folder button
                        try:
                            open_btn.pack(side='left', padx=(8, 0))
                            open_btn.configure(state='normal')
                        except Exception:
                            pass
                    except Exception as e:
                        # Re-raise single-file errors to outer handler
                        raise e

                try:
                    open_btn.pack(side='left', padx=(8, 0))
                    open_btn.configure(state='normal')
                except Exception:
                    pass
                messagebox.showinfo("Done", "AAF creation completed.")
            except Exception as e:
                if str(e).strip():  # Only show error if there's actually an error message
                    log(f"Error: {e}")
                    try:
                        status_var.set("Error — see log")
                    except Exception:
                        pass
                    messagebox.showerror("Error", f"AAF creation failed: {e}")
            finally:
                run_btn.configure(state='normal')
                cancel_btn.configure(state='disabled')

        threading.Thread(target=worker, daemon=True).start()

    def cancel_clicked():
        cancel_event.set()
        log("Cancellation requested…")

    def clear_log():
        log_text.configure(state='normal')
        log_text.delete('1.0', 'end')
        log_text.configure(state='disabled')
        input_var.set('')
        out_var.set('')
        try:
            open_btn.pack_forget()
            open_btn.configure(state='disabled')
        except Exception:
            pass

    def open_output_location():
        outp = out_var.get().strip()
        if outp and os.path.isdir(outp):
            try:
                if sys.platform == 'darwin':
                    subprocess.run(['open', outp], check=False)
                elif sys.platform == 'win32':
                    os.startfile(outp)
                else:
                    subprocess.run(['xdg-open', outp], check=False)
            except Exception:
                messagebox.showwarning("Open Location", "Could not open the AAF location.")

    # Layout
    frm = ttk.Frame(root, padding=12)
    frm.pack(fill='both', expand=True)

    # Input
    ttk.Label(frm, text="Music file or directory").grid(row=0, column=0, sticky='w')
    input_entry = ttk.Entry(frm, textvariable=input_var, width=60)
    input_entry.grid(row=1, column=0, columnspan=2, sticky='we', pady=(1, 0))
    # Place the buttons in a frame in the same row as the entry
    input_btns = ttk.Frame(frm)
    input_btns.grid(row=1, column=2, sticky='w', pady=0)
    ttk.Button(input_btns, text="File…", command=browse_input_file).grid(row=0, column=0, padx=(0, 4), pady=0)
    ttk.Button(input_btns, text="Folder…", command=browse_input_dir).grid(row=0, column=1, pady=0)

    # Output
    ttk.Label(frm, text="Output Folder for AAFs").grid(row=2, column=0, sticky='w', pady=(6, 0))
    out_entry = ttk.Entry(frm, textvariable=out_var, width=60)
    out_entry.grid(row=3, column=0, columnspan=2, sticky='we', pady=(1, 0))
    ttk.Button(frm, text="Browse…", command=browse_out).grid(row=3, column=2, sticky='w', pady=0)

    # FPS
    fps_row = ttk.Frame(frm)
    fps_row.grid(row=4, column=0, columnspan=3, sticky='w', pady=(6, 8))
    ttk.Label(fps_row, text="FPS:").pack(side='left')
    ttk.Entry(fps_row, textvariable=fps_var, width=8).pack(side='left', padx=(4, 0))
    ttk.Label(fps_row, text="(default 24)").pack(side='left', padx=(6, 0))

    # Advanced options toggle (collapsed by default)
    adv_frame = ttk.Frame(frm)
    adv_frame.grid(row=5, column=0, columnspan=3, sticky='w', pady=(0, 4))
    adv_expanded = tk.BooleanVar(value=False)

    def toggle_advanced():
        if adv_expanded.get():
            adv_container.grid_remove()
            adv_expanded.set(False)
            adv_btn.configure(text="Advanced ▼")
        else:
            adv_container.grid()
            adv_expanded.set(True)
            adv_btn.configure(text="Advanced ▲")

    adv_btn = ttk.Button(adv_frame, text="Advanced ▼", command=toggle_advanced, width=12)
    adv_btn.pack(side='left')

    # Advanced container with all 3 checkboxes
    adv_container = ttk.Frame(frm)
    adv_container.grid(row=6, column=0, columnspan=3, sticky='w', pady=(0, 8))
    ttk.Checkbutton(adv_container, text="Embed audio in AAF (recommended)", variable=embed_var).pack(side='left')
    ttk.Checkbutton(adv_container, text="Export results CSV", variable=csv_var).pack(side='left', padx=(12, 0))
    ttk.Checkbutton(adv_container, text="Export metadata CSV", variable=meta_csv_var).pack(side='left', padx=(12, 0))
    adv_container.grid_remove()

    # Action buttons
    buttons_row = ttk.Frame(frm)
    buttons_row.grid(row=7, column=0, columnspan=3, sticky='ew', pady=(0, 8))
    run_btn = ttk.Button(buttons_row, text="Run", command=run_clicked)
    run_btn.pack(side='left')
    cancel_btn = ttk.Button(buttons_row, text="Cancel", command=cancel_clicked, state='disabled')
    cancel_btn.pack(side='left', padx=(8, 0))
    open_btn = ttk.Button(buttons_row, text="Open AAF Location", command=open_output_location, state='disabled')
    open_btn.pack(side='left', padx=(8, 0))
    open_btn.pack_forget()  # Hide initially

    # Log area with clear button
    log_header = ttk.Frame(frm)
    log_header.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(0, 2))
    ttk.Label(log_header, text="Output Log").pack(side='left')
    ttk.Button(log_header, text="Clear", command=clear_log, width=8).pack(side='right')

    log_text = ScrolledText(frm, height=16, state='disabled')
    log_text.grid(row=9, column=0, columnspan=3, sticky='nsew')
    frm.rowconfigure(9, weight=1)

    # Copyright, website, and version labels below log
    copyright_font = (None, 10)
    footer = ttk.Frame(frm)
    footer.grid(row=10, column=0, columnspan=3, sticky='ew', pady=(4, 0))

    def open_website(event=None):
        webbrowser.open_new_tab('https://www.editcandy.com')

    left_lbl = ttk.Label(footer, text="© Jason Brodkey", font=copyright_font, anchor='w', justify='left')
    left_lbl.grid(row=0, column=0, sticky='w')

    center_lbl = ttk.Label(footer, text="www.editcandy.com", font=copyright_font, foreground="#4ea3ff", cursor="hand2")
    center_lbl.grid(row=0, column=1)
    center_lbl.bind("<Button-1>", open_website)

    right_lbl = ttk.Label(footer, text=f"v{__version__}", font=copyright_font, anchor='e', justify='right')
    right_lbl.grid(row=0, column=2, sticky='e')

    footer.columnconfigure(0, weight=1)
    footer.columnconfigure(1, weight=1)
    footer.columnconfigure(2, weight=1)

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
    launch_gui()


if __name__ == "__main__":
    main()
