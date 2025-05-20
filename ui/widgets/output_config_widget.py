"""
Widget para la configuración de la salida de video en la aplicación TrackerVidriera.
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QFormLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit
)
from PyQt6.QtCore import pyqtSignal, QStandardPaths


class OutputConfigWidget(QWidget):
    """Widget para configurar los parámetros de salida del video procesado y de la cámara móvil."""

    # Señal para el path del video principal
    main_output_path_changed = pyqtSignal(str)
    # Señal para el path del video de la segunda cámara
    second_cam_output_path_changed = pyqtSignal(str)
    # Señal UNIFICADA para el formato de video
    video_format_changed = pyqtSignal(str)

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

        self.output_config_group = QGroupBox("Configuración de Salida de Video")
        form_layout = QFormLayout(self.output_config_group)

        # --- Salida Principal (Video Procesado) ---
        self.main_output_path_label = QLabel("Archivo Procesado Principal:")
        self.output_path_edit = QLineEdit(str(Path.cwd() / "salida_procesada.avi"))
        main_output_save_button = QPushButton("Guardar como...")
        main_output_save_button.clicked.connect(self._set_main_output_file)

        main_output_path_widget_container = QHBoxLayout()
        main_output_path_widget_container.addWidget(self.output_path_edit)
        main_output_path_widget_container.addWidget(main_output_save_button)
        form_layout.addRow(self.main_output_path_label, main_output_path_widget_container)

        # --- Salida Segunda Cámara (Video Crudo) ---
        self.sec_cam_path_label = QLabel("Archivo Cámara Móvil (Crudo):")
        self.second_cam_output_path_edit = QLineEdit(str(Path.cwd() / "salida_cam2_crudo.avi"))
        sec_cam_output_save_button = QPushButton("Guardar como...")
        sec_cam_output_save_button.clicked.connect(self._set_second_cam_output_file)

        self.sec_cam_path_widget_container = QWidget()
        sec_cam_path_layout = QHBoxLayout(self.sec_cam_path_widget_container)
        sec_cam_path_layout.setContentsMargins(0,0,0,0)
        sec_cam_path_layout.addWidget(self.second_cam_output_path_edit)
        sec_cam_path_layout.addWidget(sec_cam_output_save_button)
        form_layout.addRow(self.sec_cam_path_label, self.sec_cam_path_widget_container)

        # --- Selector de Formato de Video UNIFICADO ---
        self.video_format_label = QLabel("Formato de Video (para ambos):")
        self.video_format_combo = QComboBox()
        self.video_format_combo.addItems(list(self.codec_extension_map.keys()))
        self.video_format_combo.currentTextChanged.connect(self._on_video_format_changed)
        form_layout.addRow(self.video_format_label, self.video_format_combo)

        main_v_layout.addWidget(self.output_config_group)

        self.set_second_camera_output_visible(False) # Ocultar campos de la segunda cámara por defecto

    def _on_video_format_changed(self, video_format):
        """Maneja el cambio del formato de video unificado."""
        # Actualizar extensión del archivo principal si es necesario
        if self.output_path_edit.text():
            new_main_path = self._ensure_valid_extension(self.output_path_edit.text(), video_format)
            if new_main_path != self.output_path_edit.text():
                self.output_path_edit.setText(new_main_path)
                self.main_output_path_changed.emit(new_main_path) # Emitir si cambió

        # Actualizar extensión del archivo de la segunda cámara si es necesario
        if self.second_cam_output_path_edit.text():
            new_sec_cam_path = self._ensure_valid_extension(self.second_cam_output_path_edit.text(), video_format)
            if new_sec_cam_path != self.second_cam_output_path_edit.text():
                self.second_cam_output_path_edit.setText(new_sec_cam_path)
                self.second_cam_output_path_changed.emit(new_sec_cam_path) # Emitir si cambió

        self.video_format_changed.emit(video_format) # Emitir el cambio de formato

    def _set_main_output_file(self):
        self._handle_set_output_file_dialog(
            self.output_path_edit,
            self.video_format_combo, # Usar el combo unificado
            self.main_output_path_changed
        )

    def _set_second_cam_output_file(self):
        self._handle_set_output_file_dialog(
            self.second_cam_output_path_edit,
            self.video_format_combo, # Usar el combo unificado
            self.second_cam_output_path_changed
        )

    def set_second_camera_output_visible(self, visible):
        if hasattr(self, 'sec_cam_path_label'):
            self.sec_cam_path_label.setVisible(visible)
        if hasattr(self, 'sec_cam_path_widget_container'):
            self.sec_cam_path_widget_container.setVisible(visible)
        # El selector de formato ahora es global, no se oculta con esta función

    def _handle_set_output_file_dialog(self, path_edit_widget, codec_combo_widget, path_changed_signal):
        # Este método ya usa el codec_combo_widget que se le pasa,
        # así que funcionará bien con el video_format_combo unificado.
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
            # Actualizar el combo de formato unificado si la extensión no coincide
            self._update_codec_for_extension(file_path_obj.suffix, self.video_format_combo)
            path_changed_signal.emit(str(file_path_obj))

    def _get_recommended_extension(self, codec_text):
        return self.codec_extension_map.get(codec_text.upper(), ".avi")

    def _ensure_valid_extension(self, file_path_str, codec_text):
        if not file_path_str or not codec_text: return file_path_str
        file_path = Path(file_path_str); current_ext = file_path.suffix.lower()
        recommended_ext = self._get_recommended_extension(codec_text)
        if current_ext != recommended_ext: return str(file_path.with_suffix(recommended_ext))
        return file_path_str

    def _update_codec_for_extension(self, extension, codec_combo_widget): # codec_combo_widget ahora es siempre self.video_format_combo
        extension = extension.lower()
        current_video_format = codec_combo_widget.currentText() # Usar el combo unificado

        new_format_to_set = None
        # Si el formato actual ya es compatible con la extensión, no hacer nada
        if self.codec_extension_map.get(current_video_format.upper()) == extension:
            return False

        for fmt, ext_map in self.codec_extension_map.items():
            if ext_map == extension:
                if new_format_to_set is None: new_format_to_set = fmt # Tomar el primero compatible

        if new_format_to_set:
            index = codec_combo_widget.findText(new_format_to_set)
            if index >= 0 and codec_combo_widget.currentIndex() != index:
                codec_combo_widget.setCurrentIndex(index) # Esto emitirá la señal _on_video_format_changed
                return True
        return False

    # --- Métodos públicos para acceder/establecer valores ---
    def get_main_output_path(self): return self.output_path_edit.text() # Renombrado para claridad
    def set_main_output_path(self, path): # Renombrado para claridad
        resolved_path = path or str(Path.cwd() / "salida_procesada.avi")
        self.output_path_edit.setText(resolved_path)
        # Sincronizar formato con la extensión al cargar, usando el combo unificado
        self._update_codec_for_extension(Path(resolved_path).suffix, self.video_format_combo)

    def get_second_cam_output_path(self): return self.second_cam_output_path_edit.text()
    def set_second_cam_output_path(self, path):
        resolved_path = path or str(Path.cwd() / "salida_cam2_crudo.avi")
        self.second_cam_output_path_edit.setText(resolved_path)
        # Sincronizar formato con la extensión al cargar, usando el combo unificado
        self._update_codec_for_extension(Path(resolved_path).suffix, self.video_format_combo)

    def get_video_format(self): # Método unificado
        return self.video_format_combo.currentText()

    def set_video_format(self, video_format_text): # Método unificado
        index = self.video_format_combo.findText(video_format_text)
        if index >= 0:
            self.video_format_combo.setCurrentIndex(index)
        elif self.video_format_combo.count() > 0: # Si no se encuentra, seleccionar el primero
            self.video_format_combo.setCurrentIndex(0)