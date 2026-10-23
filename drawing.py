"""Sketchpad: a small Tkinter drawing app.

Every stroke is drawn twice: on the Tk canvas (what you see) and on an off-screen
Pillow image (what gets saved). That makes "Save" a real PNG export instead of a
screen grab, and lets undo/redo rebuild both from the stroke history.

    python drawing.py
"""
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw

CANVAS_W, CANVAS_H = 900, 600
PALETTE = ["#000000", "#ffffff", "#e53935", "#fb8c00", "#fdd835", "#43a047",
           "#1e88e5", "#3949ab", "#8e24aa", "#d81b60", "#6d4c41", "#757575"]


@dataclass
class Stroke:
    color: str
    width: int
    points: List[Tuple[int, int]] = field(default_factory=list)


class Sketchpad:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Sketchpad")
        root.resizable(False, False)

        self.color = "#000000"
        self.background = "#ffffff"
        self.eraser_on = False
        self.strokes: List[Stroke] = []
        self.redo_stack: List[Stroke] = []
        self.current: Optional[Stroke] = None

        self._build_toolbar()
        self.canvas = tk.Canvas(root, width=CANVAS_W, height=CANVAS_H, bg=self.background,
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(padx=8, pady=(0, 4))
        self.status = ttk.Label(root, anchor="w")
        self.status.pack(fill="x", padx=8, pady=(0, 6))

        self.canvas.bind("<ButtonPress-1>", self.start_stroke)
        self.canvas.bind("<B1-Motion>", self.extend_stroke)
        self.canvas.bind("<ButtonRelease-1>", self.end_stroke)
        root.bind("<Control-z>", lambda e: self.undo())
        root.bind("<Control-y>", lambda e: self.redo())
        root.bind("<Control-s>", lambda e: self.save())
        root.bind("e", lambda e: self.toggle_eraser())
        root.bind("<bracketleft>", lambda e: self.size.set(max(1, self.size.get() - 2)))
        root.bind("<bracketright>", lambda e: self.size.set(min(60, self.size.get() + 2)))

        self._reset_image()
        self._update_status()

    # ------------------------------------------------------------------ UI
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=8)
        bar.pack(fill="x")

        swatches = ttk.Frame(bar)
        swatches.pack(side="left")
        for i, c in enumerate(PALETTE):
            tk.Button(swatches, bg=c, activebackground=c, width=2, relief="ridge", bd=1,
                      command=lambda col=c: self.set_color(col)).grid(row=i // 6, column=i % 6, padx=1, pady=1)
        self.preview = tk.Label(bar, width=4, bg=self.color, relief="sunken")
        self.preview.pack(side="left", padx=(8, 4), ipady=8)
        ttk.Button(bar, text="Custom…", command=self.pick_color).pack(side="left", padx=2)

        ttk.Label(bar, text="Size").pack(side="left", padx=(12, 2))
        self.size = tk.IntVar(value=4)
        ttk.Scale(bar, from_=1, to=60, variable=self.size, length=140,
                  command=lambda _v: self._update_status()).pack(side="left")

        self.eraser_btn = ttk.Button(bar, text="Eraser (E)", command=self.toggle_eraser)
        self.eraser_btn.pack(side="left", padx=(12, 2))
        ttk.Button(bar, text="Undo", command=self.undo).pack(side="left", padx=2)
        ttk.Button(bar, text="Redo", command=self.redo).pack(side="left", padx=2)
        ttk.Button(bar, text="Background…", command=self.pick_background).pack(side="left", padx=2)
        ttk.Button(bar, text="Clear", command=self.clear).pack(side="left", padx=2)
        ttk.Button(bar, text="Save PNG", command=self.save).pack(side="left", padx=(12, 2))

    def _update_status(self) -> None:
        tool = "Eraser" if self.eraser_on else f"Brush {self.color}"
        self.status.config(text=f"{tool} · size {int(self.size.get())} · {len(self.strokes)} strokes"
                                "   |   Ctrl+Z undo · Ctrl+Y redo · Ctrl+S save · E eraser · [ ] size")

    # -------------------------------------------------------------- tools
    def set_color(self, color: str) -> None:
        self.color, self.eraser_on = color, False
        self.preview.config(bg=color)
        self._update_status()

    def pick_color(self) -> None:
        color = colorchooser.askcolor(color=self.color, title="Brush colour")[1]
        if color:
            self.set_color(color)

    def pick_background(self) -> None:
        color = colorchooser.askcolor(color=self.background, title="Background colour")[1]
        if color:
            self.background = color
            self.redraw()

    def toggle_eraser(self) -> None:
        self.eraser_on = not self.eraser_on
        self._update_status()

    # ------------------------------------------------------------ drawing
    def start_stroke(self, event) -> None:
        # Eraser strokes paint with the background colour, so they undo like any stroke
        color = self.background if self.eraser_on else self.color
        self.current = Stroke(color=color, width=int(self.size.get()), points=[(event.x, event.y)])
        self._draw_dot(self.current, event.x, event.y)

    def extend_stroke(self, event) -> None:
        if not self.current:
            return
        x0, y0 = self.current.points[-1]
        self.current.points.append((event.x, event.y))
        self._draw_segment(self.current, x0, y0, event.x, event.y)

    def end_stroke(self, _event) -> None:
        if self.current:
            self.strokes.append(self.current)
            self.redo_stack.clear()
            self.current = None
            self._update_status()

    def _draw_dot(self, s: Stroke, x: int, y: int) -> None:
        r = s.width / 2
        self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=s.color, outline=s.color)
        self.draw.ellipse([x - r, y - r, x + r, y + r], fill=s.color)

    def _draw_segment(self, s: Stroke, x0, y0, x1, y1) -> None:
        self.canvas.create_line(x0, y0, x1, y1, fill=s.color, width=s.width,
                                capstyle=tk.ROUND, joinstyle=tk.ROUND, smooth=True)
        self.draw.line([x0, y0, x1, y1], fill=s.color, width=s.width)
        r = s.width / 2  # round joints on the saved image too
        self.draw.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=s.color)

    def _replay(self, s: Stroke) -> None:
        self._draw_dot(s, *s.points[0])
        for (x0, y0), (x1, y1) in zip(s.points, s.points[1:]):
            self._draw_segment(s, x0, y0, x1, y1)

    def _reset_image(self) -> None:
        self.image = Image.new("RGB", (CANVAS_W, CANVAS_H), self.background)
        self.draw = ImageDraw.Draw(self.image)

    def redraw(self) -> None:
        self.canvas.delete("all")
        self.canvas.config(bg=self.background)
        self._reset_image()
        for s in self.strokes:
            self._replay(s)
        self._update_status()

    # ------------------------------------------------------- history/file
    def undo(self) -> None:
        if self.strokes:
            self.redo_stack.append(self.strokes.pop())
            self.redraw()

    def redo(self) -> None:
        if self.redo_stack:
            self.strokes.append(self.redo_stack.pop())
            self.redraw()

    def clear(self) -> None:
        if self.strokes and messagebox.askyesno("Clear canvas", "Erase everything? You can't undo this."):
            self.strokes.clear()
            self.redo_stack.clear()
            self.redraw()

    def save(self, path: Optional[str] = None) -> Optional[str]:
        path = path or filedialog.asksaveasfilename(defaultextension=".png",
                                                    filetypes=[("PNG image", "*.png"), ("JPEG image", "*.jpg")])
        if not path:
            return None
        self.image.save(path)
        self.status.config(text=f"Saved {path}")
        return path


def enable_high_dpi() -> None:
    """Crisp rendering on scaled Windows displays (no-op elsewhere)."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


if __name__ == "__main__":
    enable_high_dpi()
    root = tk.Tk()
    Sketchpad(root)
    root.mainloop()
