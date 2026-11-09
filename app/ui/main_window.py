"""Основное окно приложения с CustomTkinter."""
import customtkinter as ctk

from app.core.config import load_config
from app.services import get_or_create_campaign
from app.services.resource_service import ResourceService
from app.services.report_service import ReportService
from app.services.settlement_service import SettlementService
from app.services.simulation_service import SimulationService
from app.services.trader_service import TraderService
from app.services.trade_route_service import TradeRouteService
from app.simulation.simulation_clock import SimulationClock
from app.ui.views.resources_view import ResourcesView
from app.ui.views.routes_view import RoutesView
from app.ui.views.settlements_view import SettlementsView
from app.ui.views.simulation_view import SimulationView
from app.ui.views.traders_view import TradersView
from app.ui.views.inventory_view import InventoryView
from app.ui.views.transactions_view import TransactionsView
from app.ui.views.history_view import HistoryView
from app.ui.views.reports_view import ReportsView
from app.ui.views.settings_view import SettingsView
from app.visualization.world_graph import WorldGraphView

CAMPAIGN_ID = get_or_create_campaign()
CLOCK = SimulationClock(CAMPAIGN_ID)
SIMULATION = SimulationService(CAMPAIGN_ID, CLOCK)


def _build_dashboard(container) -> callable:
    """Вкладка «Главная»: показатели экономики и карта мира."""
    title = ctk.CTkLabel(container, text="Экономический дашборд",
                         font=("Arial", 18, "bold"))
    title.pack(pady=(10, 5))

    stats = ctk.CTkLabel(container, text="", font=("Arial", 14), justify="left")
    stats.pack(pady=10, anchor="w", padx=20)

    clear_button = ctk.CTkButton(
        container, text="Очистить историю", fg_color="#8e3b3b",
        hover_color="#6d2d2d")
    clear_button.pack(anchor="w", padx=20, pady=(0, 8))

    world_graph = WorldGraphView(container, CAMPAIGN_ID)

    def refresh() -> None:
        settlements = SettlementService().get_settlements(CAMPAIGN_ID)
        resources = ResourceService().get_resources(CAMPAIGN_ID)
        traders = TraderService().get_traders(CAMPAIGN_ID)
        routes = TradeRouteService().get_routes(CAMPAIGN_ID)
        state = SIMULATION.get_state()
        stats.configure(text=(
            f"Поселений: {len(settlements)}\n"
            f"Ресурсов: {len(resources)}\n"
            f"Торговцев: {len(traders)}\n"
            f"Активных маршрутов: {sum(1 for r in routes if r.enabled)} из "
            f"{len(routes)}\n"
            f"Дата симуляции: {state['date']} (сезон {state['season']})\n"
            f"Статус симуляции: {state['status']}, скорость {state['speed']}x"
        ))
        world_graph.refresh()

    def _clear_history() -> None:
        from tkinter import messagebox
        if not messagebox.askyesno(
                "Очистка истории",
                "Удалить историю сделок, цен, переговоров и журнал событий?\n"
                "Поселения, склады, торговцы, маршруты и капиталы "
                "останутся без изменений.",
                parent=container):
            return
        ReportService().clear_history(CAMPAIGN_ID)
        refresh()

    clear_button.configure(command=_clear_history)

    return refresh


def create_main_window():
    ctk.set_appearance_mode(load_config()["theme"])
    ctk.set_default_color_theme("blue")

    root = ctk.CTk()
    root.title("Симулятор экономики D&D")
    root.geometry("1200x800")
    root.minsize(900, 600)

    # Навигационная панель слева
    nav = ctk.CTkFrame(root, width=180, corner_radius=0)
    nav.pack(side="left", fill="y")

    # Область содержимого справа
    content = ctk.CTkFrame(root)
    content.pack(side="right", fill="both", expand=True)

    # Каждый раздел — свой фрейм; переключение через pack_forget
    frames: dict[str, ctk.CTkFrame] = {}
    refreshers: dict[str, callable] = {}

    def add_section(key: str, label: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(content, corner_radius=0)
        frames[key] = frame
        button = ctk.CTkButton(nav, text=label, anchor="w", width=160,
                               command=lambda: show(key))
        button.pack(pady=4, padx=10)
        return frame

    def show(key: str) -> None:
        for frame in frames.values():
            frame.pack_forget()
        frames[key].pack(fill="both", expand=True)
        refresher = refreshers.get(key)
        if refresher:
            refresher()

    # Секции
    add_section("dashboard", "Главная")
    settlements_frame = add_section("settlements", "Поселения")
    resources_frame = add_section("resources", "Ресурсы")
    inventory_frame = add_section("inventory", "Склады")
    routes_frame = add_section("routes", "Маршруты")
    traders_frame = add_section("traders", "Торговцы")
    simulation_frame = add_section("simulation", "Симуляция")
    transactions_frame = add_section("transactions", "Сделки игроков")
    history_frame = add_section("history", "История")
    reports_frame = add_section("reports", "Отчёты")
    settings_frame = add_section("settings", "Настройки")

    refreshers["dashboard"] = _build_dashboard(frames["dashboard"])
    settlements_view = SettlementsView(settlements_frame, CAMPAIGN_ID)
    resources_view = ResourcesView(resources_frame, CAMPAIGN_ID)
    inventory_view = InventoryView(inventory_frame, CAMPAIGN_ID)
    routes_view = RoutesView(routes_frame, CAMPAIGN_ID)
    traders_view = TradersView(traders_frame, CAMPAIGN_ID)
    simulation_view = SimulationView(simulation_frame, SIMULATION)
    transactions_view = TransactionsView(transactions_frame, CAMPAIGN_ID)
    history_view = HistoryView(history_frame, CAMPAIGN_ID)
    reports_view = ReportsView(reports_frame, CAMPAIGN_ID)
    SettingsView(settings_frame, CLOCK)

    # При переключении раздела вид перечитывает данные из БД: новые поселения,
    # ресурсы и маршруты доступны сразу, без перезапуска приложения.
    refreshers.update({
        "settlements": settlements_view.refresh,
        "resources": resources_view.refresh,
        "inventory": inventory_view.refresh,
        "routes": routes_view.refresh,
        "traders": traders_view.refresh,
        "simulation": simulation_view.refresh,
        "transactions": transactions_view.refresh,
        "history": history_view.refresh,
        "reports": reports_view.refresh,
    })

    # Фоновый цикл часов: при запуске приложения возобновляет running-статус
    CLOCK.start()

    def _on_close() -> None:
        CLOCK.stop(timeout=5)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_close)

    show("dashboard")
    return root


def run_app():
    root = create_main_window()
    root.mainloop()


if __name__ == "__main__":
    run_app()
