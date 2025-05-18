"""
Módulo que contiene los widgets personalizados para la UI de TrackerVidriera.
"""

from ui.widgets.input_config_widget import InputConfigWidget, CameraThread
from ui.widgets.model_config_widget import ModelConfigWidget
from ui.widgets.output_config_widget import OutputConfigWidget
from ui.widgets.serial_config_widget import SerialConfigWidget
from ui.widgets.video_display_widget import VideoDisplayWidget
from ui.widgets.action_buttons_widget import ActionButtonsWidget
from ui.widgets.collapsible_panel_widget import CollapsiblePanelWidget

__all__ = [
    'InputConfigWidget',
    'CameraThread',
    'ModelConfigWidget',
    'OutputConfigWidget',
    'SerialConfigWidget',
    'VideoDisplayWidget',
    'ActionButtonsWidget'
]
