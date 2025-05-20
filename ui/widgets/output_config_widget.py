"""
Widget para la configuración de la salida de video en la aplicación TrackerVidriera.
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit
)
from PyQt6.QtCore import pyqtSignal, QStandardPaths # QStandardPaths ya no es necesario para el default


class OutputConfigWidget(QWidget):
    """Widget para configurar los parámetros de salida del video procesado y de la cámara móvil."""

    output_path_changed = pyqtSignal(str)
    codec_changed = pyqtSignal(str)
    second_cam_output_path_changed = pyqtSignal(str)
    second_cam_codec_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.codec_extension_map = {
            "XVID": ".avi", "MP4V": ".mp4", "MJPG": ".avi",
            "H264": ".mp4", "AVC1": ".mp4"
        }
        self._init_ui()

    def _init_ui(self):
        main_v_layout = QVBoxLayout(self)
        main_v_layout.setContentsMargins(0, 0, 0, 0)

        # --- Grupo ÚNICO de configuración de salida ---
        self.output_config_group = QGroupBox("Configuración de Salida de Video")
        form_layout = QFormLayout(self.output_config_group) # Usaremos este QFormLayout para todo

        # --- Salida Principal (Video Procesado) ---
        self.main_output_path_label = QLabel("Archivo Procesado Principal:")
        self.output_path_edit = QLineEdit(str(Path.cwd() / "salida_procesada.avi"))
        main_output_save_button = QPushButton("Guardar como...")
        main_output_save_button.clicked.connect(self._set_main_output_file)

        main_output_path_widget_container = QHBoxLayout()
        main_output_path_widget_container.addWidget(self.output_path_edit)
        main_output_path_widget_container.addWidget(main_output_save_button)
        form_layout.addRow(self.main_output_path_label, main_output_path_widget_container)

        self.main_codec_label = QLabel("Formato Procesado Principal:")
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(list(self.codec_extension_map.keys()))
        self.codec_combo.currentTextChanged.connect(self._on_main_codec_changed)
        form_layout.addRow(self.main_codec_label, self.codec_combo)

        # --- Salida Segunda Cámara (Video Crudo) ---
        self.sec_cam_path_label = QLabel("Archivo Cámara Móvil (Crudo):")
        self.second_cam_output_path_edit = QLineEdit(str(Path.cwd() / "salida_cam2_crudo.avi"))
        sec_cam_output_save_button = QPushButton("Guardar como...")
        sec_cam_output_save_button.clicked.connect(self._set_second_cam_output_file)

        self.sec_cam_path_widget_container = QWidget() # Contenedor para el QHBoxLayout
        sec_cam_path_layout = QHBoxLayout(self.sec_cam_path_widget_container)
        sec_cam_path_layout.setContentsMargins(0,0,0,0)
        sec_cam_path_layout.addWidget(self.second_cam_output_path_edit)
        sec_cam_path_layout.addWidget(sec_cam_output_save_button)
        form_layout.addRow(self.sec_cam_path_label, self.sec_cam_path_widget_container)

        self.sec_cam_codec_label = QLabel("Formato Cámara Móvil (Crudo):")
        self.second_cam_codec_combo = QComboBox()
        self.second_cam_codec_combo.addItems(list(self.codec_extension_map.keys()))
        self.second_cam_codec_combo.currentTextChanged.connect(self._on_second_cam_codec_changed)
        form_layout.addRow(self.sec_cam_codec_label, self.second_cam_codec_combo)

        main_v_layout.addWidget(self.output_config_group)

        # Ocultar campos de la segunda cámara por defecto
        self.set_second_camera_output_visible(False)

    def _on_main_codec_changed(self, codec):
        if self.output_path_edit.text():
            new_path = self._ensure_valid_extension(self.output_path_edit.text(), codec)
            if new_path != self.output_path_edit.text():
                self.output_path_edit.setText(new_path)
                self.output_path_changed.emit(new_path)
        self.codec_changed.emit(codec)

    def _set_main_output_file(self):
        self._handle_set_output_file_dialog(
            self.output_path_edit,
            self.codec_combo,
            self.output_path_changed
        )

    def _on_second_cam_codec_changed(self, codec):
        if self.second_cam_output_path_edit.text():
            new_path = self._ensure_valid_extension(self.second_cam_output_path_edit.text(), codec)
            if new_path != self.second_cam_output_path_edit.text():
                self.second_cam_output_path_edit.setText(new_path)
                self.second_cam_output_path_changed.emit(new_path)
        self.second_cam_codec_changed.emit(codec)

    def _set_second_cam_output_file(self):
        self._handle_set_output_file_dialog(
            self.second_cam_output_path_edit,
            self.second_cam_codec_combo,
            self.second_cam_output_path_changed
        )

    def set_second_camera_output_visible(self, visible):
        """Muestra u oculta las filas de configuración para la segunda cámara."""
        if hasattr(self, 'sec_cam_path_label'):
            self.sec_cam_path_label.setVisible(visible)
        if hasattr(self, 'sec_cam_path_widget_container'):
            self.sec_cam_path_widget_container.setVisible(visible)
        if hasattr(self, 'sec_cam_codec_label'):
            self.sec_cam_codec_label.setVisible(visible)
        if hasattr(self, 'second_cam_codec_combo'):
            self.second_cam_codec_combo.setVisible(visible)

    def _handle_set_output_file_dialog(self, path_edit_widget, codec_combo_widget, path_changed_signal):
        codec = codec_combo_widget.currentText()
        recommended_ext = self._get_recommended_extension(codec)
        current_path_text = path_edit_widget.text()
        current_path_obj = Path(current_path_text)

        initial_dir_for_dialog = str(current_path_obj.parent if current_path_obj.is_absolute() and current_path_obj.parent.exists() else Path.cwd())
        base_name_for_dialog = current_path_obj.stem if current_path_obj.stem else "video_salida"
        default_full_path_for_dialog = os.path.join(initial_dir_for_dialog, f"{base_name_for_dialog}{recommended_ext}")

        filter_list = []
        if recommended_ext == ".mp4": filter_list.append("MP4 (*.mp4)")
        elif recommended_ext == ".avi": filter_list.append("AVI (*.avi)")
        if "MP4 (*.mp4)" not in filter_list: filter_list.append("MP4 (*.mp4)")
        if "AVI (*.avi)" not in filter_list: filter_list.append("AVI (*.avi)")
        filter_list.append("MKV (*.mkv)"); filter_list.append("Todos los archivos (*)")
        filter_str = ";;".join(filter_list)

        file_path, selected_filter = QFileDialog.getSaveFileName(
            self, "Guardar video como", default_full_path_for_dialog, filter_str
        )

        if file_path:
            file_path_obj = Path(file_path)
            if not file_path_obj.suffix:
                if selected_filter and "(*" in selected_filter:
                    ext_from_filter = selected_filter[selected_filter.find("(*")+2 : selected_filter.find(")")]
                    if ext_from_filter != "*": file_path_obj = file_path_obj.with_suffix(ext_from_filter)
                    else: file_path_obj = file_path_obj.with_suffix(recommended_ext)
                else: file_path_obj = file_path_obj.with_suffix(recommended_ext)
            path_edit_widget.setText(str(file_path_obj))
            self._update_codec_for_extension(file_path_obj.suffix, codec_combo_widget)
            path_changed_signal.emit(str(file_path_obj))

    def _get_recommended_extension(self, codec_text):
        return self.codec_extension_map.get(codec_text.upper(), ".avi")

    def _ensure_valid_extension(self, file_path_str, codec_text):
        if not file_path_str or not codec_text: return file_path_str
        file_path = Path(file_path_str); current_ext = file_path.suffix.lower()
        recommended_ext = self._get_recommended_extension(codec_text)
        if current_ext != recommended_ext: return str(file_path.with_suffix(recommended_ext))
        return file_path_str

    def _update_codec_for_extension(self, extension, codec_combo_widget):
        extension = extension.lower(); current_codec_text = codec_combo_widget.currentText()
        new_codec_to_set = None
        if self.codec_extension_map.get(current_codec_text.upper()) == extension: return False
        for codec, ext_map in self.codec_extension_map.items():
            if ext_map == extension:
                if new_codec_to_set is None: new_codec_to_set = codec
        if new_codec_to_set:
            index = codec_combo_widget.findText(new_codec_to_set)
            if index >= 0 and codec_combo_widget.currentIndex() != index:
                codec_combo_widget.setCurrentIndex(index); return True
        return False

    def get_output_path(self): return self.output_path_edit.text()
    def set_output_path(self, path):
        resolved_path = path or str(Path.cwd() / "salida_procesada.avi")
        self.output_path_edit.setText(resolved_path)
        self._update_codec_for_extension(Path(resolved_path).suffix, self.codec_combo)

    def get_codec(self): return self.codec_combo.currentText()
    def set_codec(self, codec_text):
        index = self.codec_combo.findText(codec_text)
        if index >= 0: self.codec_combo.setCurrentIndex(index)
        elif self.codec_combo.count() > 0: self.codec_combo.setCurrentIndex(0)

    def get_second_cam_output_path(self): return self.second_cam_output_path_edit.text()
    def set_second_cam_output_path(self, path):
        resolved_path = path or str(Path.cwd() / "salida_cam2_crudo.avi")
        self.second_cam_output_path_edit.setText(resolved_path)
        self._update_codec_for_extension(Path(resolved_path).suffix, self.second_cam_codec_combo)

    def get_second_cam_codec(self): return self.second_cam_codec_combo.currentText()
    def set_second_cam_codec(self, codec_text):
        index = self.second_cam_codec_combo.findText(codec_text)
        if index >= 0: self.second_cam_codec_combo.setCurrentIndex(index)
        elif self.second_cam_codec_combo.count() > 0: self.second_cam_codec_combo.setCurrentIndex(0)

