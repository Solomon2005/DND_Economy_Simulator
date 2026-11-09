"""Вид «Отчёты»: сводка, экспорт CSV и экономические графики."""
import customtkinter as ctk

from app.core.exceptions import AppError
from app.services.report_service import ReportService
from app.ui.components import error_message, info_message
from app.visualization.economic_charts import EconomicChartsView


class ReportsView:
    """Сводные показатели экономики + графики + экспорт журнала."""

    def __init__(self, container, campaign_id: int):
        self.container = container
        self.campaign_id = campaign_id
        self.service = ReportService()
        self._build()

    def _build(self) -> None:
        top = ctk.CTkFrame(self.container, fg_color="transparent")
        top.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(top, text="Обновить сводку",
                      command=self.refresh).pack(side="left", padx=4)
        ctk.CTkButton(top, text="Экспорт журнала в CSV",
                      command=self._export).pack(side="left", padx=4)

        self.summary_box = ctk.CTkTextbox(self.container, height=150)
        self.summary_box.pack(fill="x", padx=5, pady=5)
        self.summary_box.configure(state="disabled")

        self.charts = EconomicChartsView(self.container, self.campaign_id)
        self.refresh()

    def refresh(self) -> None:
        data = self.service.summary(self.campaign_id)
        lines = [
            f"Записано сделок: {data['tx_count']}    "
            f"Событий в журнале: {data['event_count']}",
            "",
            "Топ ресурсов по объёму сделок (CP):",
        ]
        if data["top_resources"]:
            lines += [f"  {name}: {total}"
                      for name, total in data["top_resources"]]
        else:
            lines.append("  данных пока нет")
        lines.append("")
        lines.append("Балансы поселений (продажи − покупки, CP):")
        if data["balances"]:
            lines += [f"  {b['settlement']}: {b['balance']:+d}"
                      for b in data["balances"][:8]]
        else:
            lines.append("  данных пока нет")
        lines.append("")
        lines.append("Капиталы торговцев:")
        if data["traders"]:
            lines += [f"  {t['name']}: {t['capital']}"
                      for t in data["traders"][:8]]
        else:
            lines.append("  торговцев нет")

        self.summary_box.configure(state="normal")
        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("1.0", "\n".join(lines))
        self.summary_box.configure(state="disabled")
        self.charts.refresh()

    def _export(self) -> None:
        try:
            path = self.service.export_events_csv(self.campaign_id)
        except AppError as exc:
            error_message(self.container, str(exc))
            return
        info_message(self.container, f"Журнал выгружен:\n{path}")
