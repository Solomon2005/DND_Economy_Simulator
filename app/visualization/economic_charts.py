"""Экономические графики: история цен и объём сделок (реальные данные)."""
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import customtkinter as ctk

from app.services.report_service import ReportService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.economy.currency import format_copper


class EconomicChartsView:
    """Два графика: цена ресурса по времени и объём сделок по суткам."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self._reports = ReportService()
        self._resources = ResourceService()
        self._settlements = SettlementService()
        self._build()

    def _build(self) -> None:
        controls = ctk.CTkFrame(self.container, fg_color="transparent")
        controls.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(controls, text="Ресурс:").pack(side="left", padx=5)
        self.resource_combo = ctk.CTkComboBox(
            controls, width=160, state="readonly", values=["—"])
        self.resource_combo.pack(side="left", padx=5)

        ctk.CTkLabel(controls, text="Поселение:").pack(side="left", padx=5)
        self.settlement_combo = ctk.CTkComboBox(
            controls, width=160, state="readonly", values=["все"])
        self.settlement_combo.pack(side="left", padx=5)

        ctk.CTkButton(controls, text="Обновить графики",
                      command=self.refresh).pack(side="left", padx=10)

        self.figure = Figure(figsize=(9, 5.4), dpi=100, facecolor="#1e1e1e")
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.container)
        self.canvas.get_tk_widget().pack(fill="both", expand=True,
                                         padx=5, pady=5)
        self._reload_combos()
        self.refresh()

    def _reload_combos(self) -> None:
        current_resource = self.resource_combo.get()
        resources = self._resources.get_resources(self.campaign_id)
        self._resource_by_name = {r.name: r.id for r in resources}
        resource_values = list(self._resource_by_name) or ["—"]
        self.resource_combo.configure(values=resource_values)
        self.resource_combo.set(
            current_resource if current_resource in self._resource_by_name
            else resource_values[0])

        current_settlement = self.settlement_combo.get()
        settlements = self._settlements.get_settlements(self.campaign_id)
        self._settlement_by_name = {s.name: s.id for s in settlements}
        values = ["все"] + list(self._settlement_by_name)
        self.settlement_combo.configure(values=values)
        self.settlement_combo.set(
            current_settlement if current_settlement in values else "все")

    def refresh(self) -> None:
        # новые ресурсы/поселения могли появиться — обновляем списки
        self._reload_combos()

        resource_id = self._resource_by_name.get(self.resource_combo.get())
        settlement_id = self._settlement_by_name.get(self.settlement_combo.get())

        series = (self._reports.price_series(self.campaign_id, resource_id,
                                             settlement_id)
                  if resource_id else [])
        volume = self._reports.trade_volume_by_day(self.campaign_id)

        self.figure.clear()

        # --- график 1: история цены -------------------------------------
        ax1 = self.figure.add_subplot(211)
        ax1.set_facecolor("#1e1e1e")
        if series:
            # серия по каждому поселению отдельно (когда «все»)
            by_place: dict[str, list] = {}
            for point in series:
                by_place.setdefault(point["settlement"], []).append(point)
            for place, points in by_place.items():
                ax1.plot([p["game_hour"] / 24 for p in points],
                         [p["price"] for p in points],
                         marker=".", linewidth=1.4, label=place)
            ax1.legend(fontsize=7, facecolor="#2b2b2b", labelcolor="#dddddd")
        else:
            ax1.text(0.5, 0.5, "Нет данных по истории цен\n"
                     "(цены появляются после тиков симуляции)",
                     ha="center", va="center", color="#aaaaaa",
                     transform=ax1.transAxes)
        resource_name = self.resource_combo.get()
        ax1.set_title(f"История цены: {resource_name}",
                      color="#dddddd", fontsize=10)
        ax1.set_xlabel("Игровые сутки", color="#cccccc", fontsize=8)
        ax1.set_ylabel("Цена, CP", color="#cccccc", fontsize=8)
        ax1.tick_params(colors="#cccccc", labelsize=7)
        ax1.grid(color="#3a3a3a", linewidth=0.5)

        # --- график 2: объём сделок -------------------------------------
        ax2 = self.figure.add_subplot(212)
        ax2.set_facecolor("#1e1e1e")
        if volume:
            days = [d for d, _ in volume]
            totals = [t for _, t in volume]
            ax2.bar([str(d) for d in days], totals, color="#66bb6a",
                    width=0.7)
        else:
            ax2.text(0.5, 0.5, "Сделок пока нет",
                     ha="center", va="center", color="#aaaaaa",
                     transform=ax2.transAxes)
        ax2.set_title("Объём сделок по игровым суткам (CP)",
                      color="#dddddd", fontsize=10)
        ax2.set_xlabel("Сутки", color="#cccccc", fontsize=8)
        ax2.set_ylabel("CP", color="#cccccc", fontsize=8)
        ax2.tick_params(colors="#cccccc", labelsize=7)
        ax2.grid(color="#3a3a3a", linewidth=0.5)

        for ax in (ax1, ax2):
            for spine in ax.spines.values():
                spine.set_color("#555555")

        self.figure.tight_layout()
        self.canvas.draw()
