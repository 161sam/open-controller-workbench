from __future__ import annotations

from copy import deepcopy
from typing import Any

from ocw_workbench.gui.feedback import apply_status_message, friendly_ui_error
from ocw_workbench.gui.panels._common import (
    FallbackButton,
    FallbackCombo,
    FallbackLabel,
    FallbackText,
    configure_combo_box,
    load_qt,
    set_combo_items,
    set_text,
    set_tooltip,
)
from ocw_workbench.gui.runtime import component_icon_path
from ocw_workbench.services.controller_service import ControllerService
from ocw_workbench.services.interaction_service import InteractionService
from ocw_workbench.services.library_service import LibraryService


class ComponentPaletteModel:
    def __init__(self, components: list[dict[str, Any]] | None = None) -> None:
        self._components = [deepcopy(item) for item in (components or [])]

    def set_components(self, components: list[dict[str, Any]]) -> None:
        self._components = [deepcopy(item) for item in components]

    def categories(self) -> list[str]:
        categories = {str(item.get("ui", {}).get("category") or item.get("category") or "other") for item in self._components}
        return sorted(category for category in categories if category)

    def filter_components(
        self,
        *,
        search_text: str = "",
        category: str | None = None,
        favorites_only: bool = False,
        favorite_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
        normalized_search = search_text.strip().lower()
        favorites = favorite_ids or set()
        filtered: list[dict[str, Any]] = []
        for component in self._components:
            component_id = str(component["id"])
            ui = component.get("ui", {})
            ui_category = str(ui.get("category") or component.get("category") or "other")
            if category and category not in {"all", ui_category}:
                continue
            if favorites_only and component_id not in favorites:
                continue
            haystack = " ".join(
                [
                    component_id,
                    str(component.get("manufacturer") or ""),
                    str(component.get("part_number") or ""),
                    str(component.get("description") or ""),
                    str(ui.get("label") or ""),
                    " ".join(str(item) for item in ui.get("tags", [])),
                    " ".join(str(item) for item in component.get("tags", [])),
                ]
            ).lower()
            if normalized_search and normalized_search not in haystack:
                continue
            filtered.append(deepcopy(component))
        return filtered


class ComponentPalettePanel:
    def __init__(
        self,
        doc: Any,
        controller_service: ControllerService | None = None,
        library_service: LibraryService | None = None,
        interaction_service: InteractionService | None = None,
        on_status: Any | None = None,
    ) -> None:
        self.doc = doc
        self.controller_service = controller_service or ControllerService()
        self.library_service = library_service or LibraryService()
        self.interaction_service = interaction_service or InteractionService(self.controller_service)
        self.on_status = on_status
        self.model = ComponentPaletteModel()
        self._visible_components: list[dict[str, Any]] = []
        self._updating_selection = False
        self.form = _build_form()
        self.widget = self.form["widget"]
        self._configure_tooltips()
        self._connect_events()
        self.refresh()

    def refresh(self) -> None:
        self.model.set_components(self.library_service.list_by_category())
        set_combo_items(self.form["category"], ["all"] + self.model.categories())
        self._refresh_visible_components(preserve_selection=True)

    def _refresh_visible_components(self, preserve_selection: bool = False) -> None:
        settings = self.interaction_service.get_settings(self.doc)
        active_template_id = settings.get("active_component_template_id")
        favorite_ids = {str(item) for item in settings.get("favorite_component_template_ids", []) if item}
        category = self._current_category()
        search_text = self._search_text()
        favorites_only = self._favorites_only()
        self._visible_components = self.model.filter_components(
            search_text=search_text,
            category=None if category in {"", "all"} else category,
            favorites_only=favorites_only,
            favorite_ids=favorite_ids,
        )
        self._populate_grid(favorite_ids)
        if preserve_selection and active_template_id:
            self._select_component_item(active_template_id)
        elif self._visible_components:
            self._select_component_item(active_template_id or self._visible_components[0]["id"])
        self._update_details(active_template_id)
        self._update_favorite_button(active_template_id, favorite_ids)
        self._publish_status(
            f"{len(self._visible_components)} components shown. "
            f"Active template: {active_template_id or 'none'}."
        )

    def select_component_template(self, template_id: str) -> dict[str, Any]:
        settings = self.interaction_service.set_active_component_template(self.doc, template_id)
        favorite_ids = {str(item) for item in settings.get("favorite_component_template_ids", []) if item}
        self._select_component_item(template_id)
        self._update_details(template_id)
        self._update_favorite_button(template_id, favorite_ids)
        self._publish_status(f"Prepared '{template_id}' for Add/Place.")
        return settings

    def toggle_favorite_for_selection(self) -> dict[str, Any]:
        template_id = self.selected_component_template_id()
        if template_id is None:
            raise ValueError("No component template selected")
        settings = self.interaction_service.toggle_favorite_component_template(self.doc, template_id)
        favorite_ids = {str(item) for item in settings.get("favorite_component_template_ids", []) if item}
        if self._favorites_only():
            self._refresh_visible_components(preserve_selection=True)
        else:
            self._update_favorite_button(template_id, favorite_ids)
            self._populate_grid(favorite_ids)
            self._select_component_item(template_id)
        state = "added to" if template_id in favorite_ids else "removed from"
        self._publish_status(f"'{template_id}' {state} favorites.")
        return settings

    def selected_component_template_id(self) -> str | None:
        grid = self.form["grid"]
        item = None
        if hasattr(grid, "currentItem"):
            item = grid.currentItem()
        if item is not None and hasattr(item, "data"):
            qtcore, _qtgui, _qtwidgets = load_qt()
            role = getattr(getattr(qtcore, "Qt", None), "UserRole", 32)
            value = item.data(role)
            return str(value) if value else None
        return getattr(grid, "selected_template_id", None)

    def handle_search_changed(self, *_args: Any) -> None:
        self._refresh_visible_components(preserve_selection=True)

    def handle_category_changed(self, *_args: Any) -> None:
        self._refresh_visible_components(preserve_selection=True)

    def handle_favorites_filter_changed(self, *_args: Any) -> None:
        self._refresh_visible_components(preserve_selection=True)

    def handle_grid_selection_changed(self, *_args: Any) -> None:
        if self._updating_selection:
            return
        template_id = self.selected_component_template_id()
        if template_id is None:
            self._update_details(None)
            return
        try:
            self.select_component_template(template_id)
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not prepare component template", exc))

    def handle_favorite_clicked(self, *_args: Any) -> None:
        try:
            self.toggle_favorite_for_selection()
        except Exception as exc:
            self._publish_status(friendly_ui_error("Could not update favorites", exc))

    def _populate_grid(self, favorite_ids: set[str]) -> None:
        _qtcore, qtgui, qtwidgets = load_qt()
        grid = self.form["grid"]
        if qtwidgets is None or not hasattr(grid, "clear"):
            grid.items = [component["id"] for component in self._visible_components]
            return
        grid.clear()
        role = getattr(getattr(_qtcore, "Qt", None), "UserRole", 32)
        for component in self._visible_components:
            ui = component.get("ui", {})
            label = str(ui.get("label") or component["id"])
            template_id = str(component["id"])
            if template_id in favorite_ids:
                label = f"{label} *"
            item = qtwidgets.QListWidgetItem(label)
            if qtgui is not None and hasattr(qtgui, "QIcon"):
                item.setIcon(qtgui.QIcon(component_icon_path(ui.get("icon"))))
            item.setToolTip(
                "\n".join(
                    [
                        f"{template_id}",
                        str(component.get("description") or ""),
                        f"Category: {ui.get('category') or component.get('category')}",
                        f"Part: {component.get('manufacturer')} {component.get('part_number')}".strip(),
                    ]
                )
            )
            item.setData(role, template_id)
            grid.addItem(item)

    def _select_component_item(self, template_id: str | None) -> None:
        if template_id is None:
            return
        grid = self.form["grid"]
        if hasattr(grid, "count") and hasattr(grid, "item") and hasattr(grid, "setCurrentItem"):
            qtcore, _qtgui, _qtwidgets = load_qt()
            role = getattr(getattr(qtcore, "Qt", None), "UserRole", 32)
            self._updating_selection = True
            for index in range(grid.count()):
                item = grid.item(index)
                if str(item.data(role)) == template_id:
                    grid.setCurrentItem(item)
                    self._updating_selection = False
                    return
            self._updating_selection = False
            return
        grid.selected_template_id = template_id

    def _update_details(self, template_id: str | None) -> None:
        component = None
        if template_id:
            for item in self._visible_components:
                if item["id"] == template_id:
                    component = item
                    break
        if component is None and self._visible_components:
            component = self._visible_components[0]
        if component is None:
            set_text(self.form["details"], "No component matches the current filter.")
            return
        ui = component.get("ui", {})
        set_text(
            self.form["details"],
            "\n".join(
                [
                    f"Label: {ui.get('label') or component['id']}",
                    f"Template: {component['id']}",
                    f"Category: {ui.get('category') or component.get('category')}",
                    f"Part: {component.get('manufacturer')} {component.get('part_number')}".strip(),
                    f"Tags: {', '.join(ui.get('tags', [])) or '-'}",
                    f"Description: {component.get('description') or '-'}",
                ]
            ),
        )

    def _update_favorite_button(self, template_id: str | None, favorite_ids: set[str]) -> None:
        if template_id is None:
            self.form["favorite_button"].text = "Toggle Favorite"
            return
        self.form["favorite_button"].text = (
            "Remove Favorite" if template_id in favorite_ids else "Add Favorite"
        )

    def _search_text(self) -> str:
        widget = self.form["search"]
        if hasattr(widget, "text"):
            value = widget.text()
            return str(value) if value is not None else ""
        return str(getattr(widget, "text", ""))

    def _current_category(self) -> str:
        widget = self.form["category"]
        if hasattr(widget, "currentText"):
            return str(widget.currentText())
        return widget.items[widget.index] if getattr(widget, "items", None) else "all"

    def _favorites_only(self) -> bool:
        widget = self.form["favorites_only"]
        if hasattr(widget, "isChecked"):
            return bool(widget.isChecked())
        return bool(getattr(widget, "checked", False))

    def _publish_status(self, message: str) -> None:
        level = "error" if message.lower().startswith("could not") else "info"
        apply_status_message(self.form["status"], message, level=level)
        if self.on_status is not None:
            self.on_status(message)

    def _connect_events(self) -> None:
        if hasattr(self.form["search"], "textChanged"):
            self.form["search"].textChanged.connect(self.handle_search_changed)
        if hasattr(self.form["category"], "currentIndexChanged"):
            self.form["category"].currentIndexChanged.connect(self.handle_category_changed)
        if hasattr(self.form["favorites_only"], "toggled"):
            self.form["favorites_only"].toggled.connect(self.handle_favorites_filter_changed)
        if hasattr(self.form["grid"], "itemSelectionChanged"):
            self.form["grid"].itemSelectionChanged.connect(self.handle_grid_selection_changed)
        if hasattr(self.form["grid"], "itemClicked"):
            self.form["grid"].itemClicked.connect(self.handle_grid_selection_changed)
        if hasattr(self.form["favorite_button"], "clicked"):
            self.form["favorite_button"].clicked.connect(self.handle_favorite_clicked)

    def _configure_tooltips(self) -> None:
        set_tooltip(self.form["search"], "Filter the component library by name, id, part number, description or tags.")
        set_tooltip(self.form["category"], "Filter by palette category from the component UI metadata.")
        set_tooltip(self.form["favorites_only"], "Show only templates marked as favorites.")
        set_tooltip(self.form["grid"], "Select a component template to prepare it for Add/Place.")
        set_tooltip(self.form["favorite_button"], "Add or remove the selected component template from favorites.")


def _build_form() -> dict[str, Any]:
    qtcore, _qtgui, qtwidgets = load_qt()
    if qtwidgets is None:
        favorites_only = FallbackButton("Favorites Only")
        favorites_only.checked = False
        favorites_only.toggled = favorites_only.clicked
        return {
            "widget": object(),
            "search": FallbackText(),
            "category": FallbackCombo(["all"]),
            "favorites_only": favorites_only,
            "favorite_button": FallbackButton("Add Favorite"),
            "grid": type("FallbackGrid", (), {"items": [], "selected_template_id": None})(),
            "details": FallbackText(),
            "status": FallbackLabel(),
        }

    widget = qtwidgets.QWidget()
    root = qtwidgets.QVBoxLayout(widget)
    controls = qtwidgets.QHBoxLayout()
    search = qtwidgets.QLineEdit()
    search.setPlaceholderText("Search components")
    category = qtwidgets.QComboBox()
    configure_combo_box(category)
    favorites_only = qtwidgets.QCheckBox("Favorites only")
    favorite_button = qtwidgets.QPushButton("Add Favorite")
    controls.addWidget(search, 1)
    controls.addWidget(category)
    controls.addWidget(favorites_only)
    controls.addWidget(favorite_button)

    grid = qtwidgets.QListWidget()
    if hasattr(grid, "setViewMode") and hasattr(qtwidgets, "QListView"):
        grid.setViewMode(qtwidgets.QListView.IconMode)
    if hasattr(grid, "setResizeMode") and hasattr(qtwidgets, "QListView"):
        grid.setResizeMode(qtwidgets.QListView.Adjust)
    if hasattr(grid, "setMovement") and hasattr(qtwidgets, "QListView"):
        grid.setMovement(qtwidgets.QListView.Static)
    if hasattr(grid, "setSelectionMode") and hasattr(qtwidgets, "QAbstractItemView"):
        grid.setSelectionMode(qtwidgets.QAbstractItemView.SingleSelection)
    if hasattr(grid, "setIconSize"):
        size_cls = getattr(qtcore, "QSize", None)
        if callable(size_cls):
            grid.setIconSize(size_cls(56, 56))
    if hasattr(grid, "setSpacing"):
        grid.setSpacing(8)
    if hasattr(grid, "setUniformItemSizes"):
        grid.setUniformItemSizes(True)

    details = qtwidgets.QPlainTextEdit()
    details.setReadOnly(True)
    status = qtwidgets.QLabel("Component palette ready.")
    status.setWordWrap(True)

    root.addLayout(controls)
    root.addWidget(grid, 1)
    root.addWidget(details)
    root.addWidget(status)
    return {
        "widget": widget,
        "search": search,
        "category": category,
        "favorites_only": favorites_only,
        "favorite_button": favorite_button,
        "grid": grid,
        "details": details,
        "status": status,
    }
