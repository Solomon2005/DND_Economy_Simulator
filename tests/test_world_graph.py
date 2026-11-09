"""Карта мира: сохранение позиций узлов и перетаскивание."""
from types import SimpleNamespace

from app.visualization.world_graph import WorldGraphView


def _blank_view() -> WorldGraphView:
    """Экземпляр без Tk: только состояние, нужное обработчикам."""
    view = WorldGraphView.__new__(WorldGraphView)
    view._draw = lambda: None
    view._show_info = lambda _sid: None
    return view


def test_ensure_positions_keeps_dragged_node_and_adds_new():
    view = _blank_view()
    view._positions = {1: (0.5, 0.5), 2: (-0.5, 0.0)}
    settlements = [SimpleNamespace(id=1), SimpleNamespace(id=2),
                   SimpleNamespace(id=3)]

    view._ensure_positions(settlements, [])

    assert view._positions[1] == (0.5, 0.5)
    assert view._positions[2] == (-0.5, 0.0)
    assert 3 in view._positions


def test_ensure_positions_drops_deleted_settlement():
    view = _blank_view()
    view._positions = {1: (0.0, 0.0), 2: (1.0, 1.0)}

    view._ensure_positions([SimpleNamespace(id=1)], [])

    assert set(view._positions) == {1}


def test_press_selects_nearest_node_and_starts_drag():
    view = _blank_view()
    view._positions = {1: (0.0, 0.0), 2: (1.0, 1.0)}
    view._selected = None
    view._drag_id = None

    view._on_press(SimpleNamespace(inaxes=object(), xdata=0.02, ydata=-0.01))

    assert view._selected == 1
    assert view._drag_id == 1


def test_motion_moves_node_and_release_stops_drag():
    view = _blank_view()
    view._positions = {1: (0.0, 0.0)}
    view._drag_id = 1

    view._on_motion(SimpleNamespace(inaxes=object(), xdata=0.4, ydata=0.2))
    assert view._positions[1] == (0.4, 0.2)

    view._on_release(SimpleNamespace())
    assert view._drag_id is None
