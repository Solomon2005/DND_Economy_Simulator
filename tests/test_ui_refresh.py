"""Проверка BUG_001: новые поселения видны в списках без перезапуска."""
import pytest


@pytest.fixture(scope="module")
def root():
    ctk = pytest.importorskip("customtkinter")
    try:
        window = ctk.CTk()
    except Exception as exc:  # нет графической среды
        pytest.skip(f"Tk недоступен: {exc}")
    window.withdraw()
    yield window
    window.destroy()


def _new_settlement(campaign_id, name="Новое"):
    from app.services.settlement_service import SettlementService
    return SettlementService().create_settlement(
        campaign_id, name, "village", 100)


def test_routes_view_updates_after_settlement_created(campaign_id, root):
    from app.ui.views.routes_view import RoutesView
    view = RoutesView(root, campaign_id)
    _new_settlement(campaign_id)
    view.refresh()
    assert "Новое" in view.from_combo.cget("values")
    assert "Новое" in view.to_combo.cget("values")
    assert view._by_name["Новое"] > 0


def test_inventory_view_updates_after_settlement_created(campaign_id, root):
    from app.ui.views.inventory_view import InventoryView
    view = InventoryView(root, campaign_id)
    _new_settlement(campaign_id)
    view.refresh()
    assert "Новое" in view.settlement_combo.cget("values")


def test_inventory_view_shows_all_settlements(campaign_id, root):
    from app.services.inventory_service import InventoryService
    from app.services.resource_service import ResourceService
    from app.ui.views.inventory_view import InventoryView
    first = _new_settlement(campaign_id, "Первое")
    second = _new_settlement(campaign_id, "Второе")
    resource = ResourceService().create_resource(
        campaign_id, "Товар", "Прочее", "шт", 10)
    inventory = InventoryService()
    inventory.add_entry(first.id, resource.id)
    inventory.add_entry(second.id, resource.id)

    view = InventoryView(root, campaign_id)
    view.refresh()
    rows = [view.tree.item(iid, "values") for iid in view.tree.get_children()]
    assert {"Первое", "Второе"} <= {row[0] for row in rows}


def test_transactions_view_updates_after_settlement_created(campaign_id, root):
    from app.ui.views.transactions_view import TransactionsView
    view = TransactionsView(root, campaign_id)
    _new_settlement(campaign_id)
    view.refresh()
    assert "Новое" in view.settlement_combo.cget("values")
    assert "Новое" in view._settlement_by_name


def test_traders_view_updates_after_settlement_created(campaign_id, root):
    from app.ui.views.traders_view import TradersView
    view = TradersView(root, campaign_id)
    _new_settlement(campaign_id)
    view.refresh()
    assert "Новое" in view.home_combo.cget("values")


def test_history_view_reset_clears_events(campaign_id, root, monkeypatch):
    from tkinter import messagebox

    from app.database.models import EconomicEvent
    from app.database.session import session_scope
    from app.ui.views.history_view import HistoryView

    settlement = _new_settlement(campaign_id)
    with session_scope() as s:
        s.add(EconomicEvent(
            campaign_id=campaign_id, game_hour=1, category="purchase",
            settlement_id=settlement.id, description="Тестовое событие"))

    view = HistoryView(root, campaign_id)
    view.refresh()
    assert view.tree.get_children()

    monkeypatch.setattr(messagebox, "askyesno", lambda *a, **k: True)
    view._reset_history()

    assert not view.tree.get_children()
    with session_scope() as s:
        assert s.query(EconomicEvent).filter_by(
            campaign_id=campaign_id).count() == 0


def test_charts_view_updates_after_new_resource_and_settlement(
        campaign_id, root):
    from app.services.resource_service import ResourceService
    from app.visualization.economic_charts import EconomicChartsView
    view = EconomicChartsView(root, campaign_id)
    _new_settlement(campaign_id)
    resource = ResourceService().create_resource(
        campaign_id, "Новый ресурс", "Прочее", "шт", 10)
    view.refresh()
    assert "Новое" in view.settlement_combo.cget("values")
    assert resource.name in view.resource_combo.cget("values")
