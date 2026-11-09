"""Карта мира: NetworkX-граф поселений и маршрутов на Matplotlib."""
import networkx as nx
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import customtkinter as ctk

from app.economy.currency import format_copper
from app.services.inventory_service import InventoryService
from app.services.resource_service import ResourceService
from app.services.settlement_service import SettlementService
from app.services.trader_service import TraderService
from app.services.trade_route_service import TradeRouteService

TYPE_COLORS = {
    "village": "#8bc34a",
    "town": "#42a5f5",
    "city": "#ab47bc",
    "port": "#26c6da",
    "fortress": "#ef5350",
    "mining": "#ffa726",
    "trading_post": "#d4e157",
}
TYPE_LABELS = {
    "village": "Деревня", "town": "Городок", "city": "Город",
    "port": "Порт", "fortress": "Крепость",
    "mining": "Рудничный посёлок", "trading_post": "Торговый пост",
}


class WorldGraphView:
    """Карта мира: узлы — поселения, рёбра — маршруты, клик — детали."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self._settlements = SettlementService()
        self._routes = TradeRouteService()
        self._traders = TraderService()
        self._selected: int | None = None
        self._settlement_by_id: dict[int, object] = {}
        self._positions: dict[int, tuple[float, float]] = {}
        self._drag_id: int | None = None
        self._settlements_cache: list = []
        self._routes_cache: list = []
        self._traders_cache: list = []
        self._xlim = (-1.0, 1.0)
        self._ylim = (-1.0, 1.0)

        self.figure = Figure(figsize=(7.5, 5.2), dpi=100, facecolor="#1e1e1e")
        self.canvas = FigureCanvasTkAgg(self.figure, master=container)
        self.canvas.get_tk_widget().pack(side="left", fill="both",
                                         expand=True, padx=5, pady=5)

        side = ctk.CTkFrame(container, width=290)
        side.pack(side="right", fill="y", padx=5, pady=5)
        ctk.CTkLabel(side, text="Информация о поселении",
                     font=("Arial", 14, "bold")).pack(pady=8)
        self.info = ctk.CTkTextbox(side, width=280, height=480)
        self.info.pack(fill="both", expand=True, padx=8, pady=4)
        self.info.configure(state="disabled")

        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_release)
        self.refresh()

    # --- построение графа ----------------------------------------------
    def _build_positions(self, settlements, routes):
        graph = nx.Graph()
        for s in settlements:
            graph.add_node(s.id)
        for r in routes:
            graph.add_edge(r.from_settlement_id, r.to_settlement_id)
        if graph.number_of_edges():
            return nx.spring_layout(graph, seed=42, k=1.6)
        return {s.id: (float(i), 0.0) for i, s in enumerate(settlements)}

    def _ensure_positions(self, settlements, routes) -> None:
        """Сохранить позиции узлов; layout считать только для новых."""
        ids = {s.id for s in settlements}
        self._positions = {sid: p for sid, p in self._positions.items()
                           if sid in ids}
        if not settlements or ids <= self._positions.keys():
            return
        layout = self._build_positions(settlements, routes)
        for s in settlements:
            self._positions.setdefault(s.id, layout[s.id])

    def refresh(self) -> None:
        self._settlements_cache = self._settlements.get_settlements(
            self.campaign_id)
        self._routes_cache = self._routes.get_routes(self.campaign_id)
        self._traders_cache = self._traders.get_traders(self.campaign_id)
        self._settlement_by_id = {s.id: s for s in self._settlements_cache}
        self._ensure_positions(self._settlements_cache, self._routes_cache)
        if self._positions:
            xs = [p[0] for p in self._positions.values()]
            ys = [p[1] for p in self._positions.values()]
            self._xlim = (min(xs) - 0.25, max(xs) + 0.25)
            self._ylim = (min(ys) - 0.25, max(ys) + 0.25)
        self._draw()

    def _draw(self) -> None:
        settlements = self._settlements_cache
        routes = self._routes_cache
        pos = self._positions

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#1e1e1e")
        for spine in ax.spines.values():
            spine.set_color("#555555")

        if not settlements:
            ax.text(0.5, 0.5,
                    "Нет поселений — создайте их\nна вкладке «Поселения»",
                    ha="center", va="center", color="#aaaaaa", fontsize=13)
            ax.set_axis_off()
            self.canvas.draw()
            return

        ax.set_xlim(*self._xlim)
        ax.set_ylim(*self._ylim)

        # рёбра: включённые — сплошные зелёные, выключенные — серый пунктир
        for r in routes:
            color = "#66bb6a" if r.enabled else "#777777"
            style = "-" if r.enabled else "--"
            ax.annotate(
                "", xy=pos[r.to_settlement_id], xytext=pos[r.from_settlement_id],
                arrowprops=dict(arrowstyle="-", color=color, lw=1.6,
                                linestyle=style, shrinkA=16, shrinkB=16),
            )
            mid = ((pos[r.from_settlement_id][0] + pos[r.to_settlement_id][0]) / 2,
                   (pos[r.from_settlement_id][1] + pos[r.to_settlement_id][1]) / 2)
            ax.text(mid[0], mid[1], f"{r.travel_hours}ч", fontsize=7,
                    color=color, ha="center")

        # торговцы «на месте» под нодой
        traders_by_place: dict[int, list] = {}
        for t in self._traders_cache:
            if t.activity != "traveling" and t.current_settlement_id:
                traders_by_place.setdefault(t.current_settlement_id, []).append(t)

        for s in settlements:
            x, y = pos[s.id]
            size = 300 + min(s.population, 50000) / 50
            selected = s.id == self._selected
            ax.scatter([x], [y], s=size, c=TYPE_COLORS.get(s.type, "#9e9e9e"),
                       edgecolors="#ffffff" if selected else "#222222",
                       linewidths=2.5 if selected else 1.2, zorder=3)
            label = s.name
            count = len(traders_by_place.get(s.id, []))
            if count:
                label += f"\n♟ {count}"
            ax.text(x, y + 0.09, label, fontsize=8, color="#eeeeee",
                    ha="center", zorder=4)

        ax.set_title("Карта торговой сети (зелёные — активные маршруты)",
                     color="#dddddd", fontsize=11)
        ax.set_axis_off()
        self.canvas.draw()

    # --- взаимодействие ------------------------------------------------
    def _on_press(self, event) -> None:
        if event.inaxes is None or not self._positions:
            return
        best_id, best_dist = None, 0.0036
        for sid, (x, y) in self._positions.items():
            dist = (x - event.xdata) ** 2 + (y - event.ydata) ** 2
            if dist < best_dist:
                best_id, best_dist = sid, dist
        if best_id is None:
            return
        self._drag_id = best_id
        self._selected = best_id
        self._show_info(best_id)
        self._draw()

    def _on_motion(self, event) -> None:
        if self._drag_id is None or event.inaxes is None:
            return
        if event.xdata is None or event.ydata is None:
            return
        self._positions[self._drag_id] = (event.xdata, event.ydata)
        self._draw()

    def _on_release(self, event) -> None:
        self._drag_id = None

    def _show_info(self, settlement_id: int) -> None:
        s = self._settlement_by_id[settlement_id]
        res_names = {r.id: r.name
                     for r in ResourceService().get_resources(self.campaign_id)}

        lines = [
            f"«{s.name}»",
            f"Тип: {TYPE_LABELS.get(s.type, s.type)}",
            f"Население: {s.population}",
        ]
        if s.description:
            lines.append(f"\n{s.description}")

        lines.append("\n— Склад —")
        entries = InventoryService().get_inventory(s.id)
        if not entries:
            lines.append("пусто")
        for e in entries:
            lines.append(
                f"• {res_names.get(e.resource_id, '?')}: {e.quantity}, "
                f"цена {format_copper(e.price_copper)}"
            )

        traders = [t for t in self._traders.get_traders(self.campaign_id)
                   if t.activity != "traveling"
                   and t.current_settlement_id == s.id]
        lines.append("\n— Торговцы —")
        if traders:
            for t in traders:
                lines.append(f"• {t.name}: {format_copper(t.capital_copper)}")
        else:
            lines.append("нет")

        related = [r for r in self._routes.get_routes(self.campaign_id)
                   if s.id in (r.from_settlement_id, r.to_settlement_id)]
        lines.append("\n— Маршруты —")
        if related:
            for r in related:
                other = r.other_endpoint(s.id)
                other_name = self._settlement_by_id.get(other)
                status = "вкл" if r.enabled else "выкл"
                lines.append(
                    f"• ↔ {other_name.name if other_name else '?'}"
                    f" ({r.travel_hours}ч, {status})"
                )
        else:
            lines.append("нет")

        self.info.configure(state="normal")
        self.info.delete("1.0", "end")
        self.info.insert("1.0", "\n".join(lines))
        self.info.configure(state="disabled")
