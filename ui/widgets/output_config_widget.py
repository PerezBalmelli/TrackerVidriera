"""
Widget para la configuración de la salida de video en la aplicación TrackerVidriera.
"""
import os
import logging  # Added
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QStandardPaths

logger = logging.getLogger(__name__)  # Added


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
        self.codec_combo.addItems(["XVID", "MP4V", "MJPG", "H264", "AVC1"])  # Common codecs
        self.codec_combo.currentTextChanged.connect(self._on_global_codec_changed)
        output_layout.addRow("Formato de Video (Global):", self.codec_combo)

        # --- Main Camera Output Settings ---
        self.output_path_edit = QLineEdit("salida_principal.avi")
        self.main_output_save_button = QPushButton("Guardar como...")
        self.main_output_save_button.clicked.connect(self._set_main_output_file)

        self.save_main_camera_checkbox = QCheckBox()
        self.save_main_camera_checkbox.setToolTip("Guardar el video de la cámara principal")
        self.save_main_camera_checkbox.setChecked(True)

        main_output_controls_layout = QHBoxLayout()
        main_output_controls_layout.addWidget(self.output_path_edit)
        main_output_controls_layout.addWidget(self.main_output_save_button)
        main_output_controls_layout.addWidget(self.save_main_camera_checkbox)
        output_layout.addRow("Salida Principal:", main_output_controls_layout)

        # --- Mobile Camera Output Settings ---
        self.mobile_output_path_edit = QLineEdit("salida_movil.avi")
        self.mobile_output_save_button = QPushButton("Guardar como...")
        self.mobile_output_save_button.clicked.connect(self._set_mobile_output_file)

        self.save_mobile_camera_checkbox = QCheckBox()
        self.save_mobile_camera_checkbox.setToolTip("Guardar el video de la cámara móvil")
        self.save_mobile_camera_checkbox.setChecked(False)
        self.save_mobile_camera_checkbox.stateChanged.connect(self._update_mobile_output_widgets_enabled)

        mobile_output_controls_layout = QHBoxLayout()
        mobile_output_controls_layout.addWidget(self.mobile_output_path_edit)
        mobile_output_controls_layout.addWidget(self.mobile_output_save_button)
        mobile_output_controls_layout.addWidget(self.save_mobile_camera_checkbox)
        output_layout.addRow("Salida Móvil:", mobile_output_controls_layout)

        layout.addWidget(output_group)
        self._update_mobile_output_widgets_enabled()
        if self.codec_combo.count() > 0:  # Ensure combo is populated
            self._on_global_codec_changed(self.codec_combo.currentText())

    def _update_mobile_output_widgets_enabled(self):
        """Habilita/deshabilita los controles de salida móvil basados en el checkbox."""
        enabled = self.save_mobile_camera_checkbox.isChecked()
        self.mobile_output_path_edit.setEnabled(enabled)
        self.mobile_output_save_button.setEnabled(enabled)

    def _on_global_codec_changed(self, codec):
        logger.debug(f"Global codec changed to: {codec}")
        if self.output_path_edit.text():
            new_main_path = self._ensure_valid_extension(
                self.output_path_edit.text(), codec
            )
            if new_main_path != self.output_path_edit.text():
                self.output_path_edit.setText(new_main_path)
                self.output_path_changed.emit(new_main_path)  # Emit only if changed

        if self.save_mobile_camera_checkbox.isChecked() and self.mobile_output_path_edit.text():
            new_mobile_path = self._ensure_valid_extension(
                self.mobile_output_path_edit.text(), codec
            )
            if new_mobile_path != self.mobile_output_path_edit.text():
                self.mobile_output_path_edit.setText(new_mobile_path)
                self.mobile_output_path_changed.emit(new_mobile_path)  # Emit only if changed

        self.codec_changed.emit(codec)

    def _set_main_output_file(self):
        self._set_output_file_generic(
            self.output_path_edit,
            self.output_path_changed,
            "Principal"
        )

    def _set_mobile_output_file(self):
        if not self.save_mobile_camera_checkbox.isChecked():
            logger.info("Guardar como para cámara móvil clickeado, pero la opción no está activada.")
            return  # Do nothing if save mobile is not checked

        self._set_output_file_generic(
            self.mobile_output_path_edit,
            self.mobile_output_path_changed,
            "Móvil"
        )

    def _set_output_file_generic(self, path_edit_widget, path_changed_signal, title_suffix):
        codec = self.codec_combo.currentText()
        recommended_ext = self._get_recommended_extension(codec)

        current_path_str = path_edit_widget.text()
        current_path = Path(current_path_str)

        default_base_name_str = f"salida_{title_suffix.lower()}"

        # Suggest directory from current path or user's documents/videos directory
        if current_path.name and current_path.parent.exists():
            suggested_dir = str(current_path.parent)
            base_name = current_path.stem
        else:
            suggested_dir = QFileDialog.getExistingDirectory(self, f"Seleccionar carpeta para Salida {title_suffix}")
            if not suggested_dir:  # User cancelled folder selection
                # Fallback to a known directory or simply the current working directory
                documents_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
                videos_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)
                suggested_dir = videos_path or documents_path or os.getcwd()

            base_name = default_base_name_str

        if not base_name:  # if current_path.stem was empty
            base_name = default_base_name_str

        default_file_name = f"{base_name}{recommended_ext}"
        full_default_path = os.path.join(suggested_dir, default_file_name)

        filter_str = f"{codec.upper()} (*{self._get_recommended_extension(codec)});;MP4 (*.mp4);;AVI (*.avi);;MKV (*.mkv);;Todos los archivos (*)"
        # Prioritize the recommended extension's filter
        if recommended_ext == ".avi":
            filter_str = f"AVI (*.avi);;MP4 (*.mp4);;{codec.upper()} (*{self._get_recommended_extension(codec)});;MKV (*.mkv);;Todos los archivos (*)"
        elif recommended_ext == ".mp4":
            filter_str = f"MP4 (*.mp4);;AVI (*.avi);;{codec.upper()} (*{self._get_recommended_extension(codec)});;MKV (*.mkv);;Todos los archivos (*)"

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, f"Guardar video {title_suffix} como", full_default_path, filter_str
        )

        if file_path:
            file_path_obj = Path(file_path)
            chosen_ext = file_path_obj.suffix.lower()

            # If user types name without extension, but selects a filter with specific extension
            if not chosen_ext and selected_filter:
                if "(*.mp4)" in selected_filter:
                    chosen_ext = ".mp4"
                elif "(*.avi)" in selected_filter:
                    chosen_ext = ".avi"
                elif "(*.mkv)" in selected_filter:
                    chosen_ext = ".mkv"

            if not chosen_ext:  # Still no extension, use recommended
                file_path_obj = file_path_obj.with_suffix(recommended_ext)

            file_path = str(file_path_obj)
            path_edit_widget.setText(file_path)
            logger.info(f"Ruta de salida {title_suffix} establecida a: {file_path}")

            # Block signals to prevent recursive updates if codec change also changes path
            current_blocked_state = self.signalsBlocked()
            self.blockSignals(True)
            codec_updated_by_extension = self._update_codec_for_extension(file_path_obj.suffix.lower(),
                                                                          self.codec_combo)
            self.blockSignals(current_blocked_state)

            if codec_updated_by_extension:
                self._on_global_codec_changed(
                    self.codec_combo.currentText())  # This will emit path_changed_signal if path changes
            else:
                path_changed_signal.emit(file_path)  # Path changed by user, codec didn't need to adjust it

    def _get_recommended_extension(self, codec):
        return self.codec_extension_map.get(codec.upper(), ".mkv")  # Default to .mkv if unknown

    def _ensure_valid_extension(self, file_path_str, codec):
        if not file_path_str:
            return file_path_str  # Return empty if provided empty

        file_path = Path(file_path_str)
        current_base = file_path.stem
        current_ext = file_path.suffix.lower()
        recommended_ext = self._get_recommended_extension(codec)

        if not current_base:  # e.g. path is just ".avi" or empty after split
            return f"{'salida'}{recommended_ext}"

        # If current extension is not one of the common ones or is incompatible
        if current_ext not in [".avi", ".mp4", ".mkv"] or \
                (current_ext != recommended_ext and self._is_extension_incompatible(current_ext, codec)):
            new_path_str = str(file_path.with_suffix(recommended_ext))
            logger.info(f"Ajustando extensión de '{file_path_str}' a '{new_path_str}' para el codec {codec}")
            return new_path_str
        return file_path_str

    def _is_extension_incompatible(self, extension, codec):
        codec_upper = codec.upper()
        # H264 and AVC1 are often in MP4 or MKV. MP4V is specific to MP4.
        # XVID and MJPG are often in AVI.
        if extension == ".mp4" and codec_upper not in ["MP4V", "H264", "AVC1"]:
            return True
        if extension == ".avi" and codec_upper not in ["XVID", "MJPG"]:  # Allow H264 in AVI too, though less common
            return True
        # MKV is a versatile container, less strict incompatibilities.
        return False

    def _update_codec_for_extension(self, extension, codec_combo_widget):
        """Updates codec in combo box if current selection is incompatible with chosen file extension."""
        ext_lower = extension.lower()
        current_codec_text = codec_combo_widget.currentText()
        new_codec_str = None

        if ext_lower == ".mp4":
            if current_codec_text not in ["MP4V", "H264", "AVC1"]:
                new_codec_str = "MP4V"  # Default for .mp4
        elif ext_lower == ".avi":
            if current_codec_text not in ["XVID", "MJPG"]:
                new_codec_str = "XVID"  # Default for .avi
        # No specific codec change for .mkv as it's flexible

        if new_codec_str:
            new_codec_index = codec_combo_widget.findText(new_codec_str)
            if new_codec_index >= 0:
                if codec_combo_widget.currentIndex() != new_codec_index:
                    logger.info(f"Cambiando codec a {new_codec_str} para coincidir con la extensión {ext_lower}")
                    codec_combo_widget.setCurrentIndex(new_codec_index)
                    # The _on_global_codec_changed connected to currentTextChanged will handle emitting codec_changed
                    return True  # Codec was changed
        return False  # Codec was not changed

    def get_output_path(self):
        return self.output_path_edit.text()

    def set_output_path(self, path):
        self.output_path_edit.setText(path or "salida_principal.avi")
        # Ensure UI consistency when path is set externally
        if hasattr(self, 'codec_combo') and self.codec_combo.count() > 0:
            self._on_global_codec_changed(self.codec_combo.currentText())

    def get_codec(self):
        return self.codec_combo.currentText()

    def set_codec(self, codec):
        # Block signals to prevent path changes from _on_global_codec_changed
        # if we are only setting the codec to match a loaded setting.
        current_blocked_state = self.signalsBlocked()
        self.blockSignals(True)

        index = self.codec_combo.findText(codec)
        made_change = False
        if index >= 0:
            if self.codec_combo.currentIndex() != index:
                self.codec_combo.setCurrentIndex(index)
                made_change = True
        elif self.codec_combo.count() > 0:  # Codec not found, select first available
            if self.codec_combo.currentIndex() != 0:
                self.codec_combo.setCurrentIndex(0)
                logger.warning(f"Codec '{codec}' no encontrado. Usando '{self.codec_combo.currentText()}'.")
                made_change = True  # Technically a change if it wasn't already 0

        self.blockSignals(current_blocked_state)

        # If the codec was programmatically changed, or if it wasn't but we need to ensure consistency
        # (e.g. path might need extension update for the *current* codec)
        # we call _on_global_codec_changed.
        # However, if set_codec itself forces a change, currentTextChanged already triggers _on_global_codec_changed.
        # To avoid double calls or calls when path shouldn't change due to only codec change:
        if made_change:
            # The currentTextChanged signal would have already called _on_global_codec_changed.
            # If no change was made to the index, but we still want to ensure consistency:
            pass
        else:  # No index change, but paths might need to be synced with the current codec
            self._on_global_codec_changed(self.codec_combo.currentText())

    def should_save_main_camera(self):
        return self.save_main_camera_checkbox.isChecked()

    def get_mobile_output_path(self):
        return self.mobile_output_path_edit.text()

    def set_mobile_output_path(self, path):
        self.mobile_output_path_edit.setText(path or "salida_movil.avi")
        if hasattr(self, 'codec_combo') and self.codec_combo.count() > 0:
            self._on_global_codec_changed(self.codec_combo.currentText())

    def should_save_mobile_camera(self):
        return self.save_mobile_camera_checkbox.isChecked()

    def set_save_main_camera(self, checked):
        self.save_main_camera_checkbox.setChecked(checked)

    def set_save_mobile_camera(self, checked):
        self.save_mobile_camera_checkbox.setChecked(checked)
        self._update_mobile_output_widgets_enabled()  # Ensure dependent widgets update state