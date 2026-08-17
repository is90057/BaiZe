from __future__ import annotations

import json
import os
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QPixmap, QColor, QPainter, QFont, QPen, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QMessageBox, QGroupBox, QComboBox, QInputDialog, QFileDialog,
)

from ..i18n import tr
from ..models.media import SubtitleClip

USER_TEMPLATES_FILE = os.path.expanduser("~/.gemini/antigravity-ide/user_templates.json")

BUILTIN_TEMPLATES = [
    # ---- 🎬 INTRO ANIMATION TEMPLATES ----
    {
        "id": "intro_vlog_opening",
        "category": "intro",
        "title": "Vlog Studio Opening",
        "desc": "Cool opening title banner for Vlog episodes",
        "text": "🎬 DAILY VLOG // EPISODE 01",
        "font_family": "PingFang TC",
        "font_size": 56,
        "font_color": "#FFE600",
        "bg_color": "#000000C0",
        "stroke_color": "#000000",
        "stroke_width": 2,
        "alignment": "center",
        "animation_effect": "fly",
        "animation_duration": 0.8,
        "preview_bg": "#1a1a24",
    },
    {
        "id": "intro_cyber_gaming",
        "category": "intro",
        "title": "Cyber Gaming Intro",
        "desc": "High-tech neon typewriter intro for gaming & tech",
        "text": "PRESS START ▶ LEVEL 01",
        "font_family": "Helvetica",
        "font_size": 50,
        "font_color": "#00F0FF",
        "bg_color": "#001025D0",
        "stroke_color": "#006699",
        "stroke_width": 3,
        "alignment": "center",
        "animation_effect": "typewriter",
        "animation_duration": 0.6,
        "preview_bg": "#0d1b2a",
    },
    {
        "id": "intro_cinematic_movie",
        "category": "intro",
        "title": "Cinematic Movie Opening",
        "desc": "Dramatic golden-white title for films & trailers",
        "text": "A FILM BY BAIZE",
        "font_family": "Georgia",
        "font_size": 64,
        "font_color": "#FFFFFF",
        "bg_color": "",
        "stroke_color": "#000000",
        "stroke_width": 4,
        "alignment": "center",
        "animation_effect": "fade",
        "animation_duration": 1.2,
        "preview_bg": "#0a0a0e",
    },
    {
        "id": "intro_tech_keynote",
        "category": "intro",
        "title": "Tech Keynote Intro",
        "desc": "Clean white card intro for announcements & tutorials",
        "text": "💡 NEW FEATURE ANNOUNCEMENT",
        "font_family": "Arial",
        "font_size": 44,
        "font_color": "#111111",
        "bg_color": "#FFFFFFF0",
        "stroke_color": "",
        "stroke_width": 0,
        "alignment": "center",
        "animation_effect": "typewriter",
        "animation_duration": 0.5,
        "preview_bg": "#2d2d3a",
    },

    # ---- 🔚 OUTRO ANIMATION TEMPLATES ----
    {
        "id": "outro_subscribe",
        "category": "outro",
        "title": "Like & Subscribe Outro",
        "desc": "Vibrant red banner for channel end credits",
        "text": "❤️ THANKS FOR WATCHING! LIKE & SUBSCRIBE",
        "font_family": "PingFang TC",
        "font_size": 40,
        "font_color": "#FFFFFF",
        "bg_color": "#E60049E0",
        "stroke_color": "#000000",
        "stroke_width": 2,
        "alignment": "bottom_center",
        "animation_effect": "fly",
        "animation_duration": 0.6,
        "preview_bg": "#2b1b24",
    },
    {
        "id": "outro_next_episode",
        "category": "outro",
        "title": "Next Episode Outro",
        "desc": "Neon blue end card for next episode previews",
        "text": "▶ NEXT EPISODE COMING SOON // FOLLOW US",
        "font_family": "Helvetica",
        "font_size": 38,
        "font_color": "#00F0FF",
        "bg_color": "#001530E0",
        "stroke_color": "#004477",
        "stroke_width": 2,
        "alignment": "bottom_center",
        "animation_effect": "typewriter",
        "animation_duration": 0.5,
        "preview_bg": "#0d1b2a",
    },
    {
        "id": "outro_end_credits",
        "category": "outro",
        "title": "End Credits Roll",
        "desc": "Classic movie rolling end credits template",
        "text": "DIRECTED & EDITED BY BAIZE",
        "font_family": "Georgia",
        "font_size": 42,
        "font_color": "#E0E0E0",
        "bg_color": "#000000B0",
        "stroke_color": "#000000",
        "stroke_width": 2,
        "alignment": "center",
        "animation_effect": "fade",
        "animation_duration": 1.0,
        "preview_bg": "#111115",
    },

    # ---- 📝 TITLE & SUBTITLE TEMPLATES ----
    {
        "id": "vlog_headline",
        "category": "title",
        "title": "Vlog Headline",
        "desc": "Bright yellow bold banner for Vlog video titles",
        "text": "VLOG TITLE HERE",
        "font_family": "PingFang TC",
        "font_size": 52,
        "font_color": "#FFE600",
        "bg_color": "#000000B0",
        "stroke_color": "#000000",
        "stroke_width": 2,
        "alignment": "center",
        "animation_effect": "fly",
        "animation_duration": 0.5,
        "preview_bg": "#1e1e24",
    },
    {
        "id": "tech_cyber",
        "category": "title",
        "title": "Tech Cyber Title",
        "desc": "Neon cyan typewriter title for tech & gaming",
        "text": "CYBERPUNK // TECH TITLE",
        "font_family": "Helvetica",
        "font_size": 44,
        "font_color": "#00F0FF",
        "bg_color": "#001020C0",
        "stroke_color": "#005588",
        "stroke_width": 2,
        "alignment": "top_center",
        "animation_effect": "typewriter",
        "animation_duration": 0.6,
        "preview_bg": "#0d1b2a",
    },
    {
        "id": "cinematic_heading",
        "category": "title",
        "title": "Cinematic Title",
        "desc": "Elegant white heading with smooth fade for films",
        "text": "CINEMATIC STORY",
        "font_family": "Georgia",
        "font_size": 60,
        "font_color": "#FFFFFF",
        "bg_color": "",
        "stroke_color": "#000000",
        "stroke_width": 3,
        "alignment": "center",
        "animation_effect": "fade",
        "animation_duration": 0.8,
        "preview_bg": "#111115",
    },
    {
        "id": "lower_third_red",
        "category": "title",
        "title": "News Lower Third",
        "desc": "Crimson red banner for news & interviews",
        "text": "BREAKING NEWS / SPECIAL REPORT",
        "font_family": "Arial",
        "font_size": 32,
        "font_color": "#FFFFFF",
        "bg_color": "#CC0000D0",
        "stroke_color": "",
        "stroke_width": 0,
        "alignment": "bottom_left",
        "animation_effect": "fly",
        "animation_duration": 0.4,
        "preview_bg": "#1e1e24",
    },
    {
        "id": "tutorial_card",
        "category": "title",
        "title": "Tutorial Note Card",
        "desc": "Clean white card for tutorials and knowledge tips",
        "text": "💡 KEY TAKEAWAY & STEP 1",
        "font_family": "PingFang TC",
        "font_size": 36,
        "font_color": "#222222",
        "bg_color": "#FFFFFFF0",
        "stroke_color": "",
        "stroke_width": 0,
        "alignment": "bottom_center",
        "animation_effect": "typewriter",
        "animation_duration": 0.5,
        "preview_bg": "#2b2b36",
    },
    {
        "id": "bold_highlight",
        "category": "title",
        "title": "Vibrant Highlight",
        "desc": "Hot pink bold text for intense highlight clips",
        "text": "MUST SEE MOMENT!",
        "font_family": "Impact",
        "font_size": 48,
        "font_color": "#FF3366",
        "bg_color": "#00000080",
        "stroke_color": "#FFFFFF",
        "stroke_width": 2,
        "alignment": "bottom_center",
        "animation_effect": "fly",
        "animation_duration": 0.4,
        "preview_bg": "#1e1e24",
    },
    {
        "id": "gold_luxury",
        "category": "title",
        "title": "Gold Luxury Heading",
        "desc": "Golden upscale title for awards & luxury clips",
        "text": "SPECIAL EDITION",
        "font_family": "Georgia",
        "font_size": 46,
        "font_color": "#FFD700",
        "bg_color": "#110e05C0",
        "stroke_color": "#443300",
        "stroke_width": 2,
        "alignment": "bottom_center",
        "animation_effect": "fade",
        "animation_duration": 0.6,
        "preview_bg": "#1a160d",
    },
    {
        "id": "podcast_quote",
        "category": "title",
        "title": "Podcast Quote",
        "desc": "Subtle grey card quote for podcasts & talk shows",
        "text": "“ This is an insightful quote from the host. ”",
        "font_family": "PingFang TC",
        "font_size": 34,
        "font_color": "#F0F0F0",
        "bg_color": "#202028C0",
        "stroke_color": "",
        "stroke_width": 0,
        "alignment": "bottom_center",
        "animation_effect": "fade",
        "animation_duration": 0.5,
        "preview_bg": "#16161c",
    },
]


def load_user_templates() -> list[dict]:
    """Load custom user templates from user_templates.json."""
    if not os.path.exists(USER_TEMPLATES_FILE):
        return []
    try:
        with open(USER_TEMPLATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_user_templates(templates: list[dict]) -> None:
    """Save custom user templates to user_templates.json."""
    try:
        os.makedirs(os.path.dirname(USER_TEMPLATES_FILE), exist_ok=True)
        with open(USER_TEMPLATES_FILE, "w", encoding="utf-8") as f:
            json.dump(templates, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _create_template_icon(tmpl: dict) -> QIcon:
    pm = QPixmap(180, 70)
    bg_hex = tmpl.get("preview_bg", "#1e1e24")
    pm.fill(QColor(bg_hex))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    text_color = QColor(tmpl.get("font_color", "#FFFFFF"))
    bg_color_str = tmpl.get("bg_color", "")
    if bg_color_str:
        box_c = QColor(bg_color_str)
        if box_c.isValid():
            p.fillRect(10, 18, 160, 34, box_c)

    font = QFont(tmpl.get("font_family", "Arial"), 10, QFont.Weight.Bold)
    p.setFont(font)
    fm = p.fontMetrics()
    sample_txt = tmpl.get("title", "Template")
    tw = fm.horizontalAdvance(sample_txt)
    tx = (180 - tw) // 2
    ty = 40

    stroke_w = tmpl.get("stroke_width", 0)
    stroke_c_str = tmpl.get("stroke_color", "")
    if stroke_w > 0 and stroke_c_str:
        st_c = QColor(stroke_c_str)
        if st_c.isValid():
            p.setPen(QPen(st_c, stroke_w))
            p.drawText(tx, ty, sample_txt)

    p.setPen(text_color)
    p.drawText(tx, ty, sample_txt)

    eff = tmpl.get("animation_effect", "none")
    cat = tmpl.get("category", "title")
    cat_tag = "🎬 INTRO" if cat == "intro" else ("🔚 OUTRO" if cat == "outro" else ("⭐ CUSTOM" if cat == "custom" else ""))
    
    if cat_tag:
        p.setFont(QFont("Helvetica", 7, QFont.Weight.Bold))
        p.setPen(QColor(240, 200, 100, 220))
        p.drawText(8, 14, cat_tag)

    eff_tag = "✈️ FLY" if eff == "fly" else ("✨ FADE" if eff == "fade" else ("⌨️ TYPE" if eff == "typewriter" else ""))
    if eff_tag:
        p.setFont(QFont("Helvetica", 7, QFont.Weight.Bold))
        p.setPen(QColor(220, 220, 230, 200))
        p.drawText(130, 14, eff_tag)

    p.end()
    return QIcon(pm)


class TemplatesPanel(QWidget):
    template_applied = pyqtSignal(dict)

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.user_templates = load_user_templates()
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        head = QHBoxLayout()
        self._title = QLabel(tr("Preset Title & Animation Templates"))
        self._title.setStyleSheet("font-weight: bold; color: #d0d0d6; font-size: 13px;")
        head.addWidget(self._title)
        head.addStretch(1)
        lay.addLayout(head)

        # Filter Category Combo
        filter_box = QHBoxLayout()
        self._cat_label = QLabel(tr("Category Filter:"))
        self._cat_label.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        filter_box.addWidget(self._cat_label)

        self.cat_combo = QComboBox(self)
        self.cat_combo.addItem(tr("All Templates"), "all")
        self.cat_combo.addItem(tr("🎬 Intro Animations"), "intro")
        self.cat_combo.addItem(tr("🔚 Outro Animations"), "outro")
        self.cat_combo.addItem(tr("📝 Title & Text"), "title")
        self.cat_combo.addItem(tr("⭐ Custom & Imported"), "custom")
        self.cat_combo.currentIndexChanged.connect(self._populate_list)
        filter_box.addWidget(self.cat_combo, 1)
        lay.addLayout(filter_box)

        self.list = QListWidget(self)
        self.list.setIconSize(QSize(170, 66))
        self.list.setSpacing(4)
        self.list.itemDoubleClicked.connect(self._on_item_double_clicked)
        lay.addWidget(self.list, 1)

        # Action Buttons Box
        btn_box = QGroupBox(tr("Template Actions"))
        btn_lay = QVBoxLayout(btn_box)
        btn_lay.setContentsMargins(6, 6, 6, 6)
        btn_lay.setSpacing(4)

        self.add_btn = QPushButton(tr("+ Add Template to Timeline"))
        self.add_btn.setStyleSheet("background: #2a6e9a; color: white; font-weight: bold; padding: 6px;")
        self.add_btn.clicked.connect(self.add_selected_template)
        btn_lay.addWidget(self.add_btn)

        self.apply_style_btn = QPushButton(tr("Apply Style to Selected Subtitle"))
        self.apply_style_btn.setStyleSheet("background: #444450; color: #d0d0d6; font-weight: bold; padding: 5px;")
        self.apply_style_btn.clicked.connect(self.apply_style_to_selected)
        btn_lay.addWidget(self.apply_style_btn)

        # Custom & Import/Export Buttons
        custom_row = QHBoxLayout()
        self.save_custom_btn = QPushButton(tr("💾 Save Selected as Template"))
        self.save_custom_btn.setStyleSheet("background: #3a5a7b; color: white; font-size: 11px; padding: 4px;")
        self.save_custom_btn.clicked.connect(self.save_selected_as_custom)
        custom_row.addWidget(self.save_custom_btn)

        self.import_btn = QPushButton(tr("📥 Import JSON"))
        self.import_btn.setStyleSheet("background: #2b7b5a; color: white; font-size: 11px; padding: 4px;")
        self.import_btn.clicked.connect(self.import_template_json)
        custom_row.addWidget(self.import_btn)

        self.export_btn = QPushButton(tr("📤 Export JSON"))
        self.export_btn.setStyleSheet("background: #5a3a7b; color: white; font-size: 11px; padding: 4px;")
        self.export_btn.clicked.connect(self.export_user_templates)
        custom_row.addWidget(self.export_btn)

        btn_lay.addLayout(custom_row)
        lay.addWidget(btn_box)

        self._populate_list()

    def _all_templates( me ) -> list[dict]:
        return BUILTIN_TEMPLATES + me.user_templates

    def _populate_list(self):
        self.list.clear()
        selected_cat = self.cat_combo.currentData() or "all"

        for tmpl in self._all_templates():
            cat = tmpl.get("category", "title")
            if selected_cat != "all" and cat != selected_cat:
                continue

            item = QListWidgetItem()
            display_title = tr(tmpl["title"])
            item.setText(display_title)
            item.setData(Qt.ItemDataRole.UserRole, tmpl)
            item.setToolTip(f"{display_title}\n{tr(tmpl.get('desc', ''))}\nText: \"{tmpl.get('text', '')}\"")
            item.setIcon(_create_template_icon(tmpl))
            self.list.addItem(item)

        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def retranslate(self):
        self._title.setText(tr("Preset Title & Animation Templates"))
        self._cat_label.setText(tr("Category Filter:"))
        self.cat_combo.setItemText(0, tr("All Templates"))
        self.cat_combo.setItemText(1, tr("🎬 Intro Animations"))
        self.cat_combo.setItemText(2, tr("🔚 Outro Animations"))
        self.cat_combo.setItemText(3, tr("📝 Title & Text"))
        self.cat_combo.setItemText(4, tr("⭐ Custom & Imported"))
        self.add_btn.setText(tr("+ Add Template to Timeline"))
        self.apply_style_btn.setText(tr("Apply Style to Selected Subtitle"))
        self.save_custom_btn.setText(tr("💾 Save Selected as Template"))
        self.import_btn.setText(tr("📥 Import JSON"))
        self.export_btn.setText(tr("📤 Export JSON"))
        self._populate_list()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self.add_selected_template()

    def add_selected_template(self):
        item = self.list.currentItem()
        if item is None:
            return
        tmpl = item.data(Qt.ItemDataRole.UserRole)
        if not tmpl:
            return

        default_text = tmpl.get("text", "TITLE HERE")
        text, ok = QInputDialog.getMultiLineText(
            self,
            tr("Edit Template Text"),
            tr("Enter custom text content for this template:"),
            default_text
        )
        if not ok or not text.strip():
            return
        custom_text = text.strip()

        main_win = self.window()
        timeline = getattr(main_win, "timeline", None)
        playhead_time = timeline.playhead if timeline else 0.0

        cat = tmpl.get("category", "title")
        pos = playhead_time
        if cat == "intro":
            pos = 0.0
        elif cat == "outro":
            proj_dur = self.controller.project.duration()
            pos = max(0.0, proj_dur - 4.5)

        sub = SubtitleClip(
            text=custom_text,
            position=pos,
            duration=float(tmpl.get("duration", 4.0 if cat in ("intro", "outro") else 3.5)),
            font_family=tmpl.get("font_family", "Arial"),
            font_size=int(tmpl.get("font_size", 48)),
            font_color=tmpl.get("font_color", "#FFFFFF"),
            bg_color=tmpl.get("bg_color", ""),
            stroke_color=tmpl.get("stroke_color", ""),
            stroke_width=int(tmpl.get("stroke_width", 0)),
            alignment=tmpl.get("alignment", "center"),
            animation_effect=tmpl.get("animation_effect", "none"),
            animation_duration=float(tmpl.get("animation_duration", 0.5)),
        )
        self.controller.undo_stack.push(self._add_sub_cmd(sub))
        self.controller.timeline_changed.emit()

        inspector = getattr(main_win, "inspector", None)
        if inspector:
            inspector.select_subtitle(sub.id)

    def apply_style_to_selected(self):
        item = self.list.currentItem()
        if item is None:
            return
        tmpl = item.data(Qt.ItemDataRole.UserRole)
        if not tmpl:
            return

        main_win = self.window()
        inspector = getattr(main_win, "inspector", None)
        sub_id = getattr(inspector, "_sub_id", None) if inspector else None

        if not sub_id:
            QMessageBox.information(
                self, tr("Preset Title Templates"),
                tr("Please select a subtitle on the timeline first."))
            return

        self.controller.update_subtitle(
            sub_id,
            font_family=tmpl.get("font_family", "Arial"),
            font_size=int(tmpl.get("font_size", 48)),
            font_color=tmpl.get("font_color", "#FFFFFF"),
            bg_color=tmpl.get("bg_color", ""),
            stroke_color=tmpl.get("stroke_color", ""),
            stroke_width=int(tmpl.get("stroke_width", 0)),
            alignment=tmpl.get("alignment", "center"),
            animation_effect=tmpl.get("animation_effect", "none"),
            animation_duration=float(tmpl.get("animation_duration", 0.5)),
        )
        if inspector:
            inspector.reload_subtitle()

    def save_selected_as_custom(self):
        main_win = self.window()
        inspector = getattr(main_win, "inspector", None)
        sub_id = getattr(inspector, "_sub_id", None) if inspector else None

        if not sub_id:
            QMessageBox.information(
                self, tr("Save Custom Template"),
                tr("Please select a subtitle on the timeline to save as template."))
            return

        sub = self.controller.project.subtitle_by_id(sub_id)
        if sub is None:
            return

        name, ok = QInputDialog.getText(
            self, tr("Save Custom Template"),
            tr("Enter custom template name:"),
            text=f"Custom {sub.text[:12]}"
        )
        if not ok or not name.strip():
            return

        custom_tmpl = {
            "id": f"custom_{int(os.path.getmtime(USER_TEMPLATES_FILE)) if os.path.exists(USER_TEMPLATES_FILE) else 1}_{len(self.user_templates)}",
            "category": "custom",
            "title": name.strip(),
            "desc": "User custom saved template",
            "text": sub.text,
            "font_family": sub.font_family,
            "font_size": sub.font_size,
            "font_color": sub.font_color,
            "bg_color": sub.bg_color,
            "stroke_color": sub.stroke_color,
            "stroke_width": sub.stroke_width,
            "alignment": sub.alignment,
            "animation_effect": getattr(sub, "animation_effect", "none"),
            "animation_duration": getattr(sub, "animation_duration", 0.5),
            "preview_bg": "#1e1e24",
        }
        self.user_templates.append(custom_tmpl)
        save_user_templates(self.user_templates)
        self.cat_combo.setCurrentIndex(4)  # Switch to Custom category
        self._populate_list()
        QMessageBox.information(
            self, tr("Save Custom Template"),
            tr("Custom template saved successfully!"))

    def import_template_json(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Import Template JSON"), "", "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            added_count = 0
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and "title" in item:
                    item["category"] = "custom"
                    item["id"] = f"custom_imp_{len(self.user_templates)}_{added_count}"
                    self.user_templates.append(item)
                    added_count += 1

            if added_count > 0:
                save_user_templates(self.user_templates)
                self.cat_combo.setCurrentIndex(4)
                self._populate_list()
                QMessageBox.information(
                    self, tr("Import Template JSON"),
                    f"{tr('Successfully imported')} {added_count} {tr('templates!')}")
            else:
                QMessageBox.warning(
                    self, tr("Import Template JSON"),
                    tr("No valid template objects found in JSON file."))
        except Exception as e:
            QMessageBox.critical(
                self, tr("Import Template JSON"),
                f"{tr('Failed to import JSON file')}:\n{e}")

    def export_user_templates(self):
        if not self.user_templates:
            QMessageBox.information(
                self, tr("Export Templates"),
                tr("No custom templates to export."))
            return

        path, _ = QFileDialog.getSaveFileName(
            self, tr("Export Templates"), "my_baize_templates.json", "JSON Files (*.json)"
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.user_templates, f, ensure_ascii=False, indent=2)
            QMessageBox.information(
                self, tr("Export Templates"),
                f"{tr('Successfully exported')} {len(self.user_templates)} {tr('templates!')}")
        except Exception as e:
            QMessageBox.critical(
                self, tr("Export Templates"),
                f"{tr('Failed to export templates')}:\n{e}")

    def _add_sub_cmd(self, sub: SubtitleClip):
        from ..controllers.project_controller import _AddSubtitle
        return _AddSubtitle(self.controller.project, sub)
