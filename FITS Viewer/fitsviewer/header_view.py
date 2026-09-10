"""A searchable table view of a FITS header."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)


class HeaderView(QWidget):
    """Keyword / value / comment table, filterable like the list tabs in
    the other apps in this family."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter header keywords…")
        self.search_edit.textChanged.connect(self._apply_filter)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Keyword", "Value", "Comment"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        filter_row.addWidget(self.search_edit)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Header"))
        layout.addLayout(filter_row)
        layout.addWidget(self.table)

    def set_header(self, header) -> None:
        """Populate from a FITS header (astropy.io.fits.Header)."""
        rows = [
            (str(card.keyword), str(card.value), str(card.comment or ""))
            for card in header.cards
            if str(card.keyword).strip()
        ]
        self._set_rows(rows)

    def set_attributes(self, attributes: dict) -> None:
        """Populate from a plain {name: value} mapping - used for HDF5
        attributes, which have no FITS-style comment field."""
        rows = [(str(key), str(value), "") for key, value in attributes.items()]
        self._set_rows(rows)

    def clear(self) -> None:
        self.table.setRowCount(0)

    def _set_rows(self, rows: list[tuple[str, str, str]]) -> None:
        self.table.setRowCount(len(rows))
        for row, (keyword, value, comment) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(keyword))
            self.table.setItem(row, 1, QTableWidgetItem(value))
            self.table.setItem(row, 2, QTableWidgetItem(comment))
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self.search_edit.text().strip().lower()
        for row in range(self.table.rowCount()):
            if not text:
                self.table.setRowHidden(row, False)
                continue
            haystack = " ".join(
                self.table.item(row, col).text().lower()
                for col in range(self.table.columnCount())
                if self.table.item(row, col) is not None
            )
            self.table.setRowHidden(row, text not in haystack)
