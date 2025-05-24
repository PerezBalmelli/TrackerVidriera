"""
Widget para la configuración de la salida de video en la aplicación TrackerVidriera.
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt


class OutputConfigWidget(QWidget):
    """Widget para configurar los parámetros de salida del video procesado."""

    output_path_changed = pyqtSignal(str)
    mobile_output_path_changed = pyqtSignal(str)
    codec_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codec_extension_map = {
            "XVID": ".avi", "MP4V": ".mp4", "MJPG": ".avi",
            "H264": ".mp4", "AVC1": ".mp4"
        }
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        output_group = QGroupBox("Configuración de salida")
        output_layout = QFormLayout(output_group)

        # --- Global Codec Selector ---
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["XVID", "MP4V", "MJPG", "H264", "AVC1"])
        self.codec_combo.currentTextChanged.connect(self._on_global_codec_changed)
        output_layout.addRow("Formato de Video (Global):", self.codec_combo)

        # --- Main Camera Output Settings ---
        self.output_path_edit = QLineEdit("salida_principal.avi")
        # Aunque no causó error, es buena práctica hacerlo atributo si se manipulará.
        self.main_output_save_button = QPushButton("Guardar como...")
        self.main_output_save_button.clicked.connect(self._set_main_output_file)

        self.save_main_camera_checkbox = QCheckBox()
        self.save_main_camera_checkbox.setToolTip("Guardar el video de la cámara principal")
        self.save_main_camera_checkbox.setChecked(True)

        main_output_controls_layout = QHBoxLayout()
        main_output_controls_layout.addWidget(self.output_path_edit)
        main_output_controls_layout.addWidget(self.main_output_save_button) # Usar el atributo
        main_output_controls_layout.addWidget(self.save_main_camera_checkbox)
        output_layout.addRow("Salida Principal:", main_output_controls_layout)

        # --- Mobile Camera Output Settings ---
        self.mobile_output_path_edit = QLineEdit("salida_movil.avi")
        # CORRECCIÓN AQUÍ:
        self.mobile_output_save_button = QPushButton("Guardar como...")
        self.mobile_output_save_button.clicked.connect(self._set_mobile_output_file)

        self.save_mobile_camera_checkbox = QCheckBox()
        self.save_mobile_camera_checkbox.setToolTip("Guardar el video de la cámara móvil")
        self.save_mobile_camera_checkbox.setChecked(False)
        self.save_mobile_camera_checkbox.stateChanged.connect(self._update_mobile_output_widgets_enabled)

        mobile_output_controls_layout = QHBoxLayout()
        mobile_output_controls_layout.addWidget(self.mobile_output_path_edit)
        mobile_output_controls_layout.addWidget(self.mobile_output_save_button) # Usar el atributo
        mobile_output_controls_layout.addWidget(self.save_mobile_camera_checkbox)
        output_layout.addRow("Salida Móvil:", mobile_output_controls_layout)

        layout.addWidget(output_group)
        self._update_mobile_output_widgets_enabled()
        self._on_global_codec_changed(self.codec_combo.currentText())


    def _update_mobile_output_widgets_enabled(self):
        """Habilita/deshabilita los controles de salida móvil basados en el checkbox."""
        enabled = self.save_mobile_camera_checkbox.isChecked()
        self.mobile_output_path_edit.setEnabled(enabled)
        self.mobile_output_save_button.setEnabled(enabled) # Ahora esto funcionará

    def _on_global_codec_changed(self, codec):
        if self.output_path_edit.text():
            new_main_path = self._ensure_valid_extension(
                self.output_path_edit.text(), codec
            )
            if new_main_path != self.output_path_edit.text():
                self.output_path_edit.setText(new_main_path)
                self.output_path_changed.emit(new_main_path)

        if self.save_mobile_camera_checkbox.isChecked() and self.mobile_output_path_edit.text():
            new_mobile_path = self._ensure_valid_extension(
                self.mobile_output_path_edit.text(), codec
            )
            if new_mobile_path != self.mobile_output_path_edit.text():
                self.mobile_output_path_edit.setText(new_mobile_path)
                self.mobile_output_path_changed.emit(new_mobile_path)

        self.codec_changed.emit(codec)

    def _set_main_output_file(self):
        self._set_output_file_generic(
            self.output_path_edit,
            self.output_path_changed,
            "Principal"
        )

    def _set_mobile_output_file(self):
        self._set_output_file_generic(
            self.mobile_output_path_edit,
            self.mobile_output_path_changed,
            "Móvil"
        )

    def _set_output_file_generic(self, path_edit_widget, path_changed_signal, title_suffix):
        codec = self.codec_combo.currentText()
        recommended_ext = self._get_recommended_extension(codec)

        current_path = path_edit_widget.text()
        default_base_name = f"salida_{title_suffix.lower()}"
        base_name = os.path.splitext(Path(current_path).name)[0] if current_path and Path(current_path).name else default_base_name

        if not Path(base_name).stem and Path(base_name).suffix == base_name:
             base_name = default_base_name
        elif not base_name:
             base_name = default_base_name

        default_file_name = f"{base_name}{recommended_ext}"

        suggested_dir = os.path.dirname(current_path) if current_path and os.path.dirname(current_path) else ""
        full_default_path = os.path.join(suggested_dir, default_file_name)

        filter_str = "MP4 (*.mp4);;AVI (*.avi);;MKV (*.mkv);;Todos los archivos (*)"
        if recommended_ext == ".avi":
            filter_str = "AVI (*.avi);;MP4 (*.mp4);;MKV (*.mkv);;Todos los archivos (*)"

        file_path, _ = QFileDialog.getSaveFileName(
            self, f"Guardar video {title_suffix} como", full_default_path, filter_str
        )

        if file_path:
            file_ext = os.path.splitext(file_path)[1].lower()
            if not file_ext:
                file_path += recommended_ext
                file_ext = recommended_ext

            path_edit_widget.setText(file_path)

            current_blocked_state = self.signalsBlocked()
            self.blockSignals(True)
            codec_updated_by_extension = self._update_codec_for_extension(file_ext, self.codec_combo)
            self.blockSignals(current_blocked_state)

            if codec_updated_by_extension:
                 self._on_global_codec_changed(self.codec_combo.currentText())
            else:
                path_changed_signal.emit(file_path)

    def _get_recommended_extension(self, codec):
        return self.codec_extension_map.get(codec.upper(), ".avi")

    def _ensure_valid_extension(self, file_path, codec):
        if not file_path:
            return file_path

        current_base, current_ext = os.path.splitext(file_path)
        current_ext = current_ext.lower()
        recommended_ext = self._get_recommended_extension(codec)

        if not current_base:
             return f"{current_base or 'salida'}{recommended_ext}"

        if current_ext not in [".avi", ".mp4", ".mkv"] or \
           (current_ext != recommended_ext and self._is_extension_incompatible(current_ext, codec)):
            new_path = current_base + recommended_ext
            return new_path
        return file_path

    def _is_extension_incompatible(self, extension, codec):
        codec = codec.upper()
        if extension == ".mp4" and codec not in ["MP4V", "H264", "AVC1"]:
            return True
        if extension == ".avi" and codec not in ["XVID", "MJPG"]:
            return True
        return False

    def _update_codec_for_extension(self, extension, codec_combo_widget):
        extension = extension.lower()
        current_codec_text = codec_combo_widget.currentText()

        new_codec_str = None
        if extension == ".mp4" and current_codec_text not in ["MP4V", "H264", "AVC1"]:
            new_codec_str = "MP4V"
        elif extension == ".avi" and current_codec_text not in ["XVID", "MJPG"]:
            new_codec_str = "XVID"

        if new_codec_str:
            new_codec_index = codec_combo_widget.findText(new_codec_str)
            if new_codec_index >= 0:
                if codec_combo_widget.currentIndex() != new_codec_index:
                    codec_combo_widget.setCurrentIndex(new_codec_index)
                    return True
        return False

    def get_output_path(self):
        return self.output_path_edit.text()

    def set_output_path(self, path):
        self.output_path_edit.setText(path or "salida_principal.avi")
        if path and hasattr(self, 'codec_combo') and self.codec_combo.count() > 0 : # Asegurar que codec_combo existe y tiene items
            self._on_global_codec_changed(self.codec_combo.currentText())

    def get_codec(self):
        return self.codec_combo.currentText()

    def set_codec(self, codec):
        current_blocked_state = self.signalsBlocked()
        self.blockSignals(True)

        index = self.codec_combo.findText(codec)
        made_change = False
        if index >= 0:
            if self.codec_combo.currentIndex() != index:
                self.codec_combo.setCurrentIndex(index)
                made_change = True
        elif self.codec_combo.count() > 0:
            if self.codec_combo.currentIndex() != 0:
                self.codec_combo.setCurrentIndex(0)
                made_change = True

        self.blockSignals(current_blocked_state)

        if not made_change or self.codec_combo.currentText() == codec:
             self._on_global_codec_changed(self.codec_combo.currentText())

    def should_save_main_camera(self):
        return self.save_main_camera_checkbox.isChecked()

    def get_mobile_output_path(self):
        return self.mobile_output_path_edit.text()

    def set_mobile_output_path(self, path):
        self.mobile_output_path_edit.setText(path or "salida_movil.avi")
        if path and hasattr(self, 'codec_combo') and self.codec_combo.count() > 0 : # Asegurar que codec_combo existe y tiene items
             self._on_global_codec_changed(self.codec_combo.currentText())

    def should_save_mobile_camera(self):
        return self.save_mobile_camera_checkbox.isChecked()

    def set_save_main_camera(self, checked):
        self.save_main_camera_checkbox.setChecked(checked)

    def set_save_mobile_camera(self, checked):
        self.save_mobile_camera_checkbox.setChecked(checked)
        self._update_mobile_output_widgets_enabled()