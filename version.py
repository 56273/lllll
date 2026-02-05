# XML Injector version 2
# by Scumbumbo @ MTS
#
# The version module contains functions to test the XML Injector version and display a dialog
# for any mods that require a specific version of the injector.
#
# This mod is intended as a standard for modder's to use as a shared library.  Please do not
# distribute any modifications anywhere other than the mod's main download site.  Modification
# suggestions and bug notices should be communicated to the maintainer, currently Scumbumbo at
# the Mod The Sims website - http://modthesims.info/member.php?u=7401825
#
import sims4.log
import sims4.callback_utils
import zone
from ui.ui_dialog import UiDialogOk
from sims4.localization import LocalizationHelperTuning
from xml_injector.injector import inject_to

import traceback

XML_INJECTOR_VERSION = 4

logger = sims4.log.Logger('XmlInjector')

def get_version():
    return XML_INJECTOR_VERSION

class DefaultErrorDialog(UiDialogOk):
    def show_dialog(self):
        self.title =  lambda **_: LocalizationHelperTuning.get_raw_text('XML Injector Version')
        self.text = lambda **_: LocalizationHelperTuning.get_raw_text('One of your installed mods requires a newer version of the XML Injector.  That mod will likely not function properly until you upgrade your copy of XML Injector to the latest version.')
        super().show_dialog()

MAX_REQUESTED_VERSION = XML_INJECTOR_VERSION
ERROR_DIALOG = DefaultErrorDialog(None)

# If a requested version > any others requested, this sets the error_dialog if one is provided
# The error dialog for the highest requested version is displayed after lot load, or a default if none are tuned

def request_version(version, error_dialog):
    global MAX_REQUESTED_VERSION, ERROR_DIALOG
    
    if XML_INJECTOR_VERSION < version:
        logger.error('Version {} of XML Injector required by snippet.  Snippet may not load or operate correctly.', version)
        if version > MAX_REQUESTED_VERSION:
            MAX_REQUESTED_VERSION = version
            if not error_dialog is None:
                ERROR_DIALOG = error_dialog

def show_error_dialog():
    global ERROR_DIALOG

    if not ERROR_DIALOG is None and MAX_REQUESTED_VERSION > XML_INJECTOR_VERSION:
        if isinstance(ERROR_DIALOG, DefaultErrorDialog):
            dialog = ERROR_DIALOG.TunableFactory().default(None)
        else:
            dialog = ERROR_DIALOG(None)
        dialog.show_dialog()
    ERROR_DIALOG = None

#sims4.callback_utils.add_callbacks(sims4.callback_utils.CallbackEvent.TRANSITION_SEQUENCE_EXIT, show_error_dialog)
@inject_to(zone.Zone, 'on_loading_screen_animation_finished')
def _on_loading_screen_animation_finished(original, self):
    original(self)
    show_error_dialog()