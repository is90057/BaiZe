from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLabel, QLineEdit, QSlider,
    QDoubleSpinBox, QGroupBox, QComboBox, QScrollArea, QPushButton,
    QSpinBox, QCheckBox, QHBoxLayout,
)

from ..i18n import tr

TRANSITION_TYPES = [
    ("fade", "Fade / Crossfade"),
    ("black", "Fade to Black"),
    ("white", "Fade to White"),
    ("wipe_right", "Wipe Right"),
    ("wipe_left", "Wipe Left"),
    ("wipe_up", "Wipe Up"),
    ("wipe_down", "Wipe Down"),
    ("slide_right", "Slide Right"),
    ("slide_left", "Slide Left"),
    ("slide_up", "Slide Up"),
    ("slide_down", "Slide Down"),
    ("zoom_in", "Zoom In"),
    ("circle_crop", "Circle Crop"),
]


class InspectorPanel(QWidget):
    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._clip_id: str | None = None
        self._loading = False
        self._setup_ui()
        self.controller.selection_changed.connect(self.on_selection_changed)
        self.controller.timeline_changed.connect(self.refresh_after_edit)

    def _setup_ui(self):
        main_lay = QVBoxLayout(self)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        scroll_content = QWidget()
        lay = QVBoxLayout(scroll_content)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        self._title = QLabel(tr("Inspector"))
        self._title.setObjectName("panelTitle")
        lay.addWidget(self._title)

        self.placeholder = QLabel(
            tr("Select a clip on the timeline to edit.\n\n"
               "Video: trim, position, opacity, transitions.\n"
               "Audio: trim, position, volume."))
        self.placeholder.setWordWrap(True)
        self.placeholder.setObjectName("dimText")
        lay.addWidget(self.placeholder)

        self.group = QGroupBox(tr("Clip"))
        self._form = QFormLayout(self.group)
        self._form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.name_edit = QLineEdit()
        self.name_edit.returnPressed.connect(self.commit_name)
        self._label_name = QLabel(tr("Name"))
        self._form.addRow(self._label_name, self.name_edit)

        self.type_label = QLabel("-")
        self._label_type = QLabel(tr("Type"))
        self._form.addRow(self._label_type, self.type_label)

        self.position_spin = QDoubleSpinBox()
        self.position_spin.setDecimals(3)
        self.position_spin.setRange(0.0, 86399.0)
        self.position_spin.valueChanged.connect(self.commit_position)
        self._label_pos = QLabel(tr("Start (s)"))
        self._form.addRow(self._label_pos, self.position_spin)

        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setDecimals(3)
        self.duration_spin.setRange(0.001, 86399.0)
        self.duration_spin.valueChanged.connect(self.commit_duration)
        self._label_dur = QLabel(tr("Duration (s)"))
        self._form.addRow(self._label_dur, self.duration_spin)

        self.trim_spin = QDoubleSpinBox()
        self.trim_spin.setDecimals(3)
        self.trim_spin.setRange(0.0, 86399.0)
        self.trim_spin.valueChanged.connect(self.commit_trim)
        self._label_trim = QLabel(tr("Trim In (s)"))
        self._form.addRow(self._label_trim, self.trim_spin)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.valueChanged.connect(self.commit_volume)
        self._label_vol = QLabel(tr("Volume"))
        self._form.addRow(self._label_vol, self.vol_slider)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.valueChanged.connect(self.commit_opacity)
        self._label_opacity = QLabel(tr("Opacity"))
        self._form.addRow(self._label_opacity, self.opacity_slider)

        from .effects_panel import PRESET_EFFECTS
        self.video_fx_combo = QComboBox()
        for fx_code, fx_en, fx_zh, _ in PRESET_EFFECTS:
            self.video_fx_combo.addItem(tr(fx_en), fx_code)
        self.video_fx_combo.currentIndexChanged.connect(self.commit_video_fx)
        self._label_video_fx = QLabel(tr("Video Effect"))
        self._form.addRow(self._label_video_fx, self.video_fx_combo)

        self.group.setLayout(self._form)
        self.group.setVisible(False)
        lay.addWidget(self.group)

        # Transitions Group
        self.trans_group = QGroupBox(tr("Transitions"))
        self._trans_form = QFormLayout(self.trans_group)
        self._trans_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.in_type_combo = QComboBox()
        for t_code, t_name in TRANSITION_TYPES:
            self.in_type_combo.addItem(tr(t_name), t_code)
        self.in_type_combo.currentIndexChanged.connect(self.commit_transitions)
        self._label_in_type = QLabel(tr("Fade In (Entry)"))
        self._trans_form.addRow(self._label_in_type, self.in_type_combo)

        self.in_dur_spin = QDoubleSpinBox()
        self.in_dur_spin.setDecimals(2)
        self.in_dur_spin.setRange(0.0, 10.0)
        self.in_dur_spin.setSingleStep(0.1)
        self.in_dur_spin.valueChanged.connect(self.commit_transitions)
        self._label_in_dur = QLabel(tr("Duration (s)"))
        self._trans_form.addRow(self._label_in_dur, self.in_dur_spin)

        self.out_type_combo = QComboBox()
        for t_code, t_name in TRANSITION_TYPES:
            self.out_type_combo.addItem(tr(t_name), t_code)
        self.out_type_combo.currentIndexChanged.connect(self.commit_transitions)
        self._label_out_type = QLabel(tr("Fade Out (Exit)"))
        self._trans_form.addRow(self._label_out_type, self.out_type_combo)

        self.out_dur_spin = QDoubleSpinBox()
        self.out_dur_spin.setDecimals(2)
        self.out_dur_spin.setRange(0.0, 10.0)
        self.out_dur_spin.setSingleStep(0.1)
        self.out_dur_spin.valueChanged.connect(self.commit_transitions)
        self._label_out_dur = QLabel(tr("Duration (s)"))
        self._trans_form.addRow(self._label_out_dur, self.out_dur_spin)

        self.trans_group.setLayout(self._trans_form)
        self.trans_group.setVisible(False)
        lay.addWidget(self.trans_group)

        # Subtitle Properties Group
        self.sub_group = QGroupBox(tr("Subtitle Editor"))
        self._sub_form = QFormLayout(self.sub_group)
        self._sub_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        from PyQt6.QtWidgets import QPlainTextEdit, QSpinBox, QPushButton, QColorDialog
        self.sub_text_edit = QPlainTextEdit()
        self.sub_text_edit.setMaximumHeight(65)
        self.sub_text_edit.textChanged.connect(self.commit_subtitle)
        self._label_sub_text = QLabel(tr("Subtitle Text"))
        self._sub_form.addRow(self._label_sub_text, self.sub_text_edit)

        self.sub_pos_spin = QDoubleSpinBox()
        self.sub_pos_spin.setDecimals(2)
        self.sub_pos_spin.setRange(0.0, 86399.0)
        self.sub_pos_spin.valueChanged.connect(self.commit_subtitle)
        self._label_sub_pos = QLabel(tr("Start (s)"))
        self._sub_form.addRow(self._label_sub_pos, self.sub_pos_spin)

        self.sub_dur_spin = QDoubleSpinBox()
        self.sub_dur_spin.setDecimals(2)
        self.sub_dur_spin.setRange(0.1, 86399.0)
        self.sub_dur_spin.setSingleStep(0.5)
        self.sub_dur_spin.valueChanged.connect(self.commit_subtitle)
        self._label_sub_dur = QLabel(tr("Duration (s)"))
        self._sub_form.addRow(self._label_sub_dur, self.sub_dur_spin)

        self.sub_font_combo = QComboBox()
        for f_family in ["Arial", "Helvetica", "PingFang TC", "Heiti TC", "Microsoft JhengHei", "Courier New"]:
            self.sub_font_combo.addItem(f_family, f_family)
        self.sub_font_combo.currentIndexChanged.connect(self.commit_subtitle)
        self._label_sub_font = QLabel(tr("Font Family"))
        self._sub_form.addRow(self._label_sub_font, self.sub_font_combo)

        self.sub_size_spin = QSpinBox()
        self.sub_size_spin.setRange(12, 120)
        self.sub_size_spin.setSingleStep(2)
        self.sub_size_spin.setValue(36)
        self.sub_size_spin.valueChanged.connect(self.commit_subtitle)
        self._label_sub_size = QLabel(tr("Font Size"))
        self._sub_form.addRow(self._label_sub_size, self.sub_size_spin)

        self.sub_color_btn = QPushButton("#FFFFFF")
        self.sub_color_btn.clicked.connect(self._pick_sub_color)
        self._label_sub_color = QLabel(tr("Font Color"))
        self._sub_form.addRow(self._label_sub_color, self.sub_color_btn)

        self.sub_bg_btn = QPushButton("#00000080")
        self.sub_bg_btn.clicked.connect(self._pick_sub_bg)
        self._label_sub_bg = QLabel(tr("Background"))
        self._sub_form.addRow(self._label_sub_bg, self.sub_bg_btn)

        self.sub_stroke_spin = QSpinBox()
        self.sub_stroke_spin.setRange(0, 10)
        self.sub_stroke_spin.valueChanged.connect(self.commit_subtitle)
        self._label_sub_stroke = QLabel(tr("Outline Width"))
        self._sub_form.addRow(self._label_sub_stroke, self.sub_stroke_spin)

        self.sub_align_combo = QComboBox()
        self.sub_align_combo.addItem(tr("Bottom Center"), "bottom_center")
        self.sub_align_combo.addItem(tr("Top Center"), "top_center")
        self.sub_align_combo.addItem(tr("Center"), "center")
        self.sub_align_combo.addItem(tr("Bottom Left"), "bottom_left")
        self.sub_align_combo.addItem(tr("Bottom Right"), "bottom_right")
        self.sub_align_combo.currentIndexChanged.connect(self.commit_subtitle)
        self._label_sub_align = QLabel(tr("Alignment"))
        self._sub_form.addRow(self._label_sub_align, self.sub_align_combo)

        self.sub_anim_effect_combo = QComboBox()
        self.sub_anim_effect_combo.addItem(tr("None"), "none")
        self.sub_anim_effect_combo.addItem(tr("Fly-In / Fly-Out"), "fly")
        self.sub_anim_effect_combo.addItem(tr("Fade In / Fade Out"), "fade")
        self.sub_anim_effect_combo.addItem(tr("Typewriter"), "typewriter")
        self.sub_anim_effect_combo.currentIndexChanged.connect(self.commit_subtitle)
        self._label_sub_anim_effect = QLabel(tr("Animation Effect"))
        self._sub_form.addRow(self._label_sub_anim_effect, self.sub_anim_effect_combo)

        self.sub_anim_dur_spin = QDoubleSpinBox()
        self.sub_anim_dur_spin.setDecimals(2)
        self.sub_anim_dur_spin.setRange(0.1, 5.0)
        self.sub_anim_dur_spin.setSingleStep(0.1)
        self.sub_anim_dur_spin.setValue(0.5)
        self.sub_anim_dur_spin.valueChanged.connect(self.commit_subtitle)
        self._label_sub_anim_dur = QLabel(tr("Effect Duration (s)"))
        self._sub_form.addRow(self._label_sub_anim_dur, self.sub_anim_dur_spin)

        self.sub_group.setLayout(self._sub_form)
        self.sub_group.setVisible(False)
        lay.addWidget(self.sub_group)

        # Chroma Key Group
        from PyQt6.QtWidgets import QCheckBox, QHBoxLayout
        self.ck_group = QGroupBox(tr("Chroma Key (Green Screen)"))
        self._ck_form = QFormLayout(self.ck_group)

        self.ck_enable_chk = QCheckBox(tr("Enable Chroma Key"))
        self.ck_enable_chk.toggled.connect(self.commit_chroma_key)
        self._ck_form.addRow(self.ck_enable_chk)

        ck_btn_lay = QHBoxLayout()
        self.ck_color_btn = QPushButton("#00FF00")
        self.ck_color_btn.clicked.connect(self._pick_ck_color)
        ck_btn_lay.addWidget(self.ck_color_btn)

        self.ck_green_btn = QPushButton(tr("Green"))
        self.ck_green_btn.clicked.connect(lambda: self._set_ck_preset("#00FF00"))
        ck_btn_lay.addWidget(self.ck_green_btn)

        self.ck_blue_btn = QPushButton(tr("Blue"))
        self.ck_blue_btn.clicked.connect(lambda: self._set_ck_preset("#0000FF"))
        ck_btn_lay.addWidget(self.ck_blue_btn)

        self._label_ck_color = QLabel(tr("Key Color"))
        self._ck_form.addRow(self._label_ck_color, ck_btn_lay)

        self.ck_sim_spin = QDoubleSpinBox()
        self.ck_sim_spin.setDecimals(2)
        self.ck_sim_spin.setRange(0.01, 1.0)
        self.ck_sim_spin.setSingleStep(0.05)
        self.ck_sim_spin.setValue(0.30)
        self.ck_sim_spin.valueChanged.connect(self.commit_chroma_key)
        self._label_ck_sim = QLabel(tr("Similarity"))
        self._ck_form.addRow(self._label_ck_sim, self.ck_sim_spin)

        self.ck_smooth_spin = QDoubleSpinBox()
        self.ck_smooth_spin.setDecimals(2)
        self.ck_smooth_spin.setRange(0.00, 1.0)
        self.ck_smooth_spin.setSingleStep(0.02)
        self.ck_smooth_spin.setValue(0.10)
        self.ck_smooth_spin.valueChanged.connect(self.commit_chroma_key)
        self._label_ck_smooth = QLabel(tr("Smoothness"))
        self._ck_form.addRow(self._label_ck_smooth, self.ck_smooth_spin)

        self.ck_group.setLayout(self._ck_form)
        self.ck_group.setVisible(False)
        lay.addWidget(self.ck_group)

        # Playback Speed Group
        self.speed_group = QGroupBox(tr("Playback Speed (Slow/Fast Motion)"))
        self._speed_form = QFormLayout(self.speed_group)
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setDecimals(2)
        self.speed_spin.setRange(0.1, 10.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(1.0)
        self.speed_spin.valueChanged.connect(self.commit_speed)
        self._label_speed = QLabel(tr("Speed Multiplier"))
        self._speed_form.addRow(self._label_speed, self.speed_spin)

        speed_btn_lay = QHBoxLayout()
        for sp_val, sp_lbl in [(0.25, "0.25x"), (0.5, "0.5x"), (1.0, "1.0x"), (2.0, "2.0x"), (4.0, "4.0x")]:
            btn = QPushButton(sp_lbl)
            btn.clicked.connect(lambda _, v=sp_val: self._set_speed_preset(v))
            speed_btn_lay.addWidget(btn)
        self._speed_form.addRow(speed_btn_lay)
        self.speed_group.setLayout(self._speed_form)
        self.speed_group.setVisible(False)
        lay.addWidget(self.speed_group)

        # Color Correction Group
        self.cc_group = QGroupBox(tr("Color Correction & Grading"))
        self._cc_form = QFormLayout(self.cc_group)

        self.brightness_spin = QDoubleSpinBox()
        self.brightness_spin.setDecimals(2)
        self.brightness_spin.setRange(-1.0, 1.0)
        self.brightness_spin.setSingleStep(0.05)
        self.brightness_spin.setValue(0.0)
        self.brightness_spin.valueChanged.connect(self.commit_color_correction)
        self._label_bright = QLabel(tr("Brightness"))
        self._cc_form.addRow(self._label_bright, self.brightness_spin)

        self.contrast_spin = QDoubleSpinBox()
        self.contrast_spin.setDecimals(2)
        self.contrast_spin.setRange(0.1, 3.0)
        self.contrast_spin.setSingleStep(0.05)
        self.contrast_spin.setValue(1.0)
        self.contrast_spin.valueChanged.connect(self.commit_color_correction)
        self._label_contrast = QLabel(tr("Contrast"))
        self._cc_form.addRow(self._label_contrast, self.contrast_spin)

        self.saturation_spin = QDoubleSpinBox()
        self.saturation_spin.setDecimals(2)
        self.saturation_spin.setRange(0.0, 3.0)
        self.saturation_spin.setSingleStep(0.05)
        self.saturation_spin.setValue(1.0)
        self.saturation_spin.valueChanged.connect(self.commit_color_correction)
        self._label_sat = QLabel(tr("Saturation"))
        self._cc_form.addRow(self._label_sat, self.saturation_spin)

        self.cc_group.setLayout(self._cc_form)
        self.cc_group.setVisible(False)
        lay.addWidget(self.cc_group)

        # Blur & Focus Group
        self.bf_group = QGroupBox(tr("Blur & Focus Effects"))
        self._bf_form = QFormLayout(self.bf_group)

        self.focus_mode_combo = QComboBox()
        self.focus_mode_combo.addItem(tr("None"), "none")
        self.focus_mode_combo.addItem(tr("Gaussian Blur"), "gaussian_blur")
        self.focus_mode_combo.addItem(tr("Center Focus"), "center_focus")
        self.focus_mode_combo.addItem(tr("Tilt Shift Focus"), "tilt_shift")
        self.focus_mode_combo.currentIndexChanged.connect(self.commit_blur_focus)
        self._label_focus_mode = QLabel(tr("Focus Mode"))
        self._bf_form.addRow(self._label_focus_mode, self.focus_mode_combo)

        self.blur_amount_spin = QDoubleSpinBox()
        self.blur_amount_spin.setDecimals(1)
        self.blur_amount_spin.setRange(0.0, 20.0)
        self.blur_amount_spin.setSingleStep(0.5)
        self.blur_amount_spin.setValue(0.0)
        self.blur_amount_spin.valueChanged.connect(self.commit_blur_focus)
        self._label_blur_amt = QLabel(tr("Blur Intensity"))
        self._bf_form.addRow(self._label_blur_amt, self.blur_amount_spin)

        self.bf_group.setLayout(self._bf_form)
        self.bf_group.setVisible(False)
        lay.addWidget(self.bf_group)

        # Object Removal (Content-Aware Fill Eraser)
        self.obj_removal_group = QGroupBox(tr("Object Removal & Content-Aware Fill"))
        self._obj_form = QFormLayout(self.obj_removal_group)

        self.obj_enable_chk = QCheckBox(tr("Enable Object Removal"))
        self.obj_enable_chk.toggled.connect(self.commit_object_removal)
        self._obj_form.addRow(self.obj_enable_chk)

        brush_box = QHBoxLayout()
        self.obj_brush_btn = QPushButton(tr("🪄 Activate Magic Eraser"))
        self.obj_brush_btn.setStyleSheet("background: #8b2b3e; color: white; font-weight: bold;")
        self.obj_brush_btn.setCheckable(True)
        self.obj_brush_btn.toggled.connect(self.toggle_magic_eraser_tool)
        brush_box.addWidget(self.obj_brush_btn)

        self.obj_clear_btn = QPushButton(tr("🧹 Clear Masks"))
        self.obj_clear_btn.clicked.connect(self.clear_object_removal_masks)
        brush_box.addWidget(self.obj_clear_btn)
        self._obj_form.addRow(brush_box)

        self.obj_radius_spin = QSpinBox()
        self.obj_radius_spin.setRange(5, 100)
        self.obj_radius_spin.setValue(25)
        self.obj_radius_spin.setSuffix(" px")
        self.obj_radius_spin.valueChanged.connect(self.update_eraser_radius)
        self._label_obj_radius = QLabel(tr("Brush Radius"))
        self._obj_form.addRow(self._label_obj_radius, self.obj_radius_spin)

        self.obj_track_btn = QPushButton(tr("🎯 Auto-Track Motion"))
        self.obj_track_btn.setStyleSheet("background: #2b5a8b; color: white; font-size: 11px; font-weight: bold; padding: 4px;")
        self.obj_track_btn.clicked.connect(self.run_object_tracking)
        self._obj_form.addRow(self.obj_track_btn)

        self.obj_mask_count_lbl = QLabel(tr("0 masks applied"))
        self.obj_mask_count_lbl.setStyleSheet("color: #a0a0b0; font-size: 11px;")
        self._obj_form.addRow(self.obj_mask_count_lbl)

        self.obj_removal_group.setLayout(self._obj_form)
        self.obj_removal_group.setVisible(False)
        lay.addWidget(self.obj_removal_group)

        lay.addStretch(1)

        self.stats = QLabel()
        self.stats.setObjectName("dimText")
        self.stats.setWordWrap(True)
        lay.addWidget(self.stats)

        scroll.setWidget(scroll_content)
        main_lay.addWidget(scroll)

    def retranslate(self):
        self._title.setText(tr("Inspector"))
        self.placeholder.setText(
            tr("Select a clip on the timeline to edit.\n\n"
               "Video: trim, position, opacity, transitions.\n"
               "Audio: trim, position, volume."))
        self.group.setTitle(tr("Clip"))
        self._label_name.setText(tr("Name"))
        self._label_type.setText(tr("Type"))
        self._label_pos.setText(tr("Start (s)"))
        self._label_dur.setText(tr("Duration (s)"))
        self._label_trim.setText(tr("Trim In (s)"))
        self._label_vol.setText(tr("Volume"))
        self._label_opacity.setText(tr("Opacity"))

        self.trans_group.setTitle(tr("Transitions"))
        self._label_in_type.setText(tr("Fade In (Entry)"))
        self._label_in_dur.setText(tr("Duration (s)"))
        self._label_out_type.setText(tr("Fade Out (Exit)"))
        self._label_out_dur.setText(tr("Duration (s)"))

        for idx, (t_code, t_name) in enumerate(TRANSITION_TYPES):
            self.in_type_combo.setItemText(idx, tr(t_name))
            self.out_type_combo.setItemText(idx, tr(t_name))

        self.sub_group.setTitle(tr("Subtitle Editor"))
        self._label_sub_text.setText(tr("Subtitle Text"))
        self._label_sub_pos.setText(tr("Start (s)"))
        self._label_sub_dur.setText(tr("Duration (s)"))
        self._label_sub_font.setText(tr("Font Family"))
        self._label_sub_size.setText(tr("Font Size"))
        self._label_sub_color.setText(tr("Font Color"))
        self._label_sub_bg.setText(tr("Background"))
        self._label_sub_stroke.setText(tr("Outline Width"))
        self._label_sub_align.setText(tr("Alignment"))
        self._label_sub_anim_effect.setText(tr("Animation Effect"))
        self._label_sub_anim_dur.setText(tr("Effect Duration (s)"))
        self.sub_anim_effect_combo.setItemText(0, tr("None"))
        self.sub_anim_effect_combo.setItemText(1, tr("Fly-In / Fly-Out"))
        self.sub_anim_effect_combo.setItemText(2, tr("Fade In / Fade Out"))
        self.sub_anim_effect_combo.setItemText(3, tr("Typewriter"))

        self.speed_group.setTitle(tr("Playback Speed (Slow/Fast Motion)"))
        self._label_speed.setText(tr("Speed Multiplier"))

        self.cc_group.setTitle(tr("Color Correction & Grading"))
        self._label_bright.setText(tr("Brightness"))
        self._label_contrast.setText(tr("Contrast"))
        self._label_sat.setText(tr("Saturation"))

        self.bf_group.setTitle(tr("Blur & Focus Effects"))
        self._label_focus_mode.setText(tr("Focus Mode"))
        self.focus_mode_combo.setItemText(0, tr("None"))
        self.focus_mode_combo.setItemText(1, tr("Gaussian Blur"))
        self.focus_mode_combo.setItemText(2, tr("Center Focus"))
        self.focus_mode_combo.setItemText(3, tr("Tilt Shift Focus"))
        self._label_blur_amt.setText(tr("Blur Intensity"))

        self.reload()
        self.stats.setText(self._project_stats())

    def on_selection_changed(self, clip_ids: list[str]):
        clips = [c for c in (self.controller.project.clip_by_id(i) for i in clip_ids)
                 if c is not None]
        if len(clips) != 1:
            self._clip_id = None
            if not getattr(self, "_sub_id", None):
                self.group.setVisible(False)
                self.trans_group.setVisible(False)
                self.ck_group.setVisible(False)
                self.speed_group.setVisible(False)
                self.cc_group.setVisible(False)
                self.bf_group.setVisible(False)
                self.sub_group.setVisible(False)
                self.placeholder.setVisible(True)
                self.stats.setText(self._project_stats())
            return
        self._sub_id = None
        self.sub_group.setVisible(False)
        self.placeholder.setVisible(False)
        self.group.setVisible(True)
        self._clip_id = clips[0].id
        self.reload()

    def select_subtitle(self, sub_id: str):
        sub = self.controller.project.subtitle_by_id(sub_id)
        if sub is None:
            return
        self._clip_id = None
        self.controller.clear_selection()
        self._sub_id = sub_id
        self.group.setVisible(False)
        self.trans_group.setVisible(False)
        self.ck_group.setVisible(False)
        self.speed_group.setVisible(False)
        self.cc_group.setVisible(False)
        self.bf_group.setVisible(False)
        self.placeholder.setVisible(False)
        self.sub_group.setVisible(True)
        self.reload_subtitle()

    def reload_subtitle(self):
        if not getattr(self, "_sub_id", None):
            return
        sub = self.controller.project.subtitle_by_id(self._sub_id)
        if sub is None:
            self.sub_group.setVisible(False)
            self.placeholder.setVisible(True)
            return
        self._loading = True
        self.sub_text_edit.setPlainText(sub.text)
        self.sub_pos_spin.setValue(sub.position)
        self.sub_dur_spin.setValue(sub.duration)
        font_idx = self.sub_font_combo.findData(sub.font_family)
        if font_idx >= 0:
            self.sub_font_combo.setCurrentIndex(font_idx)
        self.sub_size_spin.setValue(sub.font_size)
        self.sub_color_btn.setText(sub.font_color)
        self.sub_bg_btn.setText(sub.bg_color)
        self.sub_stroke_spin.setValue(sub.stroke_width)
        align_idx = self.sub_align_combo.findData(sub.alignment)
        if align_idx >= 0:
            self.sub_align_combo.setCurrentIndex(align_idx)
        anim_idx = self.sub_anim_effect_combo.findData(getattr(sub, "animation_effect", "none"))
        if anim_idx >= 0:
            self.sub_anim_effect_combo.setCurrentIndex(anim_idx)
        self.sub_anim_dur_spin.setValue(getattr(sub, "animation_duration", 0.5))
        self._loading = False

    def reload(self):
        if getattr(self, "_sub_id", None):
            self.reload_subtitle()
            return
        c = self.controller.project.clip_by_id(self._clip_id) if self._clip_id else None
        if c is None:
            return
        media = self.controller.project.clip_media(c)
        is_video = media is not None and media.has_video
        has_audio = media is not None and media.has_audio
        self._loading = True
        self.name_edit.setText(c.name)
        self.type_label.setText(tr("Video") if is_video else tr("Audio"))
        self.position_spin.setValue(c.position)
        self.duration_spin.setValue(c.duration)
        self.trim_spin.setValue(c.trim_in)
        self.vol_slider.setValue(int(c.volume * 100))
        self.opacity_slider.setValue(int(c.opacity * 100))
        self.vol_slider.setEnabled(has_audio)

        fx_idx = self.video_fx_combo.findData(getattr(c, "video_fx", "none"))
        if fx_idx >= 0:
            self.video_fx_combo.setCurrentIndex(fx_idx)

        self.trans_group.setVisible(is_video)
        self.ck_group.setVisible(is_video)
        self.speed_group.setVisible(c is not None)
        self.cc_group.setVisible(is_video)
        self.bf_group.setVisible(is_video)
        self.obj_removal_group.setVisible(is_video)

        if is_video:
            in_idx = self.in_type_combo.findData(c.fade_in_type)
            if in_idx >= 0:
                self.in_type_combo.setCurrentIndex(in_idx)
            self.in_dur_spin.setValue(c.fade_in_duration)

            out_idx = self.out_type_combo.findData(c.fade_out_type)
            if out_idx >= 0:
                self.out_type_combo.setCurrentIndex(out_idx)
            self.out_dur_spin.setValue(c.fade_out_duration)

            self.ck_enable_chk.setChecked(getattr(c, "chroma_key_enabled", False))
            self.ck_color_btn.setText(getattr(c, "chroma_key_color", "#00FF00"))
            self.ck_sim_spin.setValue(getattr(c, "chroma_key_similarity", 0.30))
            self.ck_smooth_spin.setValue(getattr(c, "chroma_key_smoothness", 0.10))

            self.brightness_spin.setValue(getattr(c, "brightness", 0.0))
            self.contrast_spin.setValue(getattr(c, "contrast", 1.0))
            self.saturation_spin.setValue(getattr(c, "saturation", 1.0))

            f_idx = self.focus_mode_combo.findData(getattr(c, "focus_mode", "none"))
            if f_idx >= 0:
                self.focus_mode_combo.setCurrentIndex(f_idx)
            self.blur_amount_spin.setValue(getattr(c, "blur_amount", 0.0))

            self.obj_enable_chk.setChecked(getattr(c, "object_removal_enabled", False))
            masks = getattr(c, "object_removal_masks", [])
            self.obj_mask_count_lbl.setText(f"{len(masks)} {tr('masks applied')}")

        if c:
            self.speed_spin.setValue(getattr(c, "speed", 1.0))

        self._loading = False

    def refresh_after_edit(self):
        if self._clip_id:
            self.reload()

    def _clip(self):
        return self.controller.project.clip_by_id(self._clip_id) if self._clip_id else None

    def kind_of(self, c):
        for tr in self.controller.project.video_tracks:
            if any(x.id == c.id for x in tr.clips):
                return "video"
        return "audio"

    def commit_name(self):
        c = self._clip()
        if c and c.name != self.name_edit.text():
            self.controller.rename_clip(c.id, self.name_edit.text())

    def commit_position(self, v):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.move_clip(c.id, v, c.track_index, self.kind_of(c))

    def commit_duration(self, v):
        if self._loading:
            return
        c = self._clip()
        if c:
            media = self.controller.project.clip_media(c)
            max_dur = media.duration - c.trim_in if media else 1e6
            self.controller.trim_clip(c.id, c.trim_in, min(v, max(0.001, max_dur)))

    def commit_trim(self, v):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.trim_clip(c.id, v, c.duration)

    def commit_volume(self, v):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.set_clip_volume(c.id, v / 100.0)

    def commit_opacity(self, v):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.set_clip_opacity(c.id, v / 100.0)

    def commit_transitions(self, *args):
        if self._loading:
            return
        c = self._clip()
        if c:
            in_dur = float(self.in_dur_spin.value())
            in_type = self.in_type_combo.currentData() or "fade"
            out_dur = float(self.out_dur_spin.value())
            out_type = self.out_type_combo.currentData() or "fade"
            self.controller.set_clip_transition(
                c.id,
                fade_in_dur=in_dur, fade_in_type=in_type,
                fade_out_dur=out_dur, fade_out_type=out_type,
            )

    def commit_subtitle(self, *args):
        if self._loading or not getattr(self, "_sub_id", None):
            return
        sub = self.controller.project.subtitle_by_id(self._sub_id)
        if sub is None:
            return
        self.controller.update_subtitle(
            self._sub_id,
            text=self.sub_text_edit.toPlainText(),
            position=float(self.sub_pos_spin.value()),
            duration=float(self.sub_dur_spin.value()),
            font_family=self.sub_font_combo.currentData() or "sans-serif",
            font_size=int(self.sub_size_spin.value()),
            stroke_width=int(self.sub_stroke_spin.value()),
            alignment=self.sub_align_combo.currentData() or "bottom_center",
            animation_effect=self.sub_anim_effect_combo.currentData() or "none",
            animation_duration=float(self.sub_anim_dur_spin.value()),
        )

    def _pick_sub_color(self):
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        if not getattr(self, "_sub_id", None):
            return
        sub = self.controller.project.subtitle_by_id(self._sub_id)
        curr = QColor(sub.font_color if sub else "#FFFFFF")
        color = QColorDialog.getColor(curr, self, tr("Font Color"))
        if color.isValid():
            hex_str = color.name().upper()
            self.sub_color_btn.setText(hex_str)
            self.controller.update_subtitle(self._sub_id, font_color=hex_str)

    def _pick_sub_bg(self):
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        if not getattr(self, "_sub_id", None):
            return
        sub = self.controller.project.subtitle_by_id(self._sub_id)
        curr = QColor(sub.bg_color[:7] if sub and len(sub.bg_color) >= 7 else "#000000")
        color = QColorDialog.getColor(curr, self, tr("Background Color"))
        if color.isValid():
            hex_str = color.name().upper() + "80"
            self.sub_bg_btn.setText(hex_str)
            self.controller.update_subtitle(self._sub_id, bg_color=hex_str)

    def commit_chroma_key(self, *args):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.set_clip_chroma_key(
                c.id,
                enabled=self.ck_enable_chk.isChecked(),
                color=self.ck_color_btn.text(),
                similarity=float(self.ck_sim_spin.value()),
                smoothness=float(self.ck_smooth_spin.value()),
            )

    def _pick_ck_color(self):
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        c = self._clip()
        curr_hex = c.chroma_key_color if c else "#00FF00"
        color = QColorDialog.getColor(QColor(curr_hex), self, tr("Key Color"))
        if color.isValid():
            hex_str = color.name().upper()
            self.ck_color_btn.setText(hex_str)
            self.commit_chroma_key()

    def _set_ck_preset(self, hex_color: str):
        self.ck_color_btn.setText(hex_color)
        self.commit_chroma_key()

    def commit_video_fx(self, *args):
        if self._loading:
            return
        c = self._clip()
        if c:
            fx_id = self.video_fx_combo.currentData() or "none"
            self.controller.set_clip_video_fx(c.id, fx_id)

    def commit_speed(self, *args):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.set_clip_speed(c.id, float(self.speed_spin.value()))

    def _set_speed_preset(self, val: float):
        self.speed_spin.setValue(val)
        self.commit_speed()

    def commit_color_correction(self, *args):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.set_clip_color_correction(
                c.id,
                brightness=float(self.brightness_spin.value()),
                contrast=float(self.contrast_spin.value()),
                saturation=float(self.saturation_spin.value()),
            )

    def commit_blur_focus(self, *args):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.set_clip_blur_focus(
                c.id,
                focus_mode=self.focus_mode_combo.currentData() or "none",
                blur_amount=float(self.blur_amount_spin.value()),
            )

    def commit_object_removal(self, enabled: bool):
        if self._loading:
            return
        c = self._clip()
        if c:
            self.controller.set_clip_object_removal(c.id, enabled=enabled)

    def toggle_magic_eraser_tool(self, checked: bool):
        main_win = self.window()
        preview = getattr(main_win, "preview", None)
        if preview:
            preview.set_eraser_mode(checked, radius=self.obj_radius_spin.value())

    def update_eraser_radius(self, radius: int):
        main_win = self.window()
        preview = getattr(main_win, "preview", None)
        if preview and getattr(preview, "_eraser_mode", False):
            preview.set_eraser_mode(True, radius=radius)

    def clear_object_removal_masks(self):
        c = self._clip()
        if c:
            self.controller.clear_object_removal_masks(c.id)
            self.reload()
            main_win = self.window()
            preview = getattr(main_win, "preview", None)
            if preview:
                preview._request_frame(force=True)

    def run_object_tracking(self):
        c = self._clip()
        if c:
            self.controller.track_clip_object_masks(c.id)
            self.reload()
            main_win = self.window()
            preview = getattr(main_win, "preview", None)
            if preview:
                preview._request_frame(force=True)

    def _project_stats(self) -> str:
        p = self.controller.project
        n_clips = sum(len(t.clips) for t in p.all_tracks())
        return (f"{tr('Project')}: {p.name}\n"
                f"{p.width}×{p.height}  {p.fps:.0f} fps\n"
                f"{len(p.media)} {tr('media')}  {n_clips} {tr('clips')}\n"
                f"{tr('Duration')}: {_dur(p.duration())}")


def _dur(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"