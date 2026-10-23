import tkinter as tk

import pytest

import drawing

try:
    ROOT = tk.Tk()  # one interpreter for the whole module; each test gets its own window
    ROOT.withdraw()
except tk.TclError:  # no display (e.g. headless CI)
    pytest.skip("Tk display not available", allow_module_level=True)


class Event:
    def __init__(self, x, y):
        self.x, self.y = x, y


@pytest.fixture
def app():
    window = tk.Toplevel(ROOT)
    yield drawing.Sketchpad(window)
    window.destroy()


def draw(app, points, color="#e53935"):
    app.set_color(color)
    app.start_stroke(Event(*points[0]))
    for p in points[1:]:
        app.extend_stroke(Event(*p))
    app.end_stroke(None)


def test_undo_redo_restores_strokes(app):
    draw(app, [(10, 10), (50, 50)])
    draw(app, [(60, 10), (90, 40)])
    app.undo()
    assert len(app.strokes) == 1 and len(app.redo_stack) == 1
    app.redo()
    assert len(app.strokes) == 2 and not app.redo_stack


def test_new_stroke_clears_redo(app):
    draw(app, [(10, 10), (20, 20)])
    app.undo()
    draw(app, [(30, 30), (40, 40)])
    assert not app.redo_stack


def test_saved_png_contains_the_drawing(app, tmp_path):
    draw(app, [(100, 100), (200, 100)], color="#1e88e5")
    path = app.save(str(tmp_path / "out.png"))
    from PIL import Image
    img = Image.open(path).convert("RGB")
    assert img.size == (drawing.CANVAS_W, drawing.CANVAS_H)
    assert img.getpixel((150, 100)) == (0x1E, 0x88, 0xE5)
    assert img.getpixel((5, 5)) == (255, 255, 255)


def test_eraser_paints_background(app):
    app.toggle_eraser()
    app.start_stroke(Event(5, 5))
    assert app.current.color == app.background
